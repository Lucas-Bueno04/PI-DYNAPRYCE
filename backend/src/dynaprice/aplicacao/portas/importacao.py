"""Portas de importação de arquivo e de estimação anual."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from dynaprice.dominio.modelos import Carteira, Competencia, EstimativaDePolitica, PoliticaVersao


@dataclass(frozen=True, slots=True)
class Rejeitada:
    arquivo: str
    linha: int
    motivo: str


@dataclass(frozen=True, slots=True)
class LeituraDeArquivo:
    carteira: Carteira
    rejeicoes: tuple[Rejeitada, ...]
    hash_conteudo: str


class LeitorDeArquivo(Protocol):
    def ler(
        self, nome: str, conteudo: bytes, inicio: Competencia, fim: Competencia
    ) -> LeituraDeArquivo: ...


class EstimadorDePolitica(Protocol):
    def estimar(
        self, carteira: Carteira, referencia: Competencia, vigente: PoliticaVersao | None
    ) -> EstimativaDePolitica: ...


class SimuladorDeRascunho(Protocol):
    def simular(
        self, carteira: Carteira, politica: PoliticaVersao, referencia: Competencia
    ) -> Mapping[str, Any]: ...
