"""Competência mensal (ano, mês) dos direcionadores e honorários."""

from __future__ import annotations

from dataclasses import dataclass

from dynaprice.dominio.modelos.erros import ValorInvalido


@dataclass(frozen=True, slots=True, order=True)
class Competencia:
    ano: int
    mes: int

    def __post_init__(self) -> None:
        if not 1 <= self.mes <= 12:
            raise ValorInvalido(f"mês inválido: {self.mes}")
        if self.ano < 1900:
            raise ValorInvalido(f"ano inválido: {self.ano}")

    @classmethod
    def de_texto(cls, texto: str) -> Competencia:
        ano, _, mes = texto.partition("-")
        try:
            return cls(int(ano), int(mes))
        except ValueError as erro:
            raise ValorInvalido(f"competência inválida: {texto!r}") from erro

    def _indice(self) -> int:
        return self.ano * 12 + self.mes - 1

    @classmethod
    def _do_indice(cls, indice: int) -> Competencia:
        return cls(indice // 12, indice % 12 + 1)

    def proxima(self) -> Competencia:
        return self._do_indice(self._indice() + 1)

    def anterior(self) -> Competencia:
        return self._do_indice(self._indice() - 1)

    def somar(self, meses: int) -> Competencia:
        return self._do_indice(self._indice() + meses)

    def meses_ate(self, outra: Competencia) -> int:
        return outra._indice() - self._indice()

    def __str__(self) -> str:
        return f"{self.ano:04d}-{self.mes:02d}"
