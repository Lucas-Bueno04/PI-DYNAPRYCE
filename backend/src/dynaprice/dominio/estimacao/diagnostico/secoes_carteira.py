"""Seções para validar com o escritório: contratos mistos (D1), regime (D13), fechamento (D10)."""

from dynaprice.dominio.estimacao.diagnostico.contexto import Contexto
from dynaprice.dominio.estimacao.diagnostico.rascunho import DIAS_DE_FECHAMENTO
from dynaprice.dominio.modelos import Item, Secao, Tabela

_LISTADOS = 20


def secao_mistos(contexto: Contexto) -> Secao:
    mistos = [c.agregado for c in contexto.contratos if c.agregado.misto]
    alertas = [m for m in mistos if m.alerta_segmento]
    fonte = (
        "k_agr: segmento = regime da empresa principal (D1 a); alerta se principal MEI/SN com LP/LR"
    )
    linhas = tuple(
        (
            m.contrato_id,
            m.regime.value,
            ", ".join(sorted(r.value for r in m.regimes)),
            "sim" if m.alerta_segmento else "",
        )
        for m in mistos[:_LISTADOS]
    )
    tabela = Tabela(
        f"Primeiros {_LISTADOS} contratos mistos",
        ("contrato", "segmento", "regimes", "alerta"),
        linhas,
        fonte,
    )
    itens = (
        Item("Contratos mistos", str(len(mistos)), fonte),
        Item("Com alerta de segmento", str(len(alertas)), fonte),
    )
    return Secao("Contratos mistos (D1)", itens, (tabela,))


def secao_mudanca_de_regime(contexto: Contexto) -> Secao:
    fonte = (
        "D13 (b): só os meses do regime novo; a medição exige histórico de regime da fonte (F0.22)"
    )
    return Secao(
        "Mudanças de regime na janela (D13)",
        (
            Item(
                "Contratos com mudança de regime",
                "não medido: a fonte não traz histórico de regime",
                fonte,
            ),
        ),
    )


def secao_fechamento(contexto: Contexto) -> Secao:
    return Secao(
        "Dias de fechamento (D10)",
        (
            Item("Parâmetro em uso", f"{DIAS_DE_FECHAMENTO} dias", "D10 (a)"),
            Item(
                "Medição", "não medido: a fonte não traz a data dos lançamentos", "medir em F0.22"
            ),
        ),
    )
