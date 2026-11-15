"""Porta `idp` (F3): federação OIDC por código com PKCE; o JWT continua o próprio (ADR-002)."""

import base64
import hashlib
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IdentidadeFederada:
    sujeito: str
    email: str
    email_verificado: bool


@dataclass(frozen=True, slots=True)
class EstadoDeFederacao:
    """Conteúdo do cookie assinado entre o início e o retorno do fluxo."""

    state: str
    nonce: str
    verificador_pkce: str


class ProvedorOidc(Protocol):
    def url_de_autorizacao(self, state: str, nonce: str, desafio_pkce: str) -> str: ...

    def identidade(self, codigo: str, verificador_pkce: str, nonce: str) -> IdentidadeFederada:
        """Troca o código e valida o id_token; levanta TokenInvalido se algo não conferir."""
        ...


def desafio_pkce(verificador: str) -> str:
    """code_challenge S256 (RFC 7636)."""
    resumo = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")
