"""Lado produtor da fila: grava o job na transação de quem o originou."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from dynaprice.adaptadores.saida.postgres.conexao import Conexao


class AgendaDeJobsPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def enfileirar(
        self, tipo: str, chave: str, parametros: Mapping[str, Any], quando: datetime
    ) -> bool:
        cursor = self._conexao.execute(
            """INSERT INTO job.job (tenant_id, tipo, chave_idempotencia, parametros,
                   proxima_tentativa_em)
               VALUES (core.tenant_atual(), %s, %s, %s, %s)
               ON CONFLICT (tenant_id, chave_idempotencia) DO NOTHING""",
            (tipo, chave, Jsonb(dict(parametros)), quando),
        )
        return cursor.rowcount == 1

    def reabrir(self, chave: str, quando: datetime) -> None:
        self._conexao.execute(
            """UPDATE job.job SET estado = 'pendente', tentativas = 0, erro = NULL,
                   proxima_tentativa_em = %s
               WHERE chave_idempotencia = %s AND estado = 'falhou'""",
            (quando, chave),
        )
