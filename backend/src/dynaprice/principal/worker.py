"""Composição do worker e das fontes de dados."""

import signal
import socket
import threading
from typing import Any

from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.entrada.api.logs import configurar_logs
from dynaprice.adaptadores.entrada.worker import LacoDoWorker
from dynaprice.adaptadores.saida.arquivos.exportador import ExportadorCsvDeRecomendacoes
from dynaprice.adaptadores.saida.postgres import (
    EscutaDeJobs,
    FabricaDeUnidadesPostgres,
    FilaPostgres,
    abrir_pool,
)
from dynaprice.adaptadores.saida.relogio import RelogioDoSistema
from dynaprice.adaptadores.saida.seguranca import CifradorAesGcm, carregar_chaves_mestras
from dynaprice.aplicacao.casos_de_uso.conciliar import Conciliar
from dynaprice.aplicacao.casos_de_uso.conectores import AgendarCiclo, ExtrairCompetencia
from dynaprice.aplicacao.casos_de_uso.estimar import EstimarPolitica
from dynaprice.aplicacao.casos_de_uso.exportar import ExecutarExportacao
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.aplicacao.casos_de_uso.retencao import AplicarRetencao
from dynaprice.aplicacao.portas import JobReservado
from dynaprice.dominio.estimacao.anual import EstimadorAnual
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.fila import ParametrosDeFila
from dynaprice.principal.comum import caminho_do_segredo, ler_segredo
from dynaprice.principal.fontes import fontes_de_dados

_INTERVALO_DE_AGENDA_S = 3600.0


def _competencia(job: JobReservado) -> Competencia:
    return Competencia.de_texto(str(job.parametros["competencia"]))


def _montar_laco(pool: ConnectionPool[Any]) -> tuple[LacoDoWorker, AgendarCiclo, FilaPostgres]:
    relogio = RelogioDoSistema()
    fabrica = FabricaDeUnidadesPostgres(pool, relogio)
    parametros = ParametrosDeFila()
    cifrador = CifradorAesGcm(
        carregar_chaves_mestras(caminho_do_segredo("DYNAPRICE_CHAVES_MESTRAS_FILE"))
    )
    chave = ler_segredo("DYNAPRICE_CHAVE_PSEUDONIMO_FILE").encode()
    fontes = fontes_de_dados(chave)
    recalibrar = Recalibrar(fabrica, relogio)
    conciliar = Conciliar(fabrica)
    retencao = AplicarRetencao(fabrica, relogio)
    manipuladores = {
        "extrair": ExtrairCompetencia(fabrica, relogio, cifrador, fontes).executar,
        "recalibrar": lambda job: _ignorar(recalibrar.executar(job.tenant_id, _competencia(job))),
        "conciliar": lambda job: _ignorar(conciliar.executar(job.tenant_id, _competencia(job))),
        "exportar": ExecutarExportacao(
            fabrica, relogio, ExportadorCsvDeRecomendacoes(), parametros.max_tentativas
        ).executar,
        "estimar_politica": EstimarPolitica(fabrica, EstimadorAnual()).executar,
        "retencao": lambda job: _ignorar(retencao.executar(job)),
    }
    fila = FilaPostgres(pool, relogio, parametros, socket.gethostname())
    return LacoDoWorker(fila, manipuladores, relogio), AgendarCiclo(fabrica, relogio), fila


def _ignorar(_: object) -> None:
    return None


def rodar_worker(uma_vez: bool) -> None:
    configurar_logs()
    url = ler_segredo("DYNAPRICE_DB_URL_FILE")
    with abrir_pool(url, tamanho_maximo=4) as pool:
        laco, agenda, fila = _montar_laco(pool)
        if uma_vez:
            laco.executar_um()
            return
        parar = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: parar.set())
        signal.signal(signal.SIGINT, lambda *_: parar.set())

        def agendar() -> None:
            for tenant_id in fila.inquilinos_ativos():
                agenda.executar(tenant_id)

        with EscutaDeJobs(url) as escuta:
            laco.rodar(parar, escuta.aguardar, agendar, _INTERVALO_DE_AGENDA_S)
