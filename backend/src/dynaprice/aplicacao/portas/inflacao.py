"""Portas do índice de inflação: fonte externa (BCB) e gravação no índice global."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.indice import VariacaoDeIndice


class FonteDeInflacao(Protocol):
    def variacoes(self, inicio: Competencia, fim: Competencia) -> Sequence[VariacaoDeIndice]:
        """Falha com ConectorIndisponivel; devolve só os meses publicados dentro do intervalo."""
        ...


@dataclass(frozen=True, slots=True)
class Divergencia:
    competencia: Competencia
    gravado: Decimal
    da_fonte: Decimal


class RepositorioDeIndices(Protocol):
    def gravar_se_ausente(self, variacao: VariacaoDeIndice, registrado_por: str) -> Decimal | None:
        """None se gravou; senão, o valor que já existia (nunca sobrescreve)."""
        ...
