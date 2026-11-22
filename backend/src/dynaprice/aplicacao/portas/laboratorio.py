"""Portas do laboratório: a análise (implementada em dominio/estimacao) e a saída do relatório.

A aplicação não importa os estimadores (contrato E2): recebe a análise por esta porta,
ligada no Composition Root.
"""

from typing import Protocol, runtime_checkable

from dynaprice.dominio.modelos import Carteira, Competencia, Relatorio


@runtime_checkable
class AnalisadorDeCarteira(Protocol):
    def analisar(self, carteira: Carteira, referencia: Competencia) -> Relatorio: ...


@runtime_checkable
class EscritorDeRelatorio(Protocol):
    def escrever(self, relatorio: Relatorio) -> None: ...
