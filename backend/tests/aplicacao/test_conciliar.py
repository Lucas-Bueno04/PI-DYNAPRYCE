"""F1.29: conciliação aprovado × cobrado e simulação mw9kw9i514upw:16."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.conciliar import Conciliar, TratarDivergencia
from dynaprice.aplicacao.erros import AcessoNegado, NaoEncontrado
from dynaprice.dominio.modelos import (
    Competencia,
    Dinheiro,
    Honorario,
    TransicaoInvalida,
    ValorInvalido,
)
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from dynaprice.dominio.modelos.recomendacao import Recomendacao
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

EFEITO = Competencia(2027, 3)


def _exportada(preco: CenarioDePreco, contrato: str = "C1") -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7(contrato)
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        alvo = uow.precos_alvo.gravar(
            contrato, Competencia(2027, 1), 1, 2, Decimal(1), {}, Decimal(1)
        )
        assert alvo is not None
        rec = Recomendacao(
            id=uuid4(),
            contrato_id=contrato,
            preco_alvo_id=alvo,
            politica_versao=1,
            competencia=Competencia(2027, 1),
            efeito=EFEITO,
            preco_vigente=Dinheiro.de(437),
            preco_proposto=Dinheiro.de("502.55"),
            trajetoria=(Dinheiro.de("502.55"),),
        )
        uow.recomendacoes.inserir(rec)
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        aprovada = rec.aprovar(uuid4())
        uow.recomendacoes.salvar(aprovada, 1)
        lote = uuid4()
        uow.lotes.criar_com_id(lote, "h")
        uow.recomendacoes.salvar(aprovada.exportar(lote), aprovada.versao)


def _cobrar(preco: CenarioDePreco, valor: str, contrato: str = "C1") -> None:
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        uow.fatos.gravar_honorario(Honorario(contrato, EFEITO, Dinheiro.de(valor)))


def _conciliar(preco: CenarioDePreco) -> int:
    return Conciliar(preco.fabrica).executar(preco.tenant, EFEITO)


def _divergencia(preco: CenarioDePreco) -> tuple[UUID, str]:
    (linha,) = preco.consulta(
        "SELECT id, situacao FROM core.divergencia_cobranca WHERE tenant_id=%s", preco.tenant
    )
    return linha[0], linha[1]


def _tratar(preco: CenarioDePreco) -> TratarDivergencia:
    return TratarDivergencia(preco.fabrica)


class TestSimulacaoDivergencia:
    """Simulação mw9kw9i514upw:16, passo a passo."""

    def test_quatro_passos(self, preco: CenarioDePreco) -> None:
        _exportada(preco)
        # Passo 1: cobrado 480,00 difere de 502,55.
        _cobrar(preco, "480.00")
        assert _conciliar(preco) == 1
        identificador, situacao = _divergencia(preco)
        assert situacao == "aberta"
        (linha,) = preco.consulta(
            "SELECT aprovado, cobrado FROM core.divergencia_cobranca WHERE id=%s", identificador
        )
        assert linha == (Decimal("502.55"), Decimal("480.00"))
        assert ("divergencia",) in preco.consulta(
            "SELECT tipo FROM core.alerta WHERE tenant_id=%s", preco.tenant
        )
        # Passo 3: o gestor justifica, com auditoria.
        _tratar(preco).justificar(preco.aprovador, identificador, "desconto pontual")
        assert _divergencia(preco)[1] == "justificada"
        assert ("divergencia_justificada",) in preco.consulta(
            "SELECT tipo FROM audit.evento WHERE tenant_id=%s", preco.tenant
        )
        # Passo 4: encerramento.
        _tratar(preco).resolver(preco.aprovador, identificador)
        assert _divergencia(preco)[1] == "resolvida"

    def test_passo2_valores_iguais_nao_abrem(self, preco: CenarioDePreco) -> None:
        _exportada(preco)
        _cobrar(preco, "502.55")
        assert _conciliar(preco) == 0


def test_conciliar_de_novo_nao_duplica(preco: CenarioDePreco) -> None:
    _exportada(preco)
    _cobrar(preco, "480.00")
    assert [_conciliar(preco), _conciliar(preco)] == [1, 0]


def test_sem_recomendacao_exportada_nao_ha_o_que_conciliar(preco: CenarioDePreco) -> None:
    preco.contrato_tabela_7()
    _cobrar(preco, "480.00")
    assert _conciliar(preco) == 0


def test_antes_do_efeito_nao_concilia(preco: CenarioDePreco) -> None:
    _exportada(preco)
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        uow.fatos.gravar_honorario(Honorario("C1", EFEITO.anterior(), Dinheiro.de("437")))
    assert Conciliar(preco.fabrica).executar(preco.tenant, EFEITO.anterior()) == 0


def test_justificar_vazio_e_recusado(preco: CenarioDePreco) -> None:
    _exportada(preco)
    _cobrar(preco, "480.00")
    _conciliar(preco)
    with pytest.raises(ValorInvalido):
        _tratar(preco).justificar(preco.aprovador, _divergencia(preco)[0], "  ")


def test_resolvida_nao_volta(preco: CenarioDePreco) -> None:
    _exportada(preco)
    _cobrar(preco, "480.00")
    _conciliar(preco)
    identificador = _divergencia(preco)[0]
    _tratar(preco).resolver(preco.aprovador, identificador)
    with pytest.raises(TransicaoInvalida):
        _tratar(preco).justificar(preco.aprovador, identificador, "tarde")


def test_tratar_exige_aprovar(preco: CenarioDePreco) -> None:
    analista = Principal(uuid4(), preco.tenant, frozenset({Papel.ANALISAR}), True)
    with pytest.raises(AcessoNegado):
        _tratar(preco).resolver(analista, uuid4())


def test_divergencia_inexistente(preco: CenarioDePreco) -> None:
    with pytest.raises(NaoEncontrado):
        _tratar(preco).resolver(preco.aprovador, uuid4())
