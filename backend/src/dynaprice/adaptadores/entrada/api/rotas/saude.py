"""Saúde do serviço."""

from fastapi import APIRouter

from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, publica

roteador = APIRouter(tags=["saude"])


@roteador.get("/saude", **publica())
def saude(deps: Dependencias) -> dict[str, str]:
    with deps.auth.fabrica.sem_tenant() as uow:
        uow.usuarios.existe_administrador()
    return {"situacao": "ok"}
