"""Índice de inflação global (core.indice_inflacao): só o papel migrador grava."""

from decimal import Decimal
from typing import Any

from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres.repositorios.cadastro import data_da_competencia
from dynaprice.dominio.modelos.indice import VariacaoDeIndice

INDICE_PADRAO = "IPCA"


class IndicesDeInflacaoPostgres:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def gravar_se_ausente(self, variacao: VariacaoDeIndice, registrado_por: str) -> Decimal | None:
        data = data_da_competencia(variacao.competencia)
        with self._pool.connection() as conexao:
            gravada = conexao.execute(
                """INSERT INTO core.indice_inflacao (competencia, indice, variacao, registrado_por)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (competencia, indice) DO NOTHING
                   RETURNING 1""",
                (data, INDICE_PADRAO, variacao.variacao, registrado_por),
            ).fetchone()
            if gravada is not None:
                return None
            linha = conexao.execute(
                "SELECT variacao FROM core.indice_inflacao WHERE competencia = %s AND indice = %s",
                (data, INDICE_PADRAO),
            ).fetchone()
        assert linha is not None
        existente: Decimal = linha[0]
        return existente
