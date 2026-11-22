"""Segmentação principal declarada = regime tributário (ADR-004 item 1)."""

from enum import StrEnum


class Regime(StrEnum):
    MEI = "MEI"
    SN = "SN"
    LP = "LP"
    LR = "LR"


class Departamento(StrEnum):
    """Departamentos m das equações de tempo (Eq. 36; Tabela 7)."""

    FISCAL = "fiscal"
    CONTABIL = "contabil"
    FOLHA = "folha"
