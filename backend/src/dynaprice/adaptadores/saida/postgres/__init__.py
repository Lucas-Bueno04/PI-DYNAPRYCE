"""Adaptador a_db: PostgreSQL com RLS (implementa as portas de persistência)."""

from dynaprice.adaptadores.saida.postgres.conexao import abrir_pool
from dynaprice.adaptadores.saida.postgres.escuta import EscutaDeJobs, EscutaDePoliticas
from dynaprice.adaptadores.saida.postgres.fila import FilaPostgres
from dynaprice.adaptadores.saida.postgres.unidade_de_trabalho import (
    FabricaDeUnidadesPostgres,
    UnidadeDeTrabalhoPostgres,
)

__all__ = [
    "EscutaDeJobs",
    "EscutaDePoliticas",
    "FabricaDeUnidadesPostgres",
    "FilaPostgres",
    "UnidadeDeTrabalhoPostgres",
    "abrir_pool",
]
