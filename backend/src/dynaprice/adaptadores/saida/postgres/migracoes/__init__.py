"""Migrações do esquema (Alembic): rodam pela cli, com o papel dynaprice_migrador (F1.9)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_PASTA = Path(__file__).resolve().parent


def migrar(url: str) -> None:
    """Leva o banco de `url` à revisão mais recente."""
    configuracao = Config()
    configuracao.set_main_option("script_location", str(_PASTA))
    configuracao.attributes["url"] = url.replace("postgresql://", "postgresql+psycopg://", 1)
    command.upgrade(configuracao, "head")
