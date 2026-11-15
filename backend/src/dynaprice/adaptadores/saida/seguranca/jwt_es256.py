"""Adaptador a_jwt: tokens ES256 com kid e JWKS (ADR-002)."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from jwt.algorithms import ECAlgorithm

from dynaprice.aplicacao.portas import Relogio, TokenInvalido
from dynaprice.aplicacao.portas.oidc import EstadoDeFederacao
from dynaprice.dominio.modelos.autenticacao import Papel, Principal

_ALGORITMO = "ES256"
_VALIDADE_DO_ACESSO = timedelta(minutes=15)
_VALIDADE_DO_DESAFIO = timedelta(minutes=5)
_VALIDADE_DO_ESTADO = timedelta(minutes=10)
_TOLERANCIA_S = 30
_CLAIMS_DE_ACESSO = ["iss", "aud", "sub", "tid", "roles", "mfa", "iat", "exp", "jti"]
_CLAIMS_DE_DESAFIO = ["iss", "aud", "sub", "iat", "exp", "jti"]
_CLAIMS_DE_ESTADO = ["iss", "aud", "state", "nonce", "pkce", "iat", "exp", "jti"]


@dataclass(frozen=True, slots=True)
class ChavesEs256:
    """A chave atual assina; as anteriores só validam até o fim da validade dos tokens."""

    kid: str
    privada_pem: str = field(repr=False)
    publicas_anteriores: Mapping[str, str] = field(default_factory=dict)


def carregar_chaves_es256(arquivo: Path) -> ChavesEs256:
    """Lê o segredo da implantação: JSON {kid, privada, publicas_anteriores}."""
    conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
    return ChavesEs256(
        conteudo["kid"], conteudo["privada"], conteudo.get("publicas_anteriores", {})
    )


class EmissorJwtEs256:
    def __init__(self, chaves: ChavesEs256, relogio: Relogio, emissor: str, audiencia: str) -> None:
        privada = cast(
            EllipticCurvePrivateKey, load_pem_private_key(chaves.privada_pem.encode(), None)
        )
        self._kid = chaves.kid
        self._privada = privada
        self._publicas: dict[str, Any] = {chaves.kid: privada.public_key()}
        for kid, pem in chaves.publicas_anteriores.items():
            self._publicas[kid] = load_pem_public_key(pem.encode())
        self._relogio = relogio
        self._emissor = emissor
        self._audiencia = audiencia
        self._audiencia_mfa = f"{audiencia}-mfa"
        self._audiencia_oidc = f"{audiencia}-oidc"

    def _assinar(self, audiencia: str, validade: timedelta, extras: dict[str, Any]) -> str:
        agora = self._relogio.agora()
        corpo = {
            "iss": self._emissor,
            "aud": audiencia,
            "iat": int(agora.timestamp()),
            "exp": int((agora + validade).timestamp()),
            "jti": str(uuid4()),
            **extras,
        }
        return jwt.encode(corpo, self._privada, algorithm=_ALGORITMO, headers={"kid": self._kid})

    def emitir(self, principal: Principal) -> str:
        return self._assinar(
            self._audiencia,
            _VALIDADE_DO_ACESSO,
            {
                "sub": str(principal.usuario_id),
                "tid": str(principal.tenant_id),
                "roles": sorted(p.value for p in principal.papeis),
                "mfa": principal.mfa_verificado,
            },
        )

    def emitir_desafio(self, usuario_id: UUID) -> str:
        return self._assinar(self._audiencia_mfa, _VALIDADE_DO_DESAFIO, {"sub": str(usuario_id)})

    def _corpo_verificado(self, token: str, audiencia: str, claims: list[str]) -> dict[str, Any]:
        try:
            cabecalho = jwt.get_unverified_header(token)
            if cabecalho.get("alg") != _ALGORITMO:
                raise TokenInvalido("algoritmo recusado")
            publica = self._publicas.get(cabecalho.get("kid", ""))
            if publica is None:
                raise TokenInvalido("kid desconhecido")
            # A validade é conferida abaixo com o relógio injetável.
            corpo: dict[str, Any] = jwt.decode(
                token,
                publica,
                algorithms=[_ALGORITMO],
                issuer=self._emissor,
                audience=audiencia,
                options={"require": claims, "verify_exp": False, "verify_iat": False},
            )
        except jwt.PyJWTError as erro:
            raise TokenInvalido("token inválido") from erro
        if corpo["exp"] + _TOLERANCIA_S < self._relogio.agora().timestamp():
            raise TokenInvalido("token expirado")
        return corpo

    def verificar(self, token: str) -> Principal:
        corpo = self._corpo_verificado(token, self._audiencia, _CLAIMS_DE_ACESSO)
        try:
            if not isinstance(corpo["mfa"], bool):
                raise ValueError("mfa precisa ser booleano")
            return Principal(
                UUID(corpo["sub"]),
                UUID(corpo["tid"]),
                frozenset(Papel(papel) for papel in corpo["roles"]),
                corpo["mfa"],
            )
        except (ValueError, TypeError) as erro:
            raise TokenInvalido("claims inválidas") from erro

    def verificar_desafio(self, token: str) -> UUID:
        corpo = self._corpo_verificado(token, self._audiencia_mfa, _CLAIMS_DE_DESAFIO)
        try:
            return UUID(corpo["sub"])
        except (ValueError, TypeError) as erro:
            raise TokenInvalido("claims inválidas") from erro

    def emitir_estado_de_federacao(self, estado: EstadoDeFederacao) -> str:
        return self._assinar(
            self._audiencia_oidc,
            _VALIDADE_DO_ESTADO,
            {"state": estado.state, "nonce": estado.nonce, "pkce": estado.verificador_pkce},
        )

    def verificar_estado_de_federacao(self, token: str) -> EstadoDeFederacao:
        corpo = self._corpo_verificado(token, self._audiencia_oidc, _CLAIMS_DE_ESTADO)
        try:
            return EstadoDeFederacao(str(corpo["state"]), str(corpo["nonce"]), str(corpo["pkce"]))
        except (TypeError, ValueError) as erro:
            raise TokenInvalido("claims inválidas") from erro

    def jwks(self) -> dict[str, Any]:
        chaves = []
        for kid, publica in self._publicas.items():
            jwk = ECAlgorithm.to_jwk(publica, as_dict=True)
            chaves.append({**jwk, "kid": kid, "alg": _ALGORITMO, "use": "sig"})
        return {"keys": chaves}
