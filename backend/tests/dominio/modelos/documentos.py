"""Documento de política de referência: Quadro 7 adaptado a D4, D10, D11, D12 e ADR-004."""

from typing import Any


def documento_tabela_7() -> dict[str, Any]:
    return {
        "versao": 1,
        "piso_por_segmento": {"MEI": "80", "SN": "185", "LP": "235", "LR": "340"},
        "tarifa_hora_padrao": {"valor": "103.5", "origem": "preco_revelado"},
        "kappa_maximo": "1.2",
        "reajuste": {"teto_real_por_ciclo": "0.15", "antecedencia_meses": 2},
        "gatilho_revisao": "0.15",
        "informacao_incompleta": {"sem_historico": "piso_regime", "razao_s2_v2": "2"},
        "fechamento_dias": 5,
        "equacoes_de_tempo": [
            {
                "departamento": "fiscal",
                "beta0_horas": "0.91",
                "inclinacoes_minutos": {"notas_entrada": "3.75"},
            },
            {
                "departamento": "contabil",
                "beta0_horas": "0.79",
                "inclinacoes_minutos": {"lancamentos_manuais": "2.54"},
            },
            {
                "departamento": "folha",
                "beta0_horas": "0.05",
                "inclinacoes_minutos": {"empregados": "18.5"},
            },
        ],
    }
