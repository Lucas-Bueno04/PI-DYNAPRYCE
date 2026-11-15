"""Ambiente do Alembic: a URL vem de quem chamou, nunca de arquivo versionado."""

from alembic import context
from sqlalchemy import create_engine, pool

motor = create_engine(context.config.attributes["url"], poolclass=pool.NullPool)
with motor.connect() as conexao:
    context.configure(connection=conexao, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
