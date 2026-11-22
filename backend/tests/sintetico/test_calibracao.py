"""F0.6: a carteira sintética cai nas faixas da seção 9 do artigo (validação pela forma).

As tolerâncias são largas de propósito: amostra finita com semente; o que se confere são
ordens de grandeza, sinais e razões (docs/lab/calibracao_sintetica.md).
"""

from collections import defaultdict
from decimal import Decimal
from statistics import median

import pytest

from dynaprice.adaptadores.saida.sintetico import EQUACOES_VERDADEIRAS
from dynaprice.dominio.modelos import Carteira, Departamento


def _horas_medias_por_empresa(carteira: Carteira) -> dict[str, float]:
    soma: dict[str, Decimal] = defaultdict(Decimal)
    meses: dict[str, set[object]] = defaultdict(set)
    for h in carteira.horas:
        soma[h.empresa_id] += h.horas.valor
        meses[h.empresa_id].add(h.competencia)
    return {e: float(soma[e]) / len(meses[e]) for e in soma}


def _hpad_medio_por_empresa(carteira: Carteira) -> dict[str, float]:
    soma: dict[str, float] = defaultdict(float)
    meses: dict[str, int] = defaultdict(int)
    atende = {e.id: e.departamentos for e in carteira.empresas}
    for d in carteira.direcionadores:
        for eq in EQUACOES_VERDADEIRAS:
            if eq.departamento not in atende[d.empresa_id]:
                continue
            minutos = sum(float(b * d.valor(k)) for k, b in eq.inclinacoes_minutos.items())
            soma[d.empresa_id] += float(eq.beta0_horas) + minutos / 60
        meses[d.empresa_id] += 1
    return {e: soma[e] / meses[e] for e in soma}


def _honorario_por_contrato(carteira: Carteira) -> dict[str, float]:
    ultimo = {}
    for h in sorted(carteira.honorarios, key=lambda h: h.competencia):
        ultimo[h.contrato_id] = float(h.valor.valor)
    return ultimo


def _horas_por_contrato(carteira: Carteira) -> dict[str, float]:
    horas = _horas_medias_por_empresa(carteira)
    total: dict[str, float] = defaultdict(float)
    for v in carteira.vinculos:
        total[v.contrato_id] += horas.get(v.empresa_id, 0.0)
    return total


# O "cliente" do artigo é a unidade com honorário: o contrato (ADR-003).


def test_horas_medianas_por_contrato(carteira: Carteira) -> None:
    assert 1.8 <= median(_horas_por_contrato(carteira).values()) <= 3.5  # artigo: ~2,5 h


def test_receita_por_hora_registrada(carteira: Carteira) -> None:
    honorario = _honorario_por_contrato(carteira)
    horas = _horas_por_contrato(carteira)
    assert 70 <= sum(honorario.values()) / sum(horas[c] for c in honorario) <= 110  # P̄ ≈ 88


def test_empresas_sem_honorario_proprio_tem_pouca_hora(carteira: Carteira) -> None:
    horas = _horas_medias_por_empresa(carteira)
    extras = {v.empresa_id for v in carteira.vinculos if not v.principal}
    assert 0.04 <= sum(horas[e] for e in extras) / sum(horas.values()) <= 0.20  # artigo: ~11%


def test_razao_decil_10_por_decil_1(carteira: Carteira) -> None:
    """Artigo: ~50 (0,4 h x 21,7 h). Com F = a + b·H, P̄ ≈ 88 exige média ~3,8 h, o que,
    sob o piso de β0 = 1,75 h, não convive com essa cauda; priorizam-se τ̂ e P̄ (entram no
    preço) e exige-se só uma cauda pesada (docs/lab/calibracao_sintetica.md)."""
    horas = sorted(_horas_por_contrato(carteira).values())
    decil = len(horas) // 10
    razao = median(horas[-decil:]) / median(horas[:decil])
    assert 6 <= razao <= 120


def test_participacao_dos_departamentos(carteira: Carteira) -> None:
    total: dict[Departamento, Decimal] = defaultdict(Decimal)
    for h in carteira.horas:
        total[h.departamento] += h.horas.valor
    soma = sum(total.values())
    fracao = {d: float(v / soma) for d, v in total.items()}
    assert 0.35 <= fracao[Departamento.CONTABIL] <= 0.60
    assert 0.20 <= fracao[Departamento.FISCAL] <= 0.42
    assert 0.08 <= fracao[Departamento.FOLHA] <= 0.30


def test_razao_horas_padrao_por_registradas(carteira: Carteira) -> None:
    hpad = _hpad_medio_por_empresa(carteira)
    horas = _horas_medias_por_empresa(carteira)
    rho = sum(hpad.values()) / sum(horas[e] for e in hpad)
    assert rho == pytest.approx(0.85, abs=0.07)


def test_regra_implicita_regressiva(carteira: Carteira) -> None:
    honorario = _honorario_por_contrato(carteira)
    horas = _horas_por_contrato(carteira)
    xs = [horas[c] for c in honorario]
    ys = [honorario[c] for c in honorario]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - mx) ** 2 for x in xs
    )
    a = my - b * mx
    assert 150 <= a <= 280  # artigo: a ≈ 213
    assert 20 <= b <= 45  # artigo: b ≈ 32


def test_honorario_mediano(carteira: Carteira) -> None:
    assert 250 <= median(_honorario_por_contrato(carteira).values()) <= 420


def test_tarifa_revelada_perto_de_103(carteira: Carteira) -> None:
    hpad = _hpad_medio_por_empresa(carteira)
    honorario = _honorario_por_contrato(carteira)
    hpad_contrato: dict[str, float] = defaultdict(float)
    for v in carteira.vinculos:
        hpad_contrato[v.contrato_id] += hpad.get(v.empresa_id, 0.0)
    tau = sum(honorario.values()) / sum(hpad_contrato[c] for c in honorario)
    assert 80 <= tau <= 130  # Eq. (65) e (97): τ̂ ≈ 103,5
