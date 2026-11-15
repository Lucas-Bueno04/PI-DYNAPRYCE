"""Adaptador a_clock: UTC para gravar, America/Sao_Paulo para a competência."""

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from dynaprice.dominio.modelos import Competencia

FUSO_DO_NEGOCIO = ZoneInfo("America/Sao_Paulo")


class RelogioDoSistema:
    def __init__(self, fonte: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._fonte = fonte

    def agora(self) -> datetime:
        return self._fonte().astimezone(UTC)

    def competencia_atual(self) -> Competencia:
        local = self._fonte().astimezone(FUSO_DO_NEGOCIO)
        return Competencia(local.year, local.month)

    def dia_do_mes(self) -> int:
        return self._fonte().astimezone(FUSO_DO_NEGOCIO).day
