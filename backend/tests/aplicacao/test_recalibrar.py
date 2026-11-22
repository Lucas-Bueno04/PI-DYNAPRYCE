"""F1.26: recalibração mensal e simulação mw9kw9i514upw:14 (fora da janela de reajuste)."""

from decimal import Decimal

import pytest

from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.aplicacao.portas import ErroPermanente
from dynaprice.dominio.modelos import Competencia
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco


def _recalibrar(preco: CenarioDePreco, competencia: Competencia = REFERENCIA):  # type: ignore[no-untyped-def]
    return Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, competencia)


def _recomendacoes(preco: CenarioDePreco) -> list[tuple[object, ...]]:
    return preco.consulta(
        """SELECT contrato_id, estado, preco_vigente, preco_proposto, data_efeito, politica_versao
           FROM core.recomendacao WHERE tenant_id = %s ORDER BY contrato_id, competencia""",
        preco.tenant,
    )


def test_tabela_7_gera_recomendacao_com_trajetoria(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    resumo = _recalibrar(preco)
    assert resumo.recomendacoes == 1
    (linha,) = preco.consulta(
        """SELECT estado, preco_proposto, trajetoria, data_efeito FROM core.recomendacao
           WHERE tenant_id = %s""",
        preco.tenant,
    )
    assert linha[0] == "pendente"
    assert linha[1] == Decimal("502.55")
    assert linha[2] == ["502.55", "577.93", "614.27"]
    assert (linha[3].year, linha[3].month) == (2027, 3)


def test_preco_alvo_grava_as_entradas(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    _recalibrar(preco)
    (linha,) = preco.consulta(
        """SELECT preco_alvo, h_pad, nivel_informacao, entradas, politica_versao
           FROM core.preco_alvo WHERE tenant_id = %s""",
        preco.tenant,
    )
    assert linha[0] == Decimal("614.27")
    assert linha[1] == Decimal("5.9350")
    assert linha[2] == 2
    assert linha[3]["regime"] == "LP"
    assert linha[3]["meses"] == 12
    assert linha[4] == 1


def test_repetir_nao_duplica(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    _recalibrar(preco)
    assert _recalibrar(preco).recomendacoes == 0
    assert len(_recomendacoes(preco)) == 1
    assert (
        len(preco.consulta("SELECT 1 FROM core.preco_alvo WHERE tenant_id=%s", preco.tenant)) == 1
    )


def test_sem_politica_publicada_e_erro_permanente(preco: CenarioDePreco) -> None:
    preco.contrato_tabela_7()
    with pytest.raises(ErroPermanente):
        _recalibrar(preco)


def test_politica_fica_fixa_na_recomendacao(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.publicar_politica()
    preco.contrato_tabela_7()
    _recalibrar(preco)
    assert _recomendacoes(preco)[0][5] == 2


class TestSimulacaoForaDaJanela:
    """Simulação mw9kw9i514upw:14, passo a passo."""

    def test_tres_passos(self, preco: CenarioDePreco) -> None:
        preco.publicar_politica()
        preco.contrato_tabela_7("A", mes_reajuste=3)
        preco.contrato_tabela_7("B", mes_reajuste=7)
        # Passo 1: recalibração de janeiro, efeito em março (D7).
        resumo = _recalibrar(preco, Competencia(2027, 1))
        # Passo 2: A recebe recomendação.
        assert [linha[0] for linha in _recomendacoes(preco)] == ["A"]
        # Passo 3: B fica monitorado, com preço-alvo gravado e sem recomendação.
        assert resumo.recomendacoes == 1
        assert resumo.monitorados == 1
        alvos = preco.consulta(
            "SELECT contrato_id FROM core.preco_alvo WHERE tenant_id = %s ORDER BY 1", preco.tenant
        )
        assert alvos == [("A",), ("B",)]


def test_sem_mes_de_reajuste_fica_pendente_de_cadastro(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7(mes_reajuste=None)
    resumo = _recalibrar(preco)
    assert resumo.recomendacoes == 0
    assert resumo.sem_mes_de_reajuste == ("C1",)


def test_dentro_da_zona_morta_nao_recomenda(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7(vigente="580")
    assert _recalibrar(preco).recomendacoes == 0


def test_pendente_antiga_expira_na_seguinte(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    _recalibrar(preco, Competencia(2027, 1))
    resumo = _recalibrar(preco, Competencia(2027, 2))
    assert resumo.expiradas == 1
    assert [linha[1] for linha in _recomendacoes(preco)] == ["expirada"]


def test_aprovada_nao_exportada_e_pulada_e_alerta(preco: CenarioDePreco) -> None:
    from dynaprice.aplicacao.casos_de_uso.decidir import Aprovar, DecidirRecomendacao

    preco.publicar_politica()
    preco.contrato_tabela_7()
    _recalibrar(preco, Competencia(2027, 1))
    (linha,) = preco.consulta("SELECT id FROM core.recomendacao WHERE tenant_id=%s", preco.tenant)
    DecidirRecomendacao(preco.fabrica, preco.relogio).executar(
        preco.aprovador, linha[0], 1, Aprovar()
    )
    resumo = _recalibrar(preco, Competencia(2028, 1))
    assert resumo.pulados == ("C1",)
    assert [linha[1] for linha in _recomendacoes(preco)] == ["aprovada"]
    assert ("recomendacao_nao_exportada",) in preco.consulta(
        "SELECT tipo FROM core.alerta WHERE tenant_id=%s", preco.tenant
    )


def test_provisorio_com_doze_meses_tem_revisao_integral_fora_da_janela(
    preco: CenarioDePreco,
) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7(mes_reajuste=7, provisorio=True)
    assert _recalibrar(preco).recomendacoes == 1
    (linha,) = preco.consulta(
        "SELECT preco_proposto, trajetoria FROM core.recomendacao WHERE tenant_id=%s", preco.tenant
    )
    assert linha[0] == Decimal("614.27")
    assert linha[1] == ["614.27"]


def test_provisorio_com_historico_parcial_so_monitora(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7(mes_reajuste=3, meses=6, provisorio=True)
    resumo = _recalibrar(preco)
    assert (resumo.recomendacoes, resumo.monitorados) == (0, 1)


def test_inflacao_ausente_fica_registrada_e_alerta(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    _recalibrar(preco)
    (linha,) = preco.consulta(
        "SELECT entradas FROM core.preco_alvo WHERE tenant_id=%s", preco.tenant
    )
    assert linha[0]["inflacao"] == "0"
    assert linha[0]["inflacao_ausente"] is True
    assert ("indice_ausente",) in preco.consulta(
        "SELECT tipo FROM core.alerta WHERE tenant_id=%s", preco.tenant
    )


def test_inflacao_entra_na_transicao(preco: CenarioDePreco) -> None:
    import psycopg

    preco.publicar_politica()
    preco.contrato_tabela_7()
    with psycopg.connect(preco.banco.superusuario, autocommit=True) as s:
        s.execute(
            "INSERT INTO core.indice_inflacao VALUES ('2099-01-01', 'IPCA', 0, 'x') "
            "ON CONFLICT DO NOTHING"
        )
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        assert uow.fatos.inflacao_acumulada(Competencia(2099, 1), Competencia(2099, 1)) == 0


def test_mudanca_de_regime_conta_so_meses_do_regime_atual(preco: CenarioDePreco) -> None:
    """D13: meses do regime anterior não contam; ℓ cai e o contrato volta a provisório."""
    from dynaprice.dominio.modelos import Direcionadores, Regime
    from tests.aplicacao.preco_apoio import MES

    preco.publicar_politica()
    preco.contrato_tabela_7(meses=0, mes_reajuste=3)
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        for i in range(12):
            regime = Regime.LP if i < 4 else Regime.SN
            uow.fatos.gravar_empresa_mes(
                Direcionadores("E-C1", REFERENCIA.somar(-i), MES), {}, 1, regime
            )
    resumo = _recalibrar(preco)
    (linha,) = preco.consulta(
        "SELECT nivel_informacao, entradas FROM core.preco_alvo WHERE tenant_id=%s", preco.tenant
    )
    assert (linha[0], linha[1]["meses"]) == (1, 4)
    assert resumo.recomendacoes == 0
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        contrato = uow.contratos.obter("C1")
    assert contrato is not None
    assert contrato.provisorio is True
