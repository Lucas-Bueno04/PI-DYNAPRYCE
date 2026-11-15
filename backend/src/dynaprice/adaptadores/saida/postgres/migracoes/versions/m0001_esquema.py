"""Esquema inicial de F1: core, raw, job, audit e auth, com RLS forçada."""

from pathlib import Path
from typing import Any, cast

from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    sql = Path(__file__).with_name("m0001_esquema.sql").read_text(encoding="utf-8")
    # Conexão do driver: várias instruções num só comando, na transação do Alembic.
    cast(Any, op.get_bind().connection.driver_connection).execute(sql.encode())
