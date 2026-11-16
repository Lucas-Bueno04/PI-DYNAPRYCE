"""Porta p_src: de onde vem a carteira (Domínio, Omie, planilha ou gerador sintético)."""

from typing import Protocol, runtime_checkable

from dynaprice.dominio.modelos import Carteira, Competencia


@runtime_checkable
class FonteDeCarteira(Protocol):
    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        """Retrato da carteira com os fatos mensais de [inicio, fim], ambos inclusive."""
        ...


@runtime_checkable
class EscritorDeCarteira(Protocol):
    def escrever(self, carteira: Carteira) -> None:
        """Persiste o retrato da carteira (arquivo, banco...)."""
        ...
