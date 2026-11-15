"""Porta p_job: contrato da fila de jobs (lease, tentativas e idempotência)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class ErroTransitorio(Exception):
    """Falha que pode passar sozinha: o job volta à fila com backoff."""


class ErroPermanente(Exception):
    """Falha que não adianta repetir (ex.: credencial recusada): o job vai direto a falhou."""


class ConectorIndisponivel(ErroTransitorio):
    """A fonte não respondeu (tempo esgotado, rede, limite de taxa)."""


class CredencialInvalida(ErroPermanente):
    """A fonte recusou a credencial: repetir só arrisca bloquear o usuário."""


class ErroDeExportacao(Exception):
    """Falha ao gerar ou entregar o arquivo de exportação."""


class LeasePerdido(Exception):
    """O job já não pertence a este worker: o lease venceu e outro assumiu."""


@dataclass(frozen=True, slots=True)
class JobReservado:
    id: UUID
    tenant_id: UUID
    tipo: str
    parametros: Mapping[str, Any]
    tentativas: int


class AgendaDeJobs(Protocol):
    """Lado produtor: entra na mesma transação da mudança que originou o job."""

    def enfileirar(
        self, tipo: str, chave: str, parametros: Mapping[str, Any], quando: datetime
    ) -> bool:
        """Grava o job; devolve False se a chave de idempotência já existia."""
        ...

    def reabrir(self, chave: str, quando: datetime) -> None:
        """Nova tentativa manual de um job que falhou."""
        ...


class ConsumidorDeJobs(Protocol):
    """Lado consumidor, usado pelo worker."""

    def reservar(self) -> JobReservado | None: ...

    def heartbeat(self, job: JobReservado) -> None: ...

    def concluir(self, job: JobReservado) -> None: ...

    def falhar(self, job: JobReservado, erro: str, *, permanente: bool) -> None: ...

    def recuperar_orfaos(self) -> int: ...

    @property
    def intervalo_de_heartbeat(self) -> float: ...

    @property
    def intervalo_de_varredura(self) -> float: ...
