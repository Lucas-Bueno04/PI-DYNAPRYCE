"""Ajudantes dos testes de API."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from dynaprice.dominio.modelos.autenticacao import Papel, Usuario

SENHA = "senha-bem-longa-123"


def criar_usuario(cliente: TestClient, tenant: UUID, papeis: set[Papel]) -> tuple[str, str]:
    auth = cliente.app.state.servicos.auth  # type: ignore[attr-defined]
    email = f"{uuid4()}@teste.com"
    usuario = Usuario(uuid4(), email, auth.hash_de_senha.gerar(SENHA))
    with auth.fabrica.sem_tenant() as uow:
        uow.usuarios.criar(usuario)
        uow.usuarios.definir_papeis(usuario.id, tenant, frozenset(papeis))
    return email, SENHA
