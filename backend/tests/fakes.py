"""Dublês das portas, compartilhados entre os testes."""

from datetime import UTC, datetime, timedelta

from dynaprice.dominio.modelos import Competencia


class RelogioFixo:
    """p_clock nos testes: o tempo só anda quando o teste manda."""

    def __init__(self, instante: datetime = datetime(2027, 2, 10, 12, 0, tzinfo=UTC)) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante

    def competencia_atual(self) -> Competencia:
        return Competencia(self.instante.year, self.instante.month)

    def dia_do_mes(self) -> int:
        return self.instante.day

    def avancar(self, segundos: float) -> None:
        self.instante += timedelta(seconds=segundos)
