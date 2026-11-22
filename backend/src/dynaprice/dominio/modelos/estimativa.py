"""Resultado da estimação anual: rascunho de política e portão de aceite (F1.30)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EstimativaDePolitica:
    documento: Mapping[str, Any]
    portao_aceite: bool
    relatorio: Mapping[str, Any]
