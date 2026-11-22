"""F2.2: cotação de cliente novo pela cascata da ADR-004 (d_cot).

Política de referência: π_LP = 235, τ = 103,5, κ̄ = 1,2, s²/v² = 2, arredondamento em centavos.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.cotar import (
    CotarServico,
    PedidoDeCotacao,
    ReproduzirCotacao,
)
from dynaprice.aplicacao.erros import AcessoNegado, Conflito, NaoEncontrado
from dynaprice.aplicacao.politica_em_memoria import PoliticaEmMemoria
from dynaprice.dominio.modelos import Dinheiro, Regime, ValorInvalido
from dynaprice.dominio.modelos.autenticacao import Principal
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco
from tests.dominio.modelos.documentos import documento_tabela_7


@pytest.fixture
def memoria() -> PoliticaEmMemoria:
    return PoliticaEmMemoria()


@pytest.fixture
def cotar(preco: CenarioDePreco, memoria: PoliticaEmMemoria) -> CotarServico:
    return CotarServico(preco.fabrica, preco.relogio, memoria)


def _pedido(regime: Regime = Regime.LP, **campos: object) -> PedidoDeCotacao:
    return PedidoDeCotacao(regime=regime, **campos)  # type: ignore[arg-type]


def test_sem_historico_cobra_o_piso_do_regime(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    cotacao = cotar.executar(preco.aprovador, _pedido())
    assert cotacao.preco == Dinheiro.de("235.00")
    assert cotacao.provisorio is True
    assert cotacao.politica_versao == 1
    d = cotacao.decomposicao
    assert (d["nivel_informacao"], d["credibilidade_z"], d["piso"]) == (0, "0", "235.00")
    assert d["base_propria"] is None
    assert "piso do regime" in d["motivo"]


def test_historico_parcial_mistura_esforco_e_piso_por_credibilidade(
    preco: CenarioDePreco, cotar: CotarServico
) -> None:
    preco.publicar_politica()
    cotacao = cotar.executar(preco.aprovador, _pedido(meses=4, horas_padrao=Decimal(3)))
    # Z = 4/(4+2) = 2/3; base própria = max(235; 103,5·3 = 310,5); P = 2/3·310,5 + 1/3·235
    assert cotacao.preco == Dinheiro.de("285.33")
    d = cotacao.decomposicao
    assert d["nivel_informacao"] == 1 and cotacao.provisorio is True
    assert Decimal(d["credibilidade_z"]).quantize(Decimal("0.0001")) == Decimal("0.6667")
    assert d["base_propria"] == "310.50" and d["piso_vinculante"] is False


def test_kappa_entra_no_preco_e_na_decomposicao(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    cotacao = cotar.executar(
        preco.aprovador, _pedido(meses=4, horas_padrao=Decimal(3), kappa=Decimal("1.1"))
    )
    assert cotacao.preco == Dinheiro.de("313.87")
    assert cotacao.decomposicao["kappa"] == "1.1"


def test_doze_meses_e_definitivo_pelo_preco_alvo(
    preco: CenarioDePreco, cotar: CotarServico
) -> None:
    preco.publicar_politica()
    cotacao = cotar.executar(preco.aprovador, _pedido(meses=12, horas_padrao=Decimal(1)))
    assert cotacao.preco == Dinheiro.de("235.00")  # τ·1 = 103,5 < piso
    assert cotacao.provisorio is False
    assert cotacao.decomposicao["piso_vinculante"] is True


def test_sem_politica_publicada_e_conflito(preco: CenarioDePreco, cotar: CotarServico) -> None:
    with pytest.raises(Conflito, match="política"):
        cotar.executar(preco.aprovador, _pedido())


def test_kappa_acima_do_maximo_da_politica_e_recusado(
    preco: CenarioDePreco, cotar: CotarServico
) -> None:
    preco.publicar_politica()
    with pytest.raises(ValorInvalido):
        cotar.executar(
            preco.aprovador, _pedido(meses=2, horas_padrao=Decimal(3), kappa=Decimal("1.3"))
        )


def test_historico_sem_horas_padrao_e_recusado(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    with pytest.raises(ValorInvalido, match="horas"):
        cotar.executar(preco.aprovador, _pedido(meses=3))


def test_meses_negativos_sao_recusados(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    with pytest.raises(ValorInvalido):
        cotar.executar(preco.aprovador, _pedido(meses=-1))


def test_politica_desatualizada_na_memoria_cede_a_nova_versao(
    preco: CenarioDePreco, cotar: CotarServico
) -> None:
    preco.publicar_politica()
    assert cotar.executar(preco.aprovador, _pedido()).preco == Dinheiro.de("235.00")
    novo = documento_tabela_7()
    novo["piso_por_segmento"]["LP"] = "250"
    preco.publicar_politica(novo)
    depois = cotar.executar(preco.aprovador, _pedido())
    assert (depois.preco, depois.politica_versao) == (Dinheiro.de("250.00"), 2)


def test_reprodutibilidade_apos_nova_publicacao(
    preco: CenarioDePreco, cotar: CotarServico, memoria: PoliticaEmMemoria
) -> None:
    preco.publicar_politica()
    original = cotar.executar(preco.aprovador, _pedido(meses=4, horas_padrao=Decimal(3)))
    novo = documento_tabela_7()
    novo["piso_por_segmento"]["LP"] = "250"
    preco.publicar_politica(novo)
    reproduzida = ReproduzirCotacao(preco.fabrica).executar(preco.aprovador, original.id)
    assert reproduzida.gravado == original.preco.valor
    assert reproduzida.recalculado == original.preco.valor


def test_cotacao_de_outro_inquilino_nao_existe(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    cotacao = cotar.executar(preco.aprovador, _pedido())
    estranho = Principal(uuid4(), uuid4(), preco.aprovador.papeis)
    with pytest.raises(NaoEncontrado):
        ReproduzirCotacao(preco.fabrica).executar(estranho, cotacao.id)


def test_grava_entradas_versao_e_auditoria(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    quem = preco.aprovador
    cotacao = cotar.executar(quem, _pedido(meses=4, horas_padrao=Decimal(3)))
    (linha,) = preco.consulta(
        "SELECT regime, politica_versao, preco, entradas->>'meses', criada_por "
        "FROM core.cotacao WHERE id = %s",
        cotacao.id,
    )
    assert linha == ("LP", 1, Decimal("285.33"), "4", quem.usuario_id)
    (total,) = preco.consulta(
        "SELECT count(*) FROM audit.evento WHERE tenant_id=%s AND tipo='cotacao_criada'",
        preco.tenant,
    )[0]
    assert total == 1


def test_principal_sem_papel_e_negado(preco: CenarioDePreco, cotar: CotarServico) -> None:
    preco.publicar_politica()
    sem_papel = Principal(uuid4(), preco.tenant, frozenset())
    with pytest.raises(AcessoNegado):
        cotar.executar(sem_papel, _pedido())
