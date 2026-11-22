"""Documento declarativo de política (Quadro 7) montado a partir das estimativas do laboratório."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from dynaprice.dominio.modelos import EquacaoDeTempo, Regime

THETA_INICIAL = Decimal("0.15")  # D4
DELTA_INICIAL = Decimal("0.15")  # D4
DIAS_DE_FECHAMENTO = 5  # D10
ANTECEDENCIA_MESES = 2  # D7


def _equacao(e: EquacaoDeTempo) -> dict[str, Any]:
    return {
        "departamento": e.departamento.value,
        "beta0_horas": str(e.beta0_horas),
        "inclinacoes_minutos": {k: str(v) for k, v in e.inclinacoes_minutos.items()},
    }


def documento_de_politica(
    equacoes: Sequence[EquacaoDeTempo],
    pisos: Mapping[Regime, Decimal],
    tarifa: Decimal,
    razao_s2_v2: Decimal,
) -> dict[str, Any]:
    return {
        "versao": 1,
        "piso_por_segmento": {r.value: str(pisos[r]) for r in Regime},
        "tarifa_hora_padrao": {"valor": str(tarifa), "origem": "preco_revelado"},
        "kappa_maximo": "1.2",
        "reajuste": {
            "teto_real_por_ciclo": str(THETA_INICIAL),
            "antecedencia_meses": ANTECEDENCIA_MESES,
        },
        "gatilho_revisao": str(DELTA_INICIAL),
        "informacao_incompleta": {"sem_historico": "piso_regime", "razao_s2_v2": str(razao_s2_v2)},
        "fechamento_dias": DIAS_DE_FECHAMENTO,
        "equacoes_de_tempo": [_equacao(e) for e in equacoes],
    }
