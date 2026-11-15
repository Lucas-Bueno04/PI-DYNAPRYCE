"""Conexões com o PostgreSQL: sempre em UTC, sem tenant fixado fora da transação."""

from typing import Any

import psycopg
from psycopg.rows import TupleRow
from psycopg_pool import ConnectionPool

type Conexao = psycopg.Connection[TupleRow]


def abrir_pool(url: str, tamanho_maximo: int = 10) -> ConnectionPool[Any]:
    return ConnectionPool(
        url,
        min_size=1,
        max_size=tamanho_maximo,
        kwargs={"options": "-c timezone=UTC"},
        open=True,
    )
