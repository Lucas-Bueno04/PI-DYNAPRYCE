"""Leitura de segredos e configuração do ambiente (só o Composition Root lê o ambiente)."""

import hashlib
import hmac
import os
from collections.abc import Callable, Mapping
from pathlib import Path


def caminho_do_segredo(variavel: str) -> Path:
    caminho = os.environ.get(variavel, "")
    if not caminho:
        raise RuntimeError(f"defina {variavel}")
    return Path(caminho)


def ler_segredo(variavel: str) -> str:
    return caminho_do_segredo(variavel).read_text(encoding="utf-8").strip()


def exigir_ambiente(variavel: str) -> str:
    valor = os.environ.get(variavel, "")
    if not valor:
        raise RuntimeError(f"defina {variavel}")
    return valor


def pseudonimo_de_ip(chaves: Mapping[str, bytes]) -> Callable[[str], bytes]:
    chave = hmac.new(next(iter(chaves.values())), b"limite-de-ip", hashlib.sha256).digest()
    return lambda ip: hmac.new(chave, ip.encode(), hashlib.sha256).digest()
