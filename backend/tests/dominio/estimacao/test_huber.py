"""F0.16: m_teq — equações de tempo por regressão robusta de Huber (seções 5.8 e 5.9)."""

from decimal import Decimal

import pytest

from dynaprice.adaptadores.saida.sintetico import EQUACOES_VERDADEIRAS
from dynaprice.dominio.estimacao import (
    ESPECIFICACAO_PADRAO,
    AmostraDeDepartamento,
    EstimadorHuber,
    amostras_da_carteira,
)
from dynaprice.dominio.modelos import Carteira, Departamento, ValorInvalido

# Intervalo declarado: o gerador mede horas registradas = H*/ϱ x atípico x erro (mediana
# e^(-σ²/2)); Huber estima a escala típica, ≈ 0,92 x β gerador. Aceita-se [0,75; 1,25] x β.
FAIXA = (Decimal("0.75"), Decimal("1.25"))
# Eventos raros (média < 1 por mês, concentrados nas empresas grandes, onde o erro
# multiplicativo é maior e o Huber atenua): erro-padrão maior, intervalo [0,5; 1,5] x β.
EVENTOS_RAROS = {"admissoes", "rescisoes"}
FAIXA_RARA = (Decimal("0.5"), Decimal("1.5"))
# Eventos raros (média < 1 por mês, concentrados nas empresas grandes, onde o erro
# multiplicativo é maior e o Huber atenua): erro-padrão maior, intervalo [0,5; 1,5] x β.
EVENTOS_RAROS = {"admissoes", "rescisoes"}
FAIXA_RARA = (Decimal("0.5"), Decimal("1.5"))


@pytest.fixture(scope="module")
def amostras(carteira: Carteira) -> dict[Departamento, AmostraDeDepartamento]:
    return {a.departamento: a for a in amostras_da_carteira(carteira, ESPECIFICACAO_PADRAO)}


def test_amostras_so_com_departamentos_atendidos(
    carteira: Carteira, amostras: dict[Departamento, AmostraDeDepartamento]
) -> None:
    atendem = sum(1 for e in carteira.empresas if e.atende(Departamento.FOLHA))
    assert set(amostras) == set(Departamento)
    assert len(amostras[Departamento.FOLHA].horas) <= atendem * 12
    assert len(amostras[Departamento.FISCAL].horas) == len(amostras[Departamento.FISCAL].matriz)


@pytest.mark.parametrize("verdadeira", EQUACOES_VERDADEIRAS, ids=lambda e: e.departamento.value)
def test_beta_dentro_do_intervalo_do_gerador(
    verdadeira: object, amostras: dict[Departamento, AmostraDeDepartamento]
) -> None:
    from dynaprice.dominio.modelos import EquacaoDeTempo

    assert isinstance(verdadeira, EquacaoDeTempo)
    estimada = EstimadorHuber().estimar(amostras[verdadeira.departamento]).equacao
    baixo, alto = FAIXA
    assert baixo * verdadeira.beta0_horas <= estimada.beta0_horas <= alto * verdadeira.beta0_horas
    for nome, beta in verdadeira.inclinacoes_minutos.items():
        if beta >= 1:  # inclinações quase nulas (notas de saída, automáticos) só ≥ 0
            minimo, maximo = FAIXA_RARA if nome in EVENTOS_RAROS else FAIXA
            assert minimo * beta <= estimada.inclinacoes_minutos[nome] <= maximo * beta, nome
        else:
            assert Decimal(0) <= estimada.inclinacoes_minutos[nome] <= Decimal(1), nome


def test_reprodutivel(amostras: dict[Departamento, AmostraDeDepartamento]) -> None:
    a = EstimadorHuber().estimar(amostras[Departamento.CONTABIL])
    b = EstimadorHuber().estimar(amostras[Departamento.CONTABIL])
    assert a == b


def test_diagnostico_e_tipos(amostras: dict[Departamento, AmostraDeDepartamento]) -> None:
    resultado = EstimadorHuber().estimar(amostras[Departamento.FISCAL])
    assert resultado.observacoes == len(amostras[Departamento.FISCAL].horas)
    assert 0 < resultado.fracao_atenuada < 1  # Huber atenuou os atípicos (9.8)
    assert isinstance(resultado.equacao.beta0_horas, Decimal)


def test_inclinacao_negativa_vira_zero_e_fica_registrada() -> None:
    amostra = AmostraDeDepartamento(
        Departamento.FISCAL,
        ("x",),
        matriz=((0.0,), (10.0,), (20.0,), (30.0,), (40.0,)),
        horas=(5.0, 4.0, 3.0, 2.0, 1.0),
    )
    resultado = EstimadorHuber().estimar(amostra)
    assert resultado.equacao.inclinacoes_minutos["x"] == Decimal(0)
    assert resultado.truncadas == ("x",)


def test_amostra_pequena_e_recusada() -> None:
    amostra = AmostraDeDepartamento(Departamento.FISCAL, ("x",), matriz=((1.0,),), horas=(1.0,))
    with pytest.raises(ValorInvalido):
        EstimadorHuber().estimar(amostra)


def test_intervalos_e_r2(amostras: dict[Departamento, AmostraDeDepartamento]) -> None:
    resultado = EstimadorHuber().estimar(amostras[Departamento.CONTABIL])
    baixo, alto = resultado.intervalos["beta0_horas"]
    assert baixo <= resultado.equacao.beta0_horas <= alto
    baixo, alto = resultado.intervalos["lancamentos_manuais"]
    assert baixo <= resultado.equacao.inclinacoes_minutos["lancamentos_manuais"] <= alto
    assert 0 < resultado.r2 < 1


def test_direcionador_sem_variacao_fica_nao_identificado() -> None:
    import warnings

    amostra = AmostraDeDepartamento(
        Departamento.FOLHA,
        ("empregados", "admissoes"),
        matriz=tuple((float(i % 7), 0.0) for i in range(30)),
        horas=tuple(0.05 + (i % 7) * 0.3 + ((i * 37) % 11 - 5) * 0.01 for i in range(30)),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        resultado = EstimadorHuber().estimar(amostra)
    assert resultado.nao_identificadas == ("admissoes",)
    assert resultado.equacao.inclinacoes_minutos["admissoes"] == Decimal(0)
    assert resultado.equacao.inclinacoes_minutos["empregados"] > 0
