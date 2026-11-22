"""Seções dos modelos: equações de tempo (Huber) e modelo de esforço (Ridge)."""

from collections import defaultdict

import numpy as np

from dynaprice.dominio.estimacao.diagnostico.contexto import Contexto
from dynaprice.dominio.estimacao.diagnostico.formato import br, pct
from dynaprice.dominio.estimacao.huber import EquacaoEstimada
from dynaprice.dominio.modelos import Item, Regime, Secao, Tabela


def _linhas(e: EquacaoEstimada) -> list[tuple[str, ...]]:
    departamento = e.equacao.departamento.value
    valores = {"beta0_horas": e.equacao.beta0_horas, **e.equacao.inclinacoes_minutos}
    valores = {n: v for n, v in valores.items() if n in e.intervalos}
    unidade = {"beta0_horas": "h"}
    return [
        (
            departamento,
            nome,
            br(v, 4),
            unidade.get(nome, "min"),
            br(e.intervalos[nome][0], 4),
            br(e.intervalos[nome][1], 4),
        )
        for nome, v in valores.items()
    ]


def secao_equacoes(contexto: Contexto) -> Secao:
    linhas = tuple(linha for e in contexto.equacoes for linha in _linhas(e))
    fonte = "Huber (RLM, c = 1,345) por empresa-mês; IC 95% (seções 5.8–5.9)"
    tabela = Tabela(
        "β estimados",
        ("departamento", "β", "valor", "unidade", "IC 2,5%", "IC 97,5%"),
        linhas,
        fonte,
    )
    itens = []
    for e in contexto.equacoes:
        nome = e.equacao.departamento.value
        itens.append(Item(f"R² {nome}", br(e.r2, 3), f"{fonte}; n = {e.observacoes}"))
        itens.append(
            Item(f"Atenuados pelo Huber ({nome})", pct(e.fracao_atenuada), "pesos < 1 (seção 9.8)")
        )
        if e.nao_identificadas:
            itens.append(
                Item(
                    f"Sem variação na amostra ({nome})",
                    ", ".join(e.nao_identificadas),
                    "β não identificado: 0",
                )
            )
        if e.truncadas:
            itens.append(
                Item(
                    f"Inclinações truncadas em 0 ({nome})",
                    ", ".join(e.truncadas),
                    "β < 0 sem sentido operacional",
                )
            )
    return Secao("Equações de tempo (Huber)", tuple(itens), (tabela,))


def _regime(linha: tuple[float, ...], nomes: tuple[str, ...]) -> Regime:
    for regime in (Regime.SN, Regime.LP, Regime.LR):
        if linha[nomes.index(f"regime_{regime}")] == 1.0:
            return regime
    return Regime.MEI


def secao_ridge(contexto: Contexto) -> Secao:
    modelo, amostra = contexto.ridge, contexto.esforco
    residuos = np.asarray(amostra.y) - modelo.prever(np.asarray(amostra.matriz))
    por_regime: dict[Regime, list[float]] = defaultdict(list)
    for linha, residuo in zip(amostra.matriz, residuos, strict=True):
        por_regime[_regime(linha, amostra.nomes)].append(float(residuo))
    fonte = "Ridge log-log com CV de 5 partes (seções 5.10–5.11); controle, fora do preço (E2)"
    linhas = tuple(
        (r.value, str(len(v)), br(float(np.mean(v)), 3)) for r, v in sorted(por_regime.items())
    )
    tabela = Tabela(
        "Resíduo médio de ln H por regime", ("regime", "empresas", "resíduo"), linhas, fonte
    )
    return Secao(
        "Modelo de esforço (Ridge)",
        (
            Item("λ escolhido", br(modelo.lam, 4), fonte),
            Item("Graus de liberdade efetivos", br(modelo.graus_de_liberdade, 2), "Eq. (45)"),
            Item("R² no ajuste", br(modelo.r2, 3), fonte),
            Item("R² em validação cruzada", br(modelo.r2_validacao, 3), f"{fonte}; artigo ≈ 0,77"),
        ),
        (tabela,),
    )
