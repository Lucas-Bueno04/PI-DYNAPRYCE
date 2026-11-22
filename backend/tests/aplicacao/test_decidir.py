"""F1.27: decisão humana sobre a recomendação (aprovar, ajustar κ, rejeitar)."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.decidir import (
    AjustarKappa,
    Aprovar,
    DecidirRecomendacao,
    Rejeitar,
)
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.aplicacao.erros import AcessoNegado, Conflito, NaoEncontrado
from dynaprice.dominio.modelos import ValorInvalido
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco


def _pendente(preco: CenarioDePreco) -> UUID:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)
    (linha,) = preco.consulta("SELECT id FROM core.recomendacao WHERE tenant_id=%s", preco.tenant)
    identificador: UUID = linha[0]
    return identificador


def _decidir(preco: CenarioDePreco) -> DecidirRecomendacao:
    return DecidirRecomendacao(preco.fabrica, preco.relogio)


def _estado(preco: CenarioDePreco) -> tuple[object, ...]:
    (linha,) = preco.consulta(
        "SELECT estado, preco_proposto, kappa, motivo, versao FROM core.recomendacao "
        "WHERE tenant_id=%s",
        preco.tenant,
    )
    return linha


def test_aprovar(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    _decidir(preco).executar(preco.aprovador, rec, 1, Aprovar())
    assert _estado(preco)[:2] == ("aprovada", Decimal("502.55"))


def test_rejeitar_exige_motivo(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    with pytest.raises(ValorInvalido):
        _decidir(preco).executar(preco.aprovador, rec, 1, Rejeitar("  "))
    _decidir(preco).executar(preco.aprovador, rec, 1, Rejeitar("cliente em renegociação"))
    assert _estado(preco)[0] == "rejeitada"


def test_ajustar_kappa_recalcula_alvo_e_passo(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    _decidir(preco).executar(preco.aprovador, rec, 1, AjustarKappa(Decimal("1.05"), ""))
    estado, proposto, kappa, *_ = _estado(preco)
    assert estado == "aprovada"
    assert kappa == Decimal("1.0500")
    # Alvo novo 644,98 ainda acima do teto do ciclo: o passo continua limitado por θ.
    assert proposto == Decimal("502.55")
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        contrato = uow.contratos.obter("C1")
    assert contrato is not None
    assert contrato.kappa.valor == Decimal("1.05")


def test_kappa_acima_do_maximo_e_recusado(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    with pytest.raises(ValorInvalido):
        _decidir(preco).executar(preco.aprovador, rec, 1, AjustarKappa(Decimal("1.21"), "texto"))


def test_kappa_abaixo_de_um_e_recusado(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    with pytest.raises(ValorInvalido):
        _decidir(preco).executar(preco.aprovador, rec, 1, AjustarKappa(Decimal("0.9"), "texto"))


def test_kappa_acima_de_cinco_por_cento_exige_justificativa(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    with pytest.raises(ValorInvalido):
        _decidir(preco).executar(preco.aprovador, rec, 1, AjustarKappa(Decimal("1.06"), " "))
    _decidir(preco).executar(preco.aprovador, rec, 1, AjustarKappa(Decimal("1.06"), "complexo"))
    assert _estado(preco)[0] == "aprovada"


def test_versao_antiga_e_conflito(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    _decidir(preco).executar(preco.aprovador, rec, 1, Aprovar())
    with pytest.raises(Conflito):
        _decidir(preco).executar(preco.aprovador, rec, 1, Rejeitar("tarde"))


def test_dois_gestores_um_vence(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)

    def decidir(_: int) -> str:
        try:
            _decidir(preco).executar(preco.aprovador, rec, 1, Aprovar())
        except Conflito:
            return "conflito"
        return "ok"

    with ThreadPoolExecutor(4) as executor:
        resultados = sorted(executor.map(decidir, range(4)))
    assert resultados == ["conflito", "conflito", "conflito", "ok"]
    assert _estado(preco)[4] == 2


def test_decisao_auditada_e_cadeia_integra(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    aprovador = preco.aprovador
    _decidir(preco).executar(aprovador, rec, 1, Aprovar())
    assert preco.consulta(
        "SELECT usuario_id FROM audit.evento WHERE tenant_id=%s AND tipo=%s",
        preco.tenant,
        "recomendacao_aprovada",
    ) == [(aprovador.usuario_id,)]
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        assert uow.auditoria.primeira_quebra() is None


def test_aprovar_exige_totp_na_sessao(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    sem_mfa = Principal(preco.aprovador.usuario_id, preco.tenant, frozenset({Papel.APROVAR}), False)
    with pytest.raises(AcessoNegado):
        _decidir(preco).executar(sem_mfa, rec, 1, Aprovar())


def test_recomendacao_de_outro_inquilino_nao_existe(preco: CenarioDePreco) -> None:
    rec = _pendente(preco)
    outro = Principal(uuid4(), uuid4(), frozenset({Papel.APROVAR}), True)
    with pytest.raises(NaoEncontrado):
        _decidir(preco).executar(outro, rec, 1, Aprovar())
