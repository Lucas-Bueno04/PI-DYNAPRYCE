"""Provedor OIDC por HTTP: troca o código (com PKCE) e valida o id_token com as chaves do IdP."""

import threading
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from dynaprice.aplicacao.portas import Relogio, TokenInvalido
from dynaprice.aplicacao.portas.oidc import IdentidadeFederada

_ALGORITMOS = ["RS256", "ES256"]  # nunca HS256 nem "none": evita a confusão de algoritmo
_TOLERANCIA_S = 30
_VALIDADE_DAS_CHAVES = timedelta(minutes=10)
_CLAIMS = ["iss", "aud", "sub", "iat", "exp", "nonce"]


@dataclass(frozen=True, slots=True)
class ConfiguracaoOidc:
    emissor: str
    endpoint_de_autorizacao: str
    endpoint_de_token: str
    uri_das_chaves: str
    cliente_id: str
    segredo_do_cliente: str = field(repr=False)
    uri_de_retorno: str


class ProvedorOidcHttp:
    def __init__(self, config: ConfiguracaoOidc, http: httpx.Client, relogio: Relogio) -> None:
        self._config = config
        self._http = http
        self._relogio = relogio
        self._chaves: dict[str, Any] = {}
        self._chaves_ate = relogio.agora()
        self._trava = threading.Lock()

    def url_de_autorizacao(self, state: str, nonce: str, desafio_pkce: str) -> str:
        consulta = urlencode(
            {
                "response_type": "code",
                "client_id": self._config.cliente_id,
                "redirect_uri": self._config.uri_de_retorno,
                "scope": "openid email",
                "state": state,
                "nonce": nonce,
                "code_challenge": desafio_pkce,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._config.endpoint_de_autorizacao}?{consulta}"

    def identidade(self, codigo: str, verificador_pkce: str, nonce: str) -> IdentidadeFederada:
        id_token = self._id_token(codigo, verificador_pkce)
        corpo = self._corpo_validado(id_token, nonce)
        email = corpo.get("email")
        return IdentidadeFederada(
            sujeito=str(corpo["sub"]),
            email=email.lower() if isinstance(email, str) else "",
            email_verificado=corpo.get("email_verified") is True,
        )

    def _id_token(self, codigo: str, verificador: str) -> str:
        try:
            resposta = self._http.post(
                self._config.endpoint_de_token,
                data={
                    "grant_type": "authorization_code",
                    "code": codigo,
                    "redirect_uri": self._config.uri_de_retorno,
                    "client_id": self._config.cliente_id,
                    "client_secret": self._config.segredo_do_cliente,
                    "code_verifier": verificador,
                },
            )
            resposta.raise_for_status()
            token = resposta.json()["id_token"]
        except (httpx.HTTPError, KeyError, ValueError) as erro:
            raise TokenInvalido("o provedor recusou o código") from erro
        if not isinstance(token, str):
            raise TokenInvalido("id_token ausente")
        return token

    def _corpo_validado(self, id_token: str, nonce: str) -> dict[str, Any]:
        try:
            cabecalho = jwt.get_unverified_header(id_token)
            if cabecalho.get("alg") not in _ALGORITMOS:
                raise TokenInvalido("algoritmo recusado")
            chave = self._chave(str(cabecalho.get("kid", "")))
            corpo: dict[str, Any] = jwt.decode(
                id_token,
                chave,
                algorithms=_ALGORITMOS,
                issuer=self._config.emissor,
                audience=self._config.cliente_id,
                options={"require": _CLAIMS, "verify_exp": False, "verify_iat": False},
            )
        except (jwt.PyJWTError, ValueError) as erro:
            raise TokenInvalido("id_token inválido") from erro
        if corpo["exp"] + _TOLERANCIA_S < self._relogio.agora().timestamp():
            raise TokenInvalido("id_token expirado")
        if corpo["nonce"] != nonce:
            raise TokenInvalido("nonce não confere")
        return corpo

    def _chave(self, kid: str) -> Any:
        with self._trava:
            if self._relogio.agora() >= self._chaves_ate or kid not in self._chaves:
                self._recarregar_chaves()
            if kid not in self._chaves:
                raise TokenInvalido("kid desconhecido")
            return self._chaves[kid]

    def _recarregar_chaves(self) -> None:
        try:
            resposta = self._http.get(self._config.uri_das_chaves)
            resposta.raise_for_status()
            chaves = resposta.json()["keys"]
        except (httpx.HTTPError, KeyError, ValueError) as erro:
            raise TokenInvalido("chaves do provedor indisponíveis") from erro
        self._chaves = {k["kid"]: _chave_publica(k) for k in chaves if "kid" in k}
        self._chaves_ate = self._relogio.agora() + _VALIDADE_DAS_CHAVES


def _chave_publica(jwk: dict[str, Any]) -> Any:
    if jwk.get("kty") == "EC":
        return ECAlgorithm.from_jwk(jwk)
    return RSAAlgorithm.from_jwk(jwk)


def descobrir_configuracao(
    http: httpx.Client, emissor: str, cliente_id: str, segredo: str, uri_de_retorno: str
) -> ConfiguracaoOidc:
    """Lê /.well-known/openid-configuration; o `issuer` do documento precisa ser o configurado."""
    try:
        resposta = http.get(f"{emissor.rstrip('/')}/.well-known/openid-configuration")
        resposta.raise_for_status()
        doc = resposta.json()
        autorizacao, token, chaves = (
            doc["authorization_endpoint"],
            doc["token_endpoint"],
            doc["jwks_uri"],
        )
        valido = doc["issuer"] == emissor and all(
            isinstance(u, str) and u.startswith("https://") for u in (autorizacao, token, chaves)
        )
    except (httpx.HTTPError, KeyError, ValueError) as erro:
        raise ValueError("descoberta OIDC falhou") from erro
    if not valido:
        raise ValueError("descoberta OIDC inválida: emissor diferente ou endpoint sem HTTPS")
    return ConfiguracaoOidc(
        emissor, autorizacao, token, chaves, cliente_id, segredo, uri_de_retorno
    )
