"""F0.5: PoliticaVersao imutável e validada; montada pela fábrica do documento (Quadro 7)."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from typing import Any

import pytest

from dynaprice.dominio.modelos import (
    Departamento,
    Dinheiro,
    EstadoPolitica,
    OrigemTarifa,
    PoliticaVersao,
    Regime,
    RegraSemHistorico,
    Tarifa,
    TransicaoInvalida,
    ValorInvalido,
    fabricar_politica,
)
from tests.dominio.modelos.documentos import documento_tabela_7


@pytest.fixture
def politica() -> PoliticaVersao:
    return fabricar_politica(documento_tabela_7())


def test_fabrica_monta_a_politica_do_quadro_7(politica: PoliticaVersao) -> None:
    assert politica.versao == 1
    assert politica.piso(Regime.LP) == Dinheiro.de("235")
    assert politica.tarifa == Tarifa.de("103.5")
    assert politica.origem_tarifa is OrigemTarifa.PRECO_REVELADO
    assert politica.teto_real_theta == Decimal("0.15")
    assert politica.gatilho_delta == Decimal("0.15")
    assert politica.kappa_maximo == Decimal("1.2")
    assert politica.razao_s2_v2 == Decimal("2")
    assert politica.sem_historico is RegraSemHistorico.PISO_REGIME
    assert politica.fechamento_dias == 5
    assert politica.antecedencia_reajuste_meses == 2
    assert politica.estado is EstadoPolitica.RASCUNHO


def test_equacoes_de_tempo_ficam_na_versao(politica: PoliticaVersao) -> None:
    fiscal = politica.equacao(Departamento.FISCAL, Regime.LP)
    assert fiscal.beta0_horas == Decimal("0.91")
    assert fiscal.inclinacoes_minutos["notas_entrada"] == Decimal("3.75")


def test_valores_monetarios_sao_decimal(politica: PoliticaVersao) -> None:
    for regime in Regime:
        assert isinstance(politica.piso(regime).valor, Decimal)
    assert isinstance(politica.tarifa.valor, Decimal)


def test_politica_e_imutavel(politica: PoliticaVersao) -> None:
    with pytest.raises(FrozenInstanceError):
        politica.versao = 2  # type: ignore[misc]
    with pytest.raises(TypeError):
        politica.pisos[Regime.MEI] = Dinheiro.de("1")  # type: ignore[index]
    with pytest.raises(TypeError):
        politica.equacao(Departamento.FISCAL, Regime.LP).inclinacoes_minutos["x"] = Decimal(1)  # type: ignore[index]


def test_documento_mutado_depois_nao_altera_a_politica() -> None:
    documento = documento_tabela_7()
    politica = fabricar_politica(documento)
    documento["piso_por_segmento"]["LP"] = "999"
    assert politica.piso(Regime.LP) == Dinheiro.de("235")


def _com(alteracao: dict[str, Any]) -> dict[str, Any]:
    documento = documento_tabela_7()
    documento.update(alteracao)
    return documento


@pytest.mark.parametrize(
    "alteracao",
    [
        {"piso_por_segmento": {"MEI": "80", "SN": "185", "LP": "235"}},  # falta LR
        {"piso_por_segmento": {"MEI": "0", "SN": "185", "LP": "235", "LR": "340"}},
        {"tarifa_hora_padrao": {"valor": "0", "origem": "preco_revelado"}},
        {"tarifa_hora_padrao": {"valor": "103.5", "origem": "chute"}},
        {"reajuste": {"teto_real_por_ciclo": "-0.01", "antecedencia_meses": 2}},
        {"gatilho_revisao": "-0.01"},
        {"kappa_maximo": "0"},
        {"kappa_maximo": "1.3"},  # D12 revisada: κ̄ ≤ 1,2
        {"informacao_incompleta": {"sem_historico": "piso_regime", "razao_s2_v2": "0"}},
        {"informacao_incompleta": {"sem_historico": "vizinhos", "razao_s2_v2": "2"}},
        {"fechamento_dias": -1},
        {"versao": 0},
        {"tarifa_hora_padrao": {"valor": 103.5, "origem": "preco_revelado"}},  # float recusado
    ],
)
def test_documento_invalido_e_recusado(alteracao: dict[str, Any]) -> None:
    with pytest.raises(ValorInvalido):
        fabricar_politica(_com(alteracao))


def test_campo_obrigatorio_ausente() -> None:
    documento = documento_tabela_7()
    del documento["gatilho_revisao"]
    with pytest.raises(ValorInvalido, match="gatilho_revisao"):
        fabricar_politica(documento)


def test_equacao_duplicada_e_recusada() -> None:
    documento = documento_tabela_7()
    documento["equacoes_de_tempo"].append(documento["equacoes_de_tempo"][0])
    with pytest.raises(ValorInvalido, match="duplicada"):
        fabricar_politica(documento)


def test_equacao_por_regime_tem_precedencia() -> None:
    documento = documento_tabela_7()
    documento["equacoes_de_tempo"].append(
        {
            "departamento": "fiscal",
            "regime": "LR",
            "beta0_horas": "2",
            "inclinacoes_minutos": {"notas_entrada": "5"},
        }
    )
    politica = fabricar_politica(documento)
    assert politica.equacao(Departamento.FISCAL, Regime.LR).beta0_horas == Decimal("2")
    assert politica.equacao(Departamento.FISCAL, Regime.SN).beta0_horas == Decimal("0.91")


def test_departamento_sem_equacao() -> None:
    documento = documento_tabela_7()
    documento["equacoes_de_tempo"].pop()
    politica = fabricar_politica(documento)
    with pytest.raises(ValorInvalido, match="folha"):
        politica.equacao(Departamento.FOLHA, Regime.LP)


def test_inclinacao_negativa_recusada() -> None:
    documento = documento_tabela_7()
    documento["equacoes_de_tempo"][0]["inclinacoes_minutos"] = {"notas_entrada": "-1"}
    with pytest.raises(ValorInvalido):
        fabricar_politica(documento)


class TestEstados:
    def test_publicar_gera_nova_instancia_publicada(self, politica: PoliticaVersao) -> None:
        publicada = politica.publicar()
        assert publicada.estado is EstadoPolitica.PUBLICADA
        assert politica.estado is EstadoPolitica.RASCUNHO

    def test_nao_publica_duas_vezes(self, politica: PoliticaVersao) -> None:
        with pytest.raises(TransicaoInvalida):
            politica.publicar().publicar()

    def test_substituir_so_publicada(self, politica: PoliticaVersao) -> None:
        with pytest.raises(TransicaoInvalida):
            politica.substituir()
        assert politica.publicar().substituir().estado is EstadoPolitica.SUBSTITUIDA

    def test_construtor_valida_mesmo_sem_fabrica(self, politica: PoliticaVersao) -> None:
        with pytest.raises(ValorInvalido):
            replace(politica, teto_real_theta=Decimal("-1"))
