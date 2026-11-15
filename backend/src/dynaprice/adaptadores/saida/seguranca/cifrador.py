"""Adaptador a_cif: envelope AES-256-GCM com id de chave (D-ROT-CHAVE).

Formato: versão (1) | tamanho do kid (1) | kid | nonce (12) | texto cifrado com etiqueta.
O cabeçalho e o contexto entram como dado autenticado.
"""

import base64
import json
import os
from collections.abc import Mapping
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dynaprice.aplicacao.portas import SegredoInvalido
from dynaprice.dominio.modelos import ValorInvalido

_VERSAO = 1
_TAMANHO_DA_CHAVE = 32
_TAMANHO_DO_NONCE = 12


def carregar_chaves_mestras(arquivo: Path) -> dict[str, bytes]:
    """Lê o segredo da implantação: JSON {kid: base64}; a última chave é a de cifragem."""
    conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
    return {kid: base64.b64decode(chave) for kid, chave in conteudo.items()}


class CifradorAesGcm:
    def __init__(self, chaves: Mapping[str, bytes]) -> None:
        if not chaves:
            raise ValorInvalido("nenhuma chave mestra configurada")
        if any(len(chave) != _TAMANHO_DA_CHAVE for chave in chaves.values()):
            raise ValorInvalido("chave mestra precisa ter 32 bytes")
        self._chaves = dict(chaves)
        self._kid_atual = list(chaves)[-1]

    def __repr__(self) -> str:
        return f"CifradorAesGcm(kids={list(self._chaves)})"

    def cifrar(self, segredo: bytes, contexto: str) -> bytes:
        kid = self._kid_atual.encode()
        cabecalho = bytes([_VERSAO, len(kid)]) + kid
        nonce = os.urandom(_TAMANHO_DO_NONCE)
        cifrado = AESGCM(self._chaves[self._kid_atual]).encrypt(
            nonce, segredo, cabecalho + contexto.encode()
        )
        return cabecalho + nonce + cifrado

    def decifrar(self, cifrado: bytes, contexto: str) -> bytes:
        cabecalho, kid, nonce, corpo = self._separar(cifrado)
        chave = self._chaves.get(kid)
        if chave is None:
            raise SegredoInvalido("chave desconhecida")
        try:
            return AESGCM(chave).decrypt(nonce, corpo, cabecalho + contexto.encode())
        except InvalidTag as erro:
            raise SegredoInvalido("texto cifrado inválido") from erro

    def recifrar(self, cifrado: bytes, contexto: str) -> bytes:
        return self.cifrar(self.decifrar(cifrado, contexto), contexto)

    @staticmethod
    def _separar(cifrado: bytes) -> tuple[bytes, str, bytes, bytes]:
        if len(cifrado) < 2 or cifrado[0] != _VERSAO:
            raise SegredoInvalido("formato inválido")
        fim_do_kid = 2 + cifrado[1]
        corpo = fim_do_kid + _TAMANHO_DO_NONCE
        if len(cifrado) <= corpo:
            raise SegredoInvalido("formato inválido")
        try:
            kid = cifrado[2:fim_do_kid].decode()
        except UnicodeDecodeError as erro:
            raise SegredoInvalido("formato inválido") from erro
        return cifrado[:fim_do_kid], kid, cifrado[fim_do_kid:corpo], cifrado[corpo:]
