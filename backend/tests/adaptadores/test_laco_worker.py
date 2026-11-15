"""in_worker: heartbeat real enquanto o job roda e tolerância a lease perdido."""

import threading
from uuid import uuid4

from dynaprice.adaptadores.entrada.worker import LacoDoWorker
from dynaprice.aplicacao.portas import JobReservado, LeasePerdido
from tests.fakes import RelogioFixo

JOB = JobReservado(uuid4(), uuid4(), "extrair", {}, 1)


class FilaDeTeste:
    intervalo_de_heartbeat = 0.01
    intervalo_de_varredura = 60.0

    def __init__(self, *, perder_lease: bool = False) -> None:
        self.pendente: JobReservado | None = JOB
        self.batimentos = threading.Semaphore(0)
        self.concluidos = 0
        self.falhas: list[tuple[str, bool]] = []
        self.varreduras = 0
        self.perder_lease = perder_lease

    def reservar(self) -> JobReservado | None:
        job, self.pendente = self.pendente, None
        return job

    def heartbeat(self, job: JobReservado) -> None:
        self.batimentos.release()

    def concluir(self, job: JobReservado) -> None:
        if self.perder_lease:
            raise LeasePerdido("outro worker assumiu")
        self.concluidos += 1

    def falhar(self, job: JobReservado, erro: str, *, permanente: bool) -> None:
        self.falhas.append((erro, permanente))

    def recuperar_orfaos(self) -> int:
        self.varreduras += 1
        return 0


def test_heartbeat_bate_enquanto_o_job_roda() -> None:
    fila = FilaDeTeste()
    bateu: list[bool] = []
    laco = LacoDoWorker(
        fila, {"extrair": lambda _: bateu.append(fila.batimentos.acquire(timeout=5))}, RelogioFixo()
    )
    assert laco.executar_um() is True
    assert bateu == [True]
    assert fila.concluidos == 1


def test_lease_perdido_nao_derruba_o_laco() -> None:
    fila = FilaDeTeste(perder_lease=True)
    assert LacoDoWorker(fila, {"extrair": lambda _: None}, RelogioFixo()).executar_um() is True


def test_erro_inesperado_reagenda_sem_vazar_a_mensagem() -> None:
    def explode(_: JobReservado) -> None:
        raise ValueError("cpf 000.000.000-00")

    fila = FilaDeTeste()
    LacoDoWorker(fila, {"extrair": explode}, RelogioFixo()).executar_um()
    assert fila.falhas == [("ValueError", False)]


def test_varredura_respeita_o_intervalo() -> None:
    fila = FilaDeTeste()
    relogio = RelogioFixo()
    laco = LacoDoWorker(fila, {}, relogio)
    laco.executar_um()
    laco.executar_um()
    assert fila.varreduras == 1
    relogio.avancar(61)
    laco.executar_um()
    assert fila.varreduras == 2
