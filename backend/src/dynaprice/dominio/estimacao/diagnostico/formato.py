"""Formatação pt-BR dos números do relatório."""

from decimal import Decimal


def br(valor: float | Decimal, casas: int = 2) -> str:
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(fracao: float | Decimal, casas: int = 1) -> str:
    return f"{br(float(fracao) * 100, casas)}%"
