"""Laço do worker: executa um job por vez, com heartbeat e mapeamento de erros."""

import logging
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime

from dynaprice.aplicacao.portas import (
    ConsumidorDeJobs,
    ErroPermanente,
    ErroTransitorio,
    JobReservado,
    LeasePerdido,
    Relogio,
)

type Manipulador = Callable[[JobReservado], None]

_log = logging.getLogger(__name__)
_ESPERA_SEM_JOB_S = 5.0


class LacoDoWorker:
    def __init__(
        self,
        fila: ConsumidorDeJobs,
        manipuladores: Mapping[str, Manipulador],
        relogio: Relogio,
    ) -> None:
        self._fila = fila
        self._manipuladores = manipuladores
        self._relogio = relogio
        self._ultima_varredura: datetime | None = None

    def executar_um(self) -> bool:
        """Processa o próximo job; devolve False se não havia job disponível."""
        self._varrer_orfaos()
        job = self._fila.reservar()
        if job is None:
            return False
        manipulador = self._manipuladores.get(job.tipo)
        try:
            if manipulador is None:
                self._fila.falhar(job, f"tipo de job desconhecido: {job.tipo}", permanente=True)
            else:
                self._executar(job, manipulador)
        except LeasePerdido:
            _log.warning("lease perdido", extra={"job": str(job.id)})
        return True

    def _executar(self, job: JobReservado, manipulador: Manipulador) -> None:
        inicio = time.monotonic()
        try:
            with self._batimento(job):
                manipulador(job)
        except ErroPermanente as erro:
            self._fila.falhar(job, str(erro), permanente=True)
        except ErroTransitorio as erro:
            self._fila.falhar(job, str(erro), permanente=False)
        except Exception as erro:  # a fila não pode morrer por um job: registra e reagenda
            _log.exception("falha inesperada", extra={"job": str(job.id)})
            self._fila.falhar(job, type(erro).__name__, permanente=False)
        else:
            self._fila.concluir(job)
            _log.info(
                "job_concluido",
                extra={"tipo": job.tipo, "duracao_s": round(time.monotonic() - inicio, 3)},
            )

    def _varrer_orfaos(self) -> None:
        agora = self._relogio.agora()
        ultima = self._ultima_varredura
        if ultima is None or (agora - ultima).total_seconds() >= self._fila.intervalo_de_varredura:
            self._fila.recuperar_orfaos()
            self._ultima_varredura = agora

    @contextmanager
    def _batimento(self, job: JobReservado) -> Iterator[None]:
        parar = threading.Event()
        linha = threading.Thread(target=self._bater, args=(job, parar), daemon=True)
        linha.start()
        try:
            yield
        finally:
            parar.set()
            linha.join()

    def _bater(self, job: JobReservado, parar: threading.Event) -> None:
        while not parar.wait(self._fila.intervalo_de_heartbeat):
            try:
                self._fila.heartbeat(job)
            except LeasePerdido:
                _log.warning("lease perdido no heartbeat", extra={"job": str(job.id)})
                return

    def rodar(
        self,
        parar: threading.Event,
        aguardar: Callable[[float], object],
        agendar: Callable[[], None],
        intervalo_de_agenda_s: float,
    ) -> None:
        """Laço principal: agenda o que venceu e consome a fila até receber o sinal de parada."""
        ultima_agenda: datetime | None = None
        while not parar.is_set():
            agora = self._relogio.agora()
            if ultima_agenda is None or (
                (agora - ultima_agenda).total_seconds() >= intervalo_de_agenda_s
            ):
                agendar()
                ultima_agenda = agora
            if not self.executar_um():
                aguardar(_ESPERA_SEM_JOB_S)
