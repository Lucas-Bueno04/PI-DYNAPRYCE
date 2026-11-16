"""F3.2: rotas de entrada por OIDC (redirecionamento, cookie de estado e retorno)."""

from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from dynaprice.dominio.modelos.autenticacao import Papel
from dynaprice.principal import ConfiguracaoDaApi, criar_api
from tests.api.apoio import criar_usuario
from tests.aplicacao.test_federacao import ProvedorFalso

ORIGEM = {"Origin": "https://dynaprice.teste"}
COOKIE_ESTADO = "dynaprice_oidc"


@pytest.fixture
def provedor() -> ProvedorFalso:
    return ProvedorFalso()


@pytest.fixture
def federado(configuracao: ConfiguracaoDaApi, provedor: ProvedorFalso) -> Iterator[TestClient]:
    app = criar_api(replace(configuracao, provedor_oidc=provedor))
    with TestClient(
        app,
        base_url="https://dynaprice.teste",
        raise_server_exceptions=False,
        follow_redirects=False,
    ) as aberto:
        yield aberto


def _iniciar(cliente: TestClient) -> str:
    resposta = cliente.get("/api/v1/auth/oidc/entrar")
    assert resposta.status_code == 302
    state: str = parse_qs(urlparse(resposta.headers["location"]).query)["state"][0]
    return state


def test_disponibilidade_acompanha_a_configuracao(
    cliente: TestClient, federado: TestClient
) -> None:
    assert cliente.get("/api/v1/auth/oidc/disponivel").json() == {"disponivel": False}
    assert federado.get("/api/v1/auth/oidc/disponivel").json() == {"disponivel": True}


def test_sem_provedor_configurado_as_rotas_nao_existem(cliente: TestClient) -> None:
    assert cliente.get("/api/v1/auth/oidc/entrar").status_code == 404
    assert (
        cliente.get("/api/v1/auth/oidc/retorno", params={"code": "c", "state": "s"}).status_code
        == 404
    )


def test_entrar_redireciona_ao_idp_e_grava_o_estado_em_cookie_seguro(federado: TestClient) -> None:
    resposta = federado.get("/api/v1/auth/oidc/entrar")
    assert resposta.status_code == 302
    assert resposta.headers["location"].startswith("https://idp.teste/authorize?state=")
    cookie = resposta.headers["set-cookie"].lower()
    for atributo in (COOKIE_ESTADO, "httponly", "secure", "samesite=lax", "path=/api/v1/auth/oidc"):
        assert atributo in cookie
    assert "max-age=600" in cookie


def test_retorno_de_analista_abre_sessao_e_o_refresh_renova(
    federado: TestClient, provedor: ProvedorFalso, novo_tenant: object
) -> None:
    email, _ = criar_usuario(federado, novo_tenant, {Papel.ANALISAR})  # type: ignore[arg-type]
    provedor.email = email
    state = _iniciar(federado)
    resposta = federado.get("/api/v1/auth/oidc/retorno", params={"code": "c", "state": state})
    assert (resposta.status_code, resposta.headers["location"]) == (302, "/")
    cookies = " ".join(resposta.headers.get_list("set-cookie")).lower()
    assert "dynaprice_refresh" in cookies and "samesite=strict" in cookies
    assert f'{COOKIE_ESTADO}=""' in cookies or f"{COOKIE_ESTADO}=;" in cookies  # estado apagado
    renovado = federado.post("/api/v1/auth/renovar", headers=ORIGEM)
    assert renovado.status_code == 200 and renovado.json()["acesso"]


def test_retorno_com_mfa_leva_o_desafio_no_fragmento(
    federado: TestClient, provedor: ProvedorFalso, novo_tenant: object
) -> None:
    email, _ = criar_usuario(federado, novo_tenant, {Papel.APROVAR})  # type: ignore[arg-type]
    provedor.email = email
    state = _iniciar(federado)
    resposta = federado.get("/api/v1/auth/oidc/retorno", params={"code": "c", "state": state})
    destino = urlparse(resposta.headers["location"])
    assert destino.path == "/entrar" and not destino.query  # o desafio nunca vai na query
    fragmento = parse_qs(destino.fragment)
    assert fragmento["desafio"][0] and fragmento["cadastro_mfa"] == ["1"]
    assert "dynaprice_refresh" not in resposta.headers.get("set-cookie", "")


@pytest.mark.parametrize(
    "variante", ["state_errado", "sem_cookie", "erro_do_idp", "conta_inexistente"]
)
def test_falhas_voltam_para_a_tela_de_entrada_sem_detalhe(
    federado: TestClient, provedor: ProvedorFalso, variante: str
) -> None:
    provedor.email = "ninguem@teste.com"
    state = _iniciar(federado)
    params = {"code": "c", "state": "forjado" if variante == "state_errado" else state}
    if variante == "erro_do_idp":
        params = {"error": "access_denied", "state": state}
    if variante == "sem_cookie":
        federado.cookies.clear()
    resposta = federado.get("/api/v1/auth/oidc/retorno", params=params)
    assert (resposta.status_code, resposta.headers["location"]) == (302, "/entrar?erro=federacao")
    assert "dynaprice_refresh" not in resposta.headers.get("set-cookie", "")
