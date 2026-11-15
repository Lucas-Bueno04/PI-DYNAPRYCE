"""Porta da âncora externa da auditoria (RNF06): fora do banco, só de acréscimo."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class ErroDeAncora(Exception):
    """O meio da âncora está ilegível ou foi adulterado."""


@dataclass(frozen=True, slots=True)
class Ancora:
    tenant_id: UUID
    seq: int
    hash_hex: str
    registrada_em: datetime


class AncoraExterna(Protocol):
    def registrar(self, ancora: Ancora) -> None: ...

    def listar(self, tenant_id: UUID) -> Sequence[Ancora]:
        """Em ordem de registro; levanta ErroDeAncora se o meio foi adulterado."""
        ...
