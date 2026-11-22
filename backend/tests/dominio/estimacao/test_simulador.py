"""F0.18: m_sim — simulação de políticas antes da publicação (Eq. 70; seções 6.5, 6.7, 6.8)."""

import ast
import inspect
import time
from decimal import Decimal

import pytest

from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.dominio.estimacao import (
    ContratoSimulado,
    SerieDeBase,
    SimuladorDePolitica,
    contratos_da_carteira,
    estimar_razao_s2_v2,
    simulador,
)
from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Dinheiro,
    Horas,
    Kappa,
    Regime,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import NucleoDePreco, PoliticaDePreco, RegraDeTransicao
from tests.dominio.modelos.documentos import documento_tabela_7

POLITICA = fabricar_politica(documento_tabela_7())


def _contrato(i: str, regime: Regime, h: str, vigente: str, meses: int = 12) -> ContratoSimulado:
    return ContratoSimulado(i, regime, Horas.de(h), meses, Dinheiro.de(vigente), Kappa.neutro())


CARTEIRA = [
    _contrato("tabela7", Regime.LP, "5.935", "437"),  # sobe em 3 ciclos, teto no 1º
    _contrato("piso", Regime.SN, "1.75", "185"),  # piso vinculante, já no alvo
    _contrato("acima", Regime.LP, "5.935", "750"),  # congelado (fora da zona morta)
    _contrato("novo", Regime.MEI, "0", "50", meses=0),  # sem histórico → π_MEI = 80
]


def test_metricas_da_carteira_pequena() -> None:
    r = SimuladorDePolitica(NucleoDePreco.da_politica(POLITICA)).simular(CARTEIRA)
    assert r.contratos == 4
    assert r.receita_vigente == Decimal(1422)
    assert r.receita_alvo == Decimal("614.27") + 185 + Decimal("614.27") + 80
    # Eq. (70): abaixo do alvo limitado por P0(1+θ); acima preservado
    assert r.receita_ciclo_1 == Decimal("502.55") + 185 + 750 + 80
    assert r.fracao_no_piso == pytest.approx(Decimal(1) / 3)  # só contratos completos
    assert r.fracao_no_teto == pytest.approx(Decimal(1) / 4)
    assert r.fracao_congelados == pytest.approx(Decimal(1) / 4)
    assert r.fracao_gatilho == pytest.approx(Decimal(3) / 4)
    assert r.ciclos_mediana == 1 and r.ciclos_maximo == 3


def test_revisao_integral_do_provisorio_ao_chegar_a_doze_meses() -> None:
    provisorio = ContratoSimulado(
        "p", Regime.LP, Horas.de("5.935"), 12, Dinheiro.de("235"), Kappa.neutro(), provisorio=True
    )
    r = SimuladorDePolitica(NucleoDePreco.da_politica(POLITICA)).simular([provisorio])
    assert r.receita_ciclo_1 == Decimal("614.27")  # sem θ (seção 6.7)


def test_nao_existe_segunda_formula(monkeypatch: pytest.MonkeyPatch) -> None:
    """O simulador só chama k_pol (via k_inf), k_tr e k_din; nunca recalcula max(π, τH)."""
    chamadas = {"alvo": 0, "transicao": 0}
    original_alvo, original_proximo = PoliticaDePreco.preco_alvo, RegraDeTransicao.proximo

    def alvo(self, *a, **k):  # type: ignore[no-untyped-def]
        chamadas["alvo"] += 1
        return original_alvo(self, *a, **k)

    def proximo(self, *a, **k):  # type: ignore[no-untyped-def]
        chamadas["transicao"] += 1
        return original_proximo(self, *a, **k)

    monkeypatch.setattr(PoliticaDePreco, "preco_alvo", alvo)
    monkeypatch.setattr(RegraDeTransicao, "proximo", proximo)
    SimuladorDePolitica(NucleoDePreco.da_politica(POLITICA)).simular(CARTEIRA)
    assert chamadas["alvo"] == 3  # os três com histórico; o sem histórico vai ao piso por k_inf
    assert chamadas["transicao"] >= 4
    fonte = ast.parse(inspect.getsource(simulador))
    atributos = {n.attr for n in ast.walk(fonte) if isinstance(n, ast.Attribute)}
    assert not {"tarifa", "piso", "pisos", "teto_real_theta"} & atributos


def test_razao_s2_v2() -> None:
    # s² = variância mensal média dentro do contrato; v² = E[(base − π_r)²]
    series = [
        SerieDeBase(Regime.SN, Decimal(185), (Decimal(200), Decimal(220))),
        SerieDeBase(Regime.SN, Decimal(185), (Decimal(180), Decimal(200))),
    ]
    s2 = (Decimal(200) + Decimal(200)) / 2  # variâncias amostrais 200 e 200
    v2 = ((Decimal(210) - 185) ** 2 + (Decimal(190) - 185) ** 2) / 2
    assert estimar_razao_s2_v2(series) == pytest.approx(float(s2 / v2))


@pytest.fixture(scope="module")
def mil_contratos() -> Carteira:
    parametros = ParametrosSinteticos(semente=11, contratos=1000)
    return GeradorDeCarteiraSintetica(parametros).extrair(
        Competencia(2025, 1), Competencia(2025, 12)
    )


def test_mil_contratos_em_menos_de_cinco_segundos(mil_contratos: Carteira) -> None:
    inicio = time.perf_counter()
    entrada = contratos_da_carteira(mil_contratos, POLITICA, Competencia(2025, 12))
    resultado = SimuladorDePolitica(NucleoDePreco.da_politica(POLITICA)).simular(entrada.contratos)
    razao = estimar_razao_s2_v2(entrada.series)
    assert time.perf_counter() - inicio < 5
    assert resultado.contratos == 1000
    assert 0 < resultado.fracao_no_piso < 1
    assert resultado.receita_alvo > 0 and razao > 0
