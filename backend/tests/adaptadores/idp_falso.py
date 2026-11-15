"""IdP OIDC falso para os testes: chave EC própria, JWKS, endpoint de token e id_token assinado."""

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

EMISSOR = "https://idp.teste"
CLIENTE = "dynaprice-cliente"


class IdpFalso:
    def __init__(self) -> None:
        self.privada = ec.generate_private_key(ec.SECP256R1())
        self.kid = "idp-1"
        self.token_pedidos: list[dict[str, str]] = []
        self.claims: dict[str, Any] = {}
        self.status_do_token = 200
        self.chave_de_assinatura: Any = self.privada
        self.algoritmo = "ES256"
        self.kid_no_token = self.kid

    def jwks(self) -> dict[str, Any]:
        jwk = ECAlgorithm.to_jwk(self.privada.public_key(), as_dict=True)
        return {"keys": [{**jwk, "kid": self.kid, "alg": "ES256", "use": "sig"}]}

    def id_token(self, nonce: str, **extras: Any) -> str:
        agora = int(time.time())
        corpo = {
            "iss": EMISSOR,
            "aud": CLIENTE,
            "sub": "idp|123",
            "email": "pessoa@escritorio.com",
            "email_verified": True,
            "iat": agora,
            "exp": agora + 300,
            "nonce": nonce,
            **self.claims,
            **extras,
        }
        corpo = {k: v for k, v in corpo.items() if v is not None}
        return jwt.encode(
            corpo,
            self.chave_de_assinatura,
            algorithm=self.algoritmo,
            headers={"kid": self.kid_no_token},
        )

    def transporte(self, nonce: Callable[[], str]) -> httpx.MockTransport:
        def atender(pedido: httpx.Request) -> httpx.Response:
            if pedido.url.path == "/jwks":
                return httpx.Response(200, json=self.jwks())
            if pedido.url.path == "/token":
                dados = {k: v[0] for k, v in parse_qs(pedido.content.decode()).items()}
                self.token_pedidos.append(dados)
                if self.status_do_token != 200:
                    return httpx.Response(self.status_do_token, json={"error": "invalid_grant"})
                return httpx.Response(200, content=json.dumps({"id_token": self.id_token(nonce())}))
            return httpx.Response(404)

        return httpx.MockTransport(atender)
