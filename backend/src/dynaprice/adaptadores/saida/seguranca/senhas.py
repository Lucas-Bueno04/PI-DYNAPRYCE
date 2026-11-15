"""Adaptadores a_hash: senha em Argon2id e TOTP (ADR-002)."""

import hmac
from datetime import datetime

import pyotp
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

_PERIODO_TOTP = 30
_TOLERANCIA_EM_PASSOS = 1


class HashDeSenhaArgon2:
    def __init__(self, tempo: int = 3, memoria_kib: int = 65536, paralelismo: int = 4) -> None:
        self._hasher = PasswordHasher(
            time_cost=tempo, memory_cost=memoria_kib, parallelism=paralelismo, type=Type.ID
        )
        self._hash_simulado: str | None = None

    def gerar(self, senha: str) -> str:
        return self._hasher.hash(senha)

    def verificar(self, hash_guardado: str, senha: str) -> bool:
        try:
            return self._hasher.verify(hash_guardado, senha)
        except VerificationError, InvalidHashError:
            return False

    def simular_verificacao(self, senha: str) -> None:
        if self._hash_simulado is None:
            self._hash_simulado = self._hasher.hash("verificacao-simulada")
        self.verificar(self._hash_simulado, senha)

    def precisa_refazer(self, hash_guardado: str) -> bool:
        return self._hasher.check_needs_rehash(hash_guardado)


class VerificadorTotpPyotp:
    def novo_segredo(self) -> str:
        return pyotp.random_base32()

    def uri(self, segredo: str, conta: str) -> str:
        return pyotp.TOTP(segredo).provisioning_uri(name=conta, issuer_name="DynaPrice")

    def passo_valido(self, segredo: str, codigo: str, instante: datetime) -> int | None:
        totp = pyotp.TOTP(segredo)
        atual = int(instante.timestamp()) // _PERIODO_TOTP
        for passo in range(atual - _TOLERANCIA_EM_PASSOS, atual + _TOLERANCIA_EM_PASSOS + 1):
            if hmac.compare_digest(totp.at(passo * _PERIODO_TOTP).encode(), codigo.encode()):
                return passo
        return None
