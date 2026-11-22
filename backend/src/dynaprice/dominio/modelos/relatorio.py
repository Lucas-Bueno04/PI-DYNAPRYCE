"""Documento de relatório do laboratório: seções com itens e tabelas, cada um com a fonte."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from dynaprice.dominio.modelos.erros import ValorInvalido


@dataclass(frozen=True, slots=True)
class Item:
    rotulo: str
    valor: str
    fonte: str  # equação, seção do artigo, decisão ou dado de onde o número vem


@dataclass(frozen=True, slots=True)
class Tabela:
    titulo: str
    colunas: tuple[str, ...]
    linhas: tuple[tuple[str, ...], ...]
    fonte: str


@dataclass(frozen=True, slots=True)
class Secao:
    titulo: str
    itens: tuple[Item, ...] = ()
    tabelas: tuple[Tabela, ...] = ()


@dataclass(frozen=True, slots=True)
class Relatorio:
    titulo: str
    secoes: tuple[Secao, ...]
    anexos: Mapping[str, str] = field(default_factory=dict)  # nome do arquivo → conteúdo

    def __post_init__(self) -> None:
        object.__setattr__(self, "anexos", MappingProxyType(dict(self.anexos)))

    def secao(self, titulo: str) -> Secao:
        for secao in self.secoes:
            if secao.titulo == titulo:
                return secao
        raise ValorInvalido(f"relatório sem a seção '{titulo}'")
