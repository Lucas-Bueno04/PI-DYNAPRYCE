"""Portas p_cif, p_cred e p_tok."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from dynaprice.aplicacao.portas.oidc import EstadoDeFederacao
from dynaprice.dominio.modelos.autenticacao import Principal


class SegredoInvalido(Exception):
    """Texto cifrado adulterado, de outro contexto ou de chave desconhecida."""


class TokenInvalido(Exception):
    """Token recusado. A mensagem não diz o motivo a quem chamou a API."""


class Cifrador(Protocol):
    def cifrar(self, segredo: bytes, contexto: str) -> bytes: ...

    def decifrar(self, cifrado: bytes, contexto: str) -> bytes: ...

    def recifrar(self, cifrado: bytes, contexto: str) -> bytes: ...


class HashDeSenha(Protocol):
    def gerar(self, senha: str) -> str: ...

    def verificar(self, hash_guardado: str, senha: str) -> bool: ...

    def simular_verificacao(self, senha: str) -> None:
        """Gasta o mesmo tempo de uma verificação: e-mail inexistente não é detectável."""
        ...

    def precisa_refazer(self, hash_guardado: str) -> bool: ...


class VerificadorTotp(Protocol):
    def novo_segredo(self) -> str: ...

    def uri(self, segredo: str, conta: str) -> str: ...

    def passo_valido(self, segredo: str, codigo: str, instante: datetime) -> int | None:
        """Passo de tempo em que o código vale; serve para recusar o mesmo código duas vezes."""
        ...


class EmissorDeTokens(Protocol):
    def emitir(self, principal: Principal) -> str: ...

    def verificar(self, token: str) -> Principal: ...

    def emitir_desafio(self, usuario_id: UUID) -> str: ...

    def verificar_desafio(self, token: str) -> UUID: ...

    def emitir_estado_de_federacao(self, estado: EstadoDeFederacao) -> str: ...

    def verificar_estado_de_federacao(self, token: str) -> EstadoDeFederacao: ...

    def jwks(self) -> dict[str, Any]: ...
