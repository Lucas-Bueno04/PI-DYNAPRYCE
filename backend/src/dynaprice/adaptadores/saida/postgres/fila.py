"""Lado consumidor da fila: reserva por SKIP LOCKED, lease, backoff e órfãos (F1.13)."""

import random
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID

from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.aplicacao.portas import JobReservado, LeasePerdido, Relogio
from dynaprice.dominio.modelos.fila import ParametrosDeFila, atraso_de_backoff


class FilaPostgres:
    def __init__(
        self,
        pool: ConnectionPool[Any],
        relogio: Relogio,
        parametros: ParametrosDeFila,
        dono: str,
    ) -> None:
        self._pool = pool
        self._relogio = relogio
        self._parametros = parametros
        self._dono = dono

    @property
    def intervalo_de_heartbeat(self) -> float:
        return self._parametros.heartbeat_s

    @property
    def intervalo_de_varredura(self) -> float:
        return self._parametros.varredura_s

    @contextmanager
    def _transacao(self, tenant_id: UUID) -> Iterator[Conexao]:
        with self._pool.connection() as conexao, conexao.transaction():
            conexao.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
            yield conexao

    def reservar(self) -> JobReservado | None:
        with self._pool.connection() as conexao:
            linha = conexao.execute(
                """SELECT id, tenant_id, tipo, parametros, tentativas
                   FROM job.reservar_proximo(%s, %s, %s, %s)""",
                (
                    self._dono,
                    self._relogio.agora(),
                    timedelta(seconds=self._parametros.lease_s),
                    self._parametros.max_tentativas,
                ),
            ).fetchone()
        return None if linha is None else JobReservado(*linha)

    def _atualizar_com_lease(
        self, conexao: Conexao, job: JobReservado, atribuicoes: str, valores: tuple[Any, ...]
    ) -> None:
        cursor = conexao.execute(
            f"UPDATE job.job SET {atribuicoes} "  # atribuicoes são literais deste módulo
            "WHERE id = %s AND lease_dono = %s AND estado = 'em_execucao'",
            (*valores, job.id, self._dono),
        )
        if cursor.rowcount != 1:
            raise LeasePerdido(f"job {job.id}")

    def heartbeat(self, job: JobReservado) -> None:
        agora = self._relogio.agora()
        limite = agora + timedelta(seconds=self._parametros.lease_s)
        with self._transacao(job.tenant_id) as conexao:
            self._atualizar_com_lease(
                conexao, job, "heartbeat_em = %s, lease_ate = %s", (agora, limite)
            )

    def concluir(self, job: JobReservado) -> None:
        with self._transacao(job.tenant_id) as conexao:
            self._atualizar_com_lease(
                conexao,
                job,
                "estado = 'concluido', concluido_em = %s, lease_ate = NULL, erro = NULL",
                (self._relogio.agora(),),
            )

    def falhar(self, job: JobReservado, erro: str, *, permanente: bool) -> None:
        with self._transacao(job.tenant_id) as conexao:
            if permanente or job.tentativas >= self._parametros.max_tentativas:
                self._encerrar_com_falha(conexao, job, erro)
            else:
                self._devolver_com_backoff(conexao, job, erro)

    def _encerrar_com_falha(self, conexao: Conexao, job: JobReservado, erro: str) -> None:
        self._atualizar_com_lease(
            conexao,
            job,
            "estado = 'falhou', erro = %s, lease_dono = NULL, lease_ate = NULL",
            (erro,),
        )
        conexao.execute(
            "INSERT INTO core.alerta (tenant_id, tipo, referencia) "
            "VALUES (core.tenant_atual(), 'job_falhou', %s)",
            (str(job.id),),
        )

    def _devolver_com_backoff(self, conexao: Conexao, job: JobReservado, erro: str) -> None:
        espera = atraso_de_backoff(job.tentativas, self._parametros, random.random())
        self._atualizar_com_lease(
            conexao,
            job,
            "estado = 'pendente', erro = %s, proxima_tentativa_em = %s, "
            "lease_dono = NULL, lease_ate = NULL",
            (erro, self._relogio.agora() + timedelta(seconds=espera)),
        )

    def inquilinos_ativos(self) -> Sequence[UUID]:
        with self._pool.connection() as conexao:
            linhas = conexao.execute("SELECT job.listar_tenants_ativos()").fetchall()
        return [linha[0] for linha in linhas]

    def recuperar_orfaos(self) -> int:
        with self._pool.connection() as conexao:
            linha = conexao.execute(
                "SELECT job.recuperar_orfaos(%s)", (self._relogio.agora(),)
            ).fetchone()
        return int(linha[0]) if linha else 0
