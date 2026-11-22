"""Seções da política: pisos (D2), tarifa (D3), sensibilidade de θ e δ (D4) e s²/v²."""

from dataclasses import replace
from decimal import Decimal

from dynaprice.dominio.estimacao.diagnostico.calibracao import Calibracao, observacoes
from dynaprice.dominio.estimacao.diagnostico.contexto import Contexto
from dynaprice.dominio.estimacao.diagnostico.formato import br, pct
from dynaprice.dominio.estimacao.entrada_simulacao import contratos_da_carteira
from dynaprice.dominio.estimacao.simulador import SimuladorDePolitica
from dynaprice.dominio.modelos import Item, Regime, Secao, Tabela
from dynaprice.dominio.precificacao import NucleoDePreco, fator_de_credibilidade

GRADE = (Decimal("0.10"), Decimal("0.15"), Decimal("0.20"))


def secao_pisos(contexto: Contexto, cal: Calibracao) -> Secao:
    beta0 = sum((e.equacao.beta0_horas for e in contexto.equacoes), Decimal(0))
    referencia = cal.tau_chapeu * beta0
    linhas = []
    for regime in Regime:
        n = sum(c.completo and c.agregado.regime is regime for c in contexto.contratos)
        piso = cal.pisos[regime]
        situacao = (
            "nunca vinculante (abaixo de τ̂·Σβ0)" if piso <= referencia else "acima da referência"
        )
        if regime in cal.pisos_sem_dados:
            situacao = "sem contratos: P10 da carteira toda"
        linhas.append((regime.value, str(n), br(piso), br(referencia), situacao))
    fonte = "D2 (a): P10 do honorário vigente dos contratos com 12 meses; D2-REF: τ̂·Σβ0 (seção 6.6)"
    colunas = ("regime", "contratos", "π_r proposto", "τ̂·Σβ0", "situação")
    return Secao(
        "Pisos propostos por regime (D2)", tabelas=(Tabela("Pisos", colunas, tuple(linhas), fonte),)
    )


def secao_tarifa(contexto: Contexto, cal: Calibracao) -> Secao:
    obs = observacoes(contexto)
    hpad = sum(float(o.horas_padrao.valor) for o in obs)
    horas = sum(c.horas_registradas for c in contexto.contratos if c.completo)
    itens = [
        Item(
            "τ̂ (preço revelado)",
            br(cal.tau_chapeu),
            "Eq. (65): ΣF/ΣH_pad nos contratos com 12 meses (D3)",
        ),
        Item("ϱ (horas-padrão / registradas)", br(hpad / horas, 3), "seção 6.4; artigo ≈ 0,85"),
    ]
    if cal.tau_estrela is None:
        itens.append(Item("τ* (receita constante)", "sem solução", "Prop. 4: Σκπ ≥ R0"))
    else:
        itens.append(
            Item(
                "τ* (receita constante)",
                br(cal.tau_estrela),
                "Eq. (67), Prop. 5; referência apenas",
            )
        )
        itens.append(Item("τ̂ / τ*", br(cal.tau_chapeu / cal.tau_estrela, 3), "Prop. 7: ≥ 1"))
    return Secao("Tarifa (D3)", tuple(itens))


def _linha(contexto: Contexto, cal: Calibracao, theta: Decimal, delta: Decimal) -> tuple[str, ...]:
    politica = replace(cal.politica, teto_real_theta=theta, gatilho_delta=delta)
    entrada = contratos_da_carteira(contexto.carteira, politica, contexto.referencia).contratos
    r = SimuladorDePolitica(NucleoDePreco.da_politica(politica)).simular(entrada)
    return (
        pct(theta, 0),
        pct(delta, 0),
        br(r.receita_ciclo_1 / r.receita_vigente, 3),
        br(r.receita_alvo / r.receita_vigente, 3),
        pct(r.fracao_no_teto),
        pct(r.fracao_gatilho),
        br(r.ciclos_mediana, 1),
        str(r.ciclos_maximo),
    )


def secao_sensibilidade(contexto: Contexto, cal: Calibracao) -> Secao:
    linhas = tuple(_linha(contexto, cal, t, d) for t in GRADE for d in GRADE)
    colunas = (
        "θ",
        "δ",
        "R1/R0",
        "R*/R0",
        "no teto",
        "com gatilho",
        "ciclos (mediana)",
        "ciclos (máx.)",
    )
    fonte = "m_sim sobre o rascunho de política (Eq. 70; seções 6.7–6.8); D4 propõe θ = δ = 15%"
    return Secao(
        "Sensibilidade de θ e δ (D4)", tabelas=(Tabela("Grade θ × δ", colunas, linhas, fonte),)
    )


def secao_credibilidade(cal: Calibracao) -> Secao:
    fonte = "s² mensal dentro do contrato / v² contra o piso do regime (Eq. 55–56; ADR-004)"
    itens = [Item("s²/v²", br(cal.razao_s2_v2, 4), fonte)]
    itens += [
        Item(f"Z com {m} meses", br(fator_de_credibilidade(m, cal.razao_s2_v2), 3), "Eq. (56)")
        for m in (1, 6, 11)
    ]
    return Secao("Credibilidade s²/v²", tuple(itens))
