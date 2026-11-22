"""F1.25: vínculos, pendências e simulação mw9kw9i514upw:12 (competência sem vínculo)."""

from uuid import uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.aplicacao.casos_de_uso.vincular import CriarVinculo, ListarPendencias
from dynaprice.aplicacao.erros import AcessoNegado, Conflito
from dynaprice.dominio.modelos import Competencia, Direcionadores, Empresa, Regime, Vinculo
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.aplicacao.preco_apoio import MES, REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco


def _analista(preco: CenarioDePreco) -> Principal:
    return Principal(uuid4(), preco.tenant, frozenset({Papel.ANALISAR}), False)


def _empresa_sem_vinculo(preco: CenarioDePreco, empresa: str = "E9") -> None:
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        uow.empresas.salvar(Empresa(empresa, Regime.LP))
        for i in range(12):
            uow.fatos.gravar_empresa_mes(
                Direcionadores(empresa, REFERENCIA.somar(-i), MES), {}, 1, Regime.LP
            )


def _recalibrar(preco: CenarioDePreco, competencia: Competencia = REFERENCIA):  # type: ignore[no-untyped-def]
    return Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, competencia)


class TestSimulacaoCompetenciaSemVinculo:
    """Simulação mw9kw9i514upw:12, passo a passo."""

    def test_quatro_passos(self, preco: CenarioDePreco) -> None:
        preco.publicar_politica()
        preco.contrato_tabela_7("CX", mes_reajuste=3, meses=0)
        # Passo 1: empresa com movimento e sem contrato vira pendência.
        _empresa_sem_vinculo(preco)
        pendencias = ListarPendencias(preco.fabrica).executar(_analista(preco), REFERENCIA)
        assert pendencias == ["E9"]
        # Passo 2: fora do cálculo, listada no resultado.
        resumo = _recalibrar(preco)
        assert "E9" in resumo.pendencias
        assert (
            preco.consulta(
                "SELECT 1 FROM core.preco_alvo WHERE tenant_id=%s AND entradas->'empresas' ? 'E9'",
                preco.tenant,
            )
            == []
        )
        # Passo 3: o vínculo é criado na competência.
        CriarVinculo(preco.fabrica).executar(
            _analista(preco), Vinculo("E9", "CX", Competencia(2026, 1), principal=False)
        )
        assert ListarPendencias(preco.fabrica).executar(_analista(preco), REFERENCIA) == []
        # Passo 4: sem recálculo automático; entra na recalibração seguinte.
        assert (
            preco.consulta(
                "SELECT count(*) FROM core.preco_alvo WHERE tenant_id=%s AND competencia=%s",
                preco.tenant,
                "2027-01-01",
            )[0][0]
            == 1
        )
        _recalibrar(preco, REFERENCIA.proxima())
        (linha,) = preco.consulta(
            "SELECT entradas FROM core.preco_alvo WHERE tenant_id=%s AND competencia=%s",
            preco.tenant,
            "2027-02-01",
        )
        assert "E9" in linha[0]["empresas"]


def test_empresa_sem_movimento_nao_e_pendencia(preco: CenarioDePreco) -> None:
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        uow.empresas.salvar(Empresa("E0", Regime.SN))
    assert ListarPendencias(preco.fabrica).executar(_analista(preco), REFERENCIA) == []


def test_vinculo_sobreposto_e_conflito(preco: CenarioDePreco) -> None:
    preco.contrato_tabela_7("C1")
    with pytest.raises(Conflito):
        CriarVinculo(preco.fabrica).executar(
            _analista(preco), Vinculo("E-C1", "C1", Competencia(2026, 6), principal=True)
        )


def test_criar_vinculo_exige_papel(preco: CenarioDePreco) -> None:
    aprovador = Principal(uuid4(), preco.tenant, frozenset({Papel.APROVAR}), True)
    with pytest.raises(AcessoNegado):
        CriarVinculo(preco.fabrica).executar(
            aprovador, Vinculo("E", "C", Competencia(2026, 1), principal=True)
        )
