"""Porta p_clock: o tempo é uma dependência, fixa nos testes."""

from datetime import datetime
from typing import Protocol

from dynaprice.dominio.modelos import Competencia


class Relogio(Protocol):
    def agora(self) -> datetime:
        """Instante atual em UTC."""
        ...

    def competencia_atual(self) -> Competencia:
        """Competência corrente no fuso do negócio (America/Sao_Paulo)."""
        ...

    def dia_do_mes(self) -> int:
        """Dia corrente no fuso do negócio."""
        ...
