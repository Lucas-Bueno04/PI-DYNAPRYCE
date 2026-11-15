"""F3.2: o adaptador OIDC valida o id_token (assinatura, emissor, público, validade e nonce)."""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from dynaprice.adaptadores.saida.oidc import (
    ConfiguracaoOidc,
    ProvedorOidcHttp,
    descobrir_configuracao,
)
from dynaprice.aplicacao.portas import TokenInvalido
from dynaprice.aplicacao.portas.oidc import IdentidadeFederada, desafio_pkce
from tests.adaptadores.idp_falso import CLIENTE, EMISSOR, IdpFalso
from tests.fakes import RelogioFixo

NONCE = "nonce-1"
VERIFICADOR = "v" * 43


class _Cenario:
    def __init__(self) -> None:
        self.idp = IdpFalso()
        self.relogio = RelogioFixo(datetime.now(UTC))
        transporte = self.idp.transporte(lambda: NONCE)
        config = ConfiguracaoOidc(
            emissor=EMISSOR,
            endpoint_de_autorizacao=f"{EMISSOR}/authorize",
            endpoint_de_token=f"{EMISSOR}/token",
            uri_das_chaves=f"{EMISSOR}/jwks",
            cliente_id=CLIENTE,
            segredo_do_cliente="segredo",
            uri_de_retorno="https://dynaprice.teste/api/v1/auth/oidc/retorno",
        )
        self.provedor = ProvedorOidcHttp(config, httpx.Client(transport=transporte), self.relogio)

    def identidade(self, nonce: str = NONCE) -> IdentidadeFederada:
        return self.provedor.identidade("codigo-1", VERIFICADOR, nonce)


@pytest.fixture
def c() -> _Cenario:
    return _Cenario()


def test_url_de_autorizacao_com_pkce_state_e_nonce(c: _Cenario) -> None:
    url = urlparse(c.provedor.url_de_autorizacao("st", NONCE, desafio_pkce(VERIFICADOR)))
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{EMISSOR}/authorize"
    assert q["response_type"] == "code" and q["client_id"] == CLIENTE
    assert q["scope"] == "openid email" and q["state"] == "st" and q["nonce"] == NONCE
    assert q["code_challenge_method"] == "S256"
    assert q["code_challenge"] == desafio_pkce(VERIFICADOR)
    assert q["redirect_uri"].endswith("/api/v1/auth/oidc/retorno")


def test_identidade_valida_e_pedido_de_token_com_pkce(c: _Cenario) -> None:
    ident = c.identidade()
    assert (ident.sujeito, ident.email, ident.email_verificado) == (
        "idp|123",
        "pessoa@escritorio.com",
        True,
    )
    pedido = c.idp.token_pedidos[0]
    assert pedido["grant_type"] == "authorization_code" and pedido["code"] == "codigo-1"
    assert pedido["code_verifier"] == VERIFICADOR
    assert pedido["redirect_uri"].endswith("/api/v1/auth/oidc/retorno")


def test_email_nao_verificado_ou_ausente_vira_falso(c: _Cenario) -> None:
    c.idp.claims = {"email_verified": None}
    assert c.identidade().email_verificado is False
    c.idp.claims = {"email_verified": "true"}  # só booleano verdadeiro vale
    assert c.identidade().email_verificado is False


@pytest.mark.parametrize(
    "alteracao",
    [
        {"iss": "https://outro.idp"},
        {"aud": "outro-cliente"},
        {"exp": 1},
        {"nonce": "outro"},
        {"sub": None},
    ],
)
def test_id_token_invalido_e_recusado(c: _Cenario, alteracao: dict[str, object]) -> None:
    c.idp.claims = alteracao
    with pytest.raises(TokenInvalido):
        c.identidade()


def test_assinatura_de_outra_chave_e_recusada(c: _Cenario) -> None:
    c.idp.chave_de_assinatura = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(TokenInvalido):
        c.identidade()


def test_kid_desconhecido_e_recusado(c: _Cenario) -> None:
    c.idp.kid_no_token = "outro"
    with pytest.raises(TokenInvalido):
        c.identidade()


def test_algoritmo_simetrico_e_recusado(c: _Cenario) -> None:
    """Confusão de algoritmo: HS256 assinado com material público não pode passar."""
    c.idp.algoritmo = "HS256"
    c.idp.chave_de_assinatura = "x" * 64
    with pytest.raises(TokenInvalido):
        c.identidade()


def test_erro_no_endpoint_de_token_e_recusado(c: _Cenario) -> None:
    c.idp.status_do_token = 400
    with pytest.raises(TokenInvalido):
        c.identidade()


def test_pkce_s256_conforme_a_rfc_7636() -> None:
    assert desafio_pkce("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def _descoberta(corpo: dict[str, object]) -> httpx.Client:
    def atender(pedido: httpx.Request) -> httpx.Response:
        assert pedido.url.path == "/.well-known/openid-configuration"
        return httpx.Response(200, json=corpo)

    return httpx.Client(transport=httpx.MockTransport(atender))


def _documento(**extras: object) -> dict[str, object]:
    return {
        "issuer": EMISSOR,
        "authorization_endpoint": f"{EMISSOR}/authorize",
        "token_endpoint": f"{EMISSOR}/token",
        "jwks_uri": f"{EMISSOR}/jwks",
        **extras,
    }


def test_descoberta_monta_a_configuracao() -> None:
    config = descobrir_configuracao(
        _descoberta(_documento()), EMISSOR, CLIENTE, "segredo", "https://app/retorno"
    )
    assert config.endpoint_de_token == f"{EMISSOR}/token"
    assert config.uri_das_chaves == f"{EMISSOR}/jwks" and config.cliente_id == CLIENTE


@pytest.mark.parametrize(
    "documento",
    [
        _documento(issuer="https://outro.idp"),  # emissor diferente do configurado
        {k: v for k, v in _documento().items() if k != "jwks_uri"},
        _documento(token_endpoint="http://idp.teste/token"),  # só HTTPS
    ],
)
def test_descoberta_invalida_e_recusada(documento: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="descoberta"):
        descobrir_configuracao(_descoberta(documento), EMISSOR, CLIENTE, "s", "https://app/r")
