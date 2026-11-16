"""Regera frontend/openapi.json sem banco: só precisa do desenho das rotas."""

import sys
from pathlib import Path

from dynaprice.adaptadores.entrada.api.aplicacao import criar_app
from dynaprice.adaptadores.entrada.api.seguranca import Servicos
from dynaprice.principal import exportar_openapi

if __name__ == "__main__":
    exportar_openapi(Path(sys.argv[1]), criar_app(Servicos(None, "")))  # type: ignore[arg-type]
