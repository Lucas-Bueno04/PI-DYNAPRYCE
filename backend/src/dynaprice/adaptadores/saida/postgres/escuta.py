"""LISTEN da publicação de política (D-RECARGA): invalida a memória; reconexão limpa tudo."""

from types import TracebackType
from typing import Self
from uuid import UUID

import psycopg

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.aplicacao.politica_em_memoria import PoliticaEmMemoria

_CANAL = "politica_publicada"


class EscutaDePoliticas:
    def __init__(self, url: str, memoria: PoliticaEmMemoria) -> None:
        self._url = url
        self._memoria = memoria
        self._conexao: Conexao | None = None
        self.reconexoes = 0

    def _conectar(self) -> None:
        self._conexao = psycopg.connect(self._url, autocommit=True)
        self._conexao.execute(f"LISTEN {_CANAL}")
        # Notificações enviadas enquanto não escutávamos estão perdidas.
        self._memoria.limpar()

    def __enter__(self) -> Self:
        self._conectar()
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastro: TracebackType | None,
    ) -> None:
        if self._conexao is not None:
            self._conexao.close()

    def processar(self, tempo_s: float) -> int:
        """Espera até `tempo_s` por uma notificação; devolve quantas tratou."""
        assert self._conexao is not None
        total = 0
        try:
            for aviso in self._conexao.notifies(timeout=tempo_s, stop_after=1):
                self._memoria.descartar(UUID(aviso.payload))
                total += 1
        except psycopg.OperationalError:
            self.reconexoes += 1
            self._conectar()
        return total


class EscutaDeJobs:
    """Acorda o worker quando entra job novo; sem notificação, o tempo limite faz a varredura."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._conexao: Conexao | None = None

    def __enter__(self) -> Self:
        self._conexao = psycopg.connect(self._url, autocommit=True)
        self._conexao.execute("LISTEN job_novo")
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastro: TracebackType | None,
    ) -> None:
        if self._conexao is not None:
            self._conexao.close()

    def aguardar(self, tempo_s: float) -> None:
        assert self._conexao is not None
        try:
            for _ in self._conexao.notifies(timeout=tempo_s, stop_after=1):
                pass
        except psycopg.OperationalError:
            self.__enter__()
