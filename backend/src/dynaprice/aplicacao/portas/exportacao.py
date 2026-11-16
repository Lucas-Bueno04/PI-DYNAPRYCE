"""Porta p_exp: formato do arquivo que chega ao financeiro."""

from collections.abc import Sequence
from typing import Protocol

from dynaprice.dominio.modelos.recomendacao import Recomendacao


class ExportadorDeRecomendacoes(Protocol):
    def gerar(self, recomendacoes: Sequence[Recomendacao]) -> bytes:
        """Conteúdo do arquivo; falha com ErroDeExportacao."""
        ...
