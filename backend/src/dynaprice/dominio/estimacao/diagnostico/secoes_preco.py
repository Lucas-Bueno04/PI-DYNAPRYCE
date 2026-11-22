"""Seções descritivas: carteira, curva preço × esforço, concentração e desalinhamento."""

from collections import Counter

import numpy as np

from dynaprice.dominio.estimacao.diagnostico.contexto import Contexto, ContratoAnalisado
from dynaprice.dominio.estimacao.diagnostico.formato import br, pct
from dynaprice.dominio.estimacao.diagnostico.medidas import gini, indices_de_alinhamento, regra_afim
from dynaprice.dominio.modelos import Item, Secao, Tabela


def _completos(contexto: Contexto) -> list[ContratoAnalisado]:
    return [c for c in contexto.contratos if c.completo and c.horas_registradas > 0]


def secao_carteira(contexto: Contexto) -> Secao:
    fonte = "k_agr: vínculos vigentes na competência de referência (ADR-003)"
    pendencias = Counter(p.motivo.value for p in contexto.agregacao.pendencias)
    itens = [
        Item("Competência de referência", str(contexto.referencia), "parâmetro da análise"),
        Item("Contratos agregados", str(len(contexto.contratos)), fonte),
        Item(
            "Com 12 meses (ℓ = 2)",
            str(sum(c.completo for c in contexto.contratos)),
            "Eq. (4); ADR-004",
        ),
        Item("Empresas", str(len(contexto.carteira.empresas)), "fonte de dados"),
    ]
    itens += [Item(f"Pendências: {m}", str(n), fonte) for m, n in sorted(pendencias.items())]
    return Secao("Carteira", tuple(itens))


def secao_curva(contexto: Contexto) -> Secao:
    c = _completos(contexto)
    horas, precos = [x.horas_registradas for x in c], [x.honorario for x in c]
    a, b, r2 = regra_afim(horas, precos)
    elasticidade = float(np.polyfit(np.log(horas), np.log(precos), 1)[0])
    fonte = "MQO do honorário vigente sobre as horas registradas, contratos com 12 meses"
    return Secao(
        "Curva preço × esforço",
        (
            Item("a", br(a), f"{fonte} (Eq. 12; seção 9.4: a ≈ 213)"),
            Item("b", br(b), f"{fonte} (seção 9.4: b ≈ 32)"),
            Item("R² da regra afim", br(r2, 3), fonte),
            Item("Elasticidade preço × horas", br(elasticidade, 3), "ln F sobre ln H (seção 5.1)"),
            Item("P̄ (receita por hora registrada)", br(sum(precos) / sum(horas)), "Eq. (27)"),
        ),
    )


def _lorenz(c: list[ContratoAnalisado]) -> Tabela:
    ordem = sorted(c, key=lambda x: x.horas_registradas)
    horas = np.cumsum([x.horas_registradas for x in ordem]) / sum(
        x.horas_registradas for x in ordem
    )
    precos = np.cumsum([x.honorario for x in ordem]) / sum(x.honorario for x in ordem)
    linhas = []
    for decil in range(1, 11):
        i = max(0, round(decil * len(ordem) / 10) - 1)
        linhas.append((f"{decil * 10}%", pct(horas[i]), pct(precos[i])))
    fonte = "curva de Lorenz dos contratos ordenados por horas (seção 5.5)"
    return Tabela(
        "Lorenz: fração acumulada", ("contratos", "horas", "honorários"), tuple(linhas), fonte
    )


def secao_concentracao(contexto: Contexto) -> Secao:
    c = _completos(contexto)
    hpad = [float(x.agregado.horas_padrao.total.valor) for x in c]
    fonte = "coeficiente de Gini (seção 5.5); artigo: horas 0,65, honorário 0,51"
    return Secao(
        "Concentração (Lorenz e Gini)",
        (
            Item(
                "Gini das horas registradas", br(gini([x.horas_registradas for x in c]), 3), fonte
            ),
            Item("Gini das horas-padrão", br(gini(hpad), 3), fonte),
            Item("Gini dos honorários", br(gini([x.honorario for x in c]), 3), fonte),
        ),
        (_lorenz(c),),
    )


def secao_desalinhamento(contexto: Contexto) -> Secao:
    c = _completos(contexto)
    indices = np.asarray(
        indices_de_alinhamento([x.honorario for x in c], [x.horas_registradas for x in c])
    )
    q1, q3 = np.quantile(indices, [0.25, 0.75])
    fonte = "I_i = (F_i/ΣF)/(H_i/ΣH) (seção 5.6); artigo: quartis 0,76 e 2,74"
    return Secao(
        "Desalinhamento entre preço e esforço",
        (
            Item("1º quartil de I", br(q1, 2), fonte),
            Item("3º quartil de I", br(q3, 2), fonte),
            Item("Pagam menos de 2/3 do esforço (I < 0,67)", pct(np.mean(indices < 2 / 3)), fonte),
            Item("Pagam mais de 1,5x o esforço (I > 1,5)", pct(np.mean(indices > 1.5)), fonte),
        ),
    )
