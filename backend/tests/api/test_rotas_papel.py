"""F1.18: toda rota declara papel e a declaração é aplicada de fato (S5)."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from dynaprice.adaptadores.entrada.api.seguranca import AUTENTICADA, PUBLICA
from dynaprice.aplicacao.autorizacao import MATRIZ, Acao, autorizar
from dynaprice.aplicacao.erros import AcessoNegado
from dynaprice.dominio.modelos.autenticacao import Papel, Principal

_METODOS = {"get", "post", "put", "patch", "delete"}
# Rotas públicas são a exceção: a lista é explícita para uma nova não entrar sem revisão.
PUBLICAS_ESPERADAS = {
    "GET /api/v1/saude",
    "GET /api/v1/auth/jwks.json",
    "POST /api/v1/auth/entrar",
    "POST /api/v1/auth/mfa",
    "POST /api/v1/auth/mfa/cadastrar",
    "POST /api/v1/auth/mfa/confirmar",
    "POST /api/v1/auth/renovar",
    "POST /api/v1/auth/sair",
    "POST /api/v1/auth/redefinir",
    "POST /api/v1/auth/recuperar-mfa",
    "GET /api/v1/auth/oidc/entrar",
    "GET /api/v1/auth/oidc/disponivel",
    "GET /api/v1/auth/oidc/retorno",
}


def _operacoes(cliente: TestClient) -> list[tuple[str, str, dict[str, object]]]:
    especificacao = cliente.app.openapi()  # type: ignore[attr-defined]
    return [
        (metodo.upper(), caminho, operacao)
        for caminho, item in especificacao["paths"].items()
        for metodo, operacao in item.items()
        if metodo in _METODOS
    ]


def _token(cliente: TestClient, principal: Principal) -> dict[str, str]:
    emissor = cliente.app.state.servicos.auth.emissor  # type: ignore[attr-defined]
    return {"Authorization": f"Bearer {emissor.emitir(principal)}"}


def _preencher(caminho: str) -> str:
    import re

    return re.sub(r"\{[^}]+\}", str(uuid4()), caminho)


def test_toda_rota_declara_papel(cliente: TestClient) -> None:
    sem_papel = [f"{m} {c}" for m, c, op in _operacoes(cliente) if "x-papel" not in op]
    assert sem_papel == []


def test_papeis_declarados_existem_na_matriz(cliente: TestClient) -> None:
    validos = {PUBLICA, AUTENTICADA} | {acao.value for acao in Acao}
    declarados = {str(op["x-papel"]) for _, _, op in _operacoes(cliente)}
    assert declarados <= validos


def test_rotas_publicas_sao_exatamente_as_esperadas(cliente: TestClient) -> None:
    publicas = {f"{m} {c}" for m, c, op in _operacoes(cliente) if op["x-papel"] == PUBLICA}
    assert publicas == PUBLICAS_ESPERADAS


def test_rota_protegida_sem_token_responde_401(cliente: TestClient) -> None:
    protegidas = [(m, c) for m, c, op in _operacoes(cliente) if op["x-papel"] != PUBLICA]
    assert protegidas
    for metodo, caminho in protegidas:
        resposta = cliente.request(metodo, _preencher(caminho), json={})
        assert resposta.status_code == 401, f"{metodo} {caminho}"


def test_rota_protegida_com_token_invalido_responde_401(cliente: TestClient) -> None:
    resposta = cliente.get("/api/v1/usuarios", headers={"Authorization": "Bearer lixo"})
    assert resposta.status_code == 401


def test_papel_errado_responde_403(cliente: TestClient, novo_tenant: UUID) -> None:
    principal = Principal(uuid4(), novo_tenant, frozenset({Papel.ANALISAR}), True)
    assert cliente.get("/api/v1/usuarios", headers=_token(cliente, principal)).status_code == 403


def test_administrar_sem_totp_na_sessao_e_recusado(cliente: TestClient, novo_tenant: UUID) -> None:
    principal = Principal(uuid4(), novo_tenant, frozenset({Papel.ADMINISTRAR}), False)
    assert cliente.get("/api/v1/usuarios", headers=_token(cliente, principal)).status_code == 403


def test_administrador_com_totp_passa(cliente: TestClient, novo_tenant: UUID) -> None:
    principal = Principal(uuid4(), novo_tenant, frozenset({Papel.ADMINISTRAR}), True)
    assert cliente.get("/api/v1/usuarios", headers=_token(cliente, principal)).status_code == 200


@pytest.mark.parametrize("acao", [Acao.DECIDIR_RECOMENDACAO, Acao.PUBLICAR_POLITICA])
def test_aprovar_sem_totp_na_sessao_e_recusado(acao: Acao) -> None:
    principal = Principal(uuid4(), uuid4(), frozenset({Papel.APROVAR}), mfa_verificado=False)
    with pytest.raises(AcessoNegado):
        autorizar(principal, acao)


def test_aprovar_com_totp_na_sessao_passa() -> None:
    autorizar(
        Principal(uuid4(), uuid4(), frozenset({Papel.APROVAR}), mfa_verificado=True),
        Acao.DECIDIR_RECOMENDACAO,
    )


def test_toda_acao_esta_na_matriz() -> None:
    assert set(MATRIZ) == set(Acao)


def test_quem_aprova_e_quem_administra_exigem_mfa_nas_acoes_sensiveis() -> None:
    for acao in (
        Acao.DECIDIR_RECOMENDACAO,
        Acao.PUBLICAR_POLITICA,
        Acao.GERIR_USUARIOS,
        Acao.GERIR_CONECTORES,
    ):
        assert MATRIZ[acao].exige_mfa, acao


def test_cookie_de_refresh_tem_atributos_da_adr(
    cliente: TestClient, novo_tenant: UUID, configuracao: object
) -> None:
    from tests.api.apoio import criar_usuario

    email, senha = criar_usuario(cliente, novo_tenant, {Papel.ANALISAR})
    resposta = cliente.post("/api/v1/auth/entrar", json={"email": email, "senha": senha})
    assert resposta.status_code == 200
    cabecalho = resposta.headers["set-cookie"].lower()
    for atributo in ("httponly", "secure", "samesite=strict", "path=/api/v1/auth"):
        assert atributo in cabecalho
    assert "refresh" not in resposta.json()["tokens"]


def test_renovar_confere_a_origem(cliente: TestClient, novo_tenant: UUID) -> None:
    from tests.api.apoio import criar_usuario

    email, senha = criar_usuario(cliente, novo_tenant, {Papel.ANALISAR})
    cliente.post("/api/v1/auth/entrar", json={"email": email, "senha": senha})
    invalida = cliente.post("/api/v1/auth/renovar", headers={"Origin": "https://outra.com"})
    assert invalida.status_code == 403
    valida = cliente.post("/api/v1/auth/renovar", headers={"Origin": "https://dynaprice.teste"})
    assert valida.status_code == 200
