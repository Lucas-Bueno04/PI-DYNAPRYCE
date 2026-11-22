"""Anel 4, Composition Root: único ponto que liga as dependências e monta as entradas."""

from dynaprice.principal.api import ConfiguracaoDaApi, criar_api
from dynaprice.principal.cli import montar_cli

app = montar_cli()

__all__ = ["ConfiguracaoDaApi", "app", "criar_api"]
