"""State da recomendação: transições válidas são métodos; o resto é erro de domínio (F1.3)."""

from uuid import uuid4

import pytest

from dynaprice.dominio.modelos import Competencia, Dinheiro, Kappa, TransicaoInvalida
from dynaprice.dominio.modelos.recomendacao import EstadoRecomendacao as E
from dynaprice.dominio.modelos.recomendacao import Recomendacao

POR = uuid4()
LOTE = uuid4()


def _pendente() -> Recomendacao:
    return Recomendacao(
        id=uuid4(),
        contrato_id="C1",
        preco_alvo_id=uuid4(),
        politica_versao=1,
        competencia=Competencia(2027, 1),
        efeito=Competencia(2027, 3),
        preco_vigente=Dinheiro.de(437),
        preco_proposto=Dinheiro.de("502.55"),
        trajetoria=(Dinheiro.de("502.55"), Dinheiro.de("577.93"), Dinheiro.de("614.27")),
    )


def test_caminho_feliz() -> None:
    aprovada = _pendente().aprovar(POR)
    assert aprovada.estado is E.APROVADA
    assert aprovada.decidido_por == POR
    assert aprovada.exportar(LOTE).estado is E.EXPORTADA


def test_ajuste_troca_preco_kappa_e_trajetoria() -> None:
    novo = (Dinheiro.de("510.00"), Dinheiro.de("600.00"))
    ajustada = _pendente().aprovar(POR, Kappa.de("1.1"), novo)
    assert ajustada.kappa == Kappa.de("1.1")
    assert ajustada.preco_proposto == Dinheiro.de("510.00")
    assert ajustada.trajetoria == novo


def test_rejeitar_guarda_o_motivo() -> None:
    rejeitada = _pendente().rejeitar(POR, "cliente em renegociação")
    assert (rejeitada.estado, rejeitada.motivo) == (E.REJEITADA, "cliente em renegociação")


def test_falha_de_exportacao_e_nova_tentativa() -> None:
    falha = _pendente().aprovar(POR).falhar_exportacao()
    assert falha.estado is E.FALHA_EXPORTACAO
    assert falha.tentar_de_novo().estado is E.APROVADA


@pytest.mark.parametrize(
    "transicao",
    [
        lambda r: r.exportar(LOTE),
        lambda r: r.falhar_exportacao(),
        lambda r: r.tentar_de_novo(),
    ],
)
def test_pendente_nao_pula_etapas(transicao) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(TransicaoInvalida):
        transicao(_pendente())


def test_aprovada_nao_expira() -> None:
    with pytest.raises(TransicaoInvalida):
        _pendente().aprovar(POR).expirar()


def test_decidida_nao_e_decidida_de_novo() -> None:
    with pytest.raises(TransicaoInvalida):
        _pendente().rejeitar(POR, "m").aprovar(POR)


def test_transicao_incrementa_a_versao() -> None:
    assert _pendente().aprovar(POR).versao == 2


def test_falha_de_exportacao_nao_e_aprovada_de_novo_pela_decisao() -> None:
    with pytest.raises(TransicaoInvalida):
        _pendente().aprovar(POR).falhar_exportacao().aprovar(POR)
