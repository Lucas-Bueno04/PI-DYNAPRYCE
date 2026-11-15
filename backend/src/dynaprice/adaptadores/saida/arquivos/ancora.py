"""Âncora em arquivo só de acréscimo, com elos próprios (hash da linha anterior).

Vale como âncora **externa** quando o arquivo fica fora do banco e do servidor da aplicação
(outro host, montagem só de acréscimo ou armazenamento com retenção imutável): o elo próprio
detecta edição ou remoção no meio do arquivo; só o ponto de montagem decide quem pode apagar.
"""

import hashlib
import json
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from dynaprice.aplicacao.portas.ancora import Ancora, ErroDeAncora

_INICIO = "0" * 64


def _elo(anterior: str, registro: dict[str, Any]) -> str:
    canonico = json.dumps(registro, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((anterior + canonico).encode()).hexdigest()


class AncoraEmArquivo:
    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    def registrar(self, ancora: Ancora) -> None:
        registro = {
            "tenant": str(ancora.tenant_id),
            "seq": ancora.seq,
            "hash": ancora.hash_hex,
            "em": ancora.registrada_em.isoformat(),
        }
        anterior = self._ultimo_elo()
        linha = json.dumps({**registro, "elo": _elo(anterior, registro)}, sort_keys=True)
        descritor = os.open(self._caminho, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
        try:
            os.write(descritor, (linha + "\n").encode())
            os.fsync(descritor)
        finally:
            os.close(descritor)

    def listar(self, tenant_id: UUID) -> Sequence[Ancora]:
        return [a for a in self._ler() if a.tenant_id == tenant_id]

    def _ultimo_elo(self) -> str:
        ultimo = _INICIO
        for _, elo in self._linhas():
            ultimo = elo
        return ultimo

    def _ler(self) -> list[Ancora]:
        return [a for a, _ in self._linhas()]

    def _linhas(self) -> list[tuple[Ancora, str]]:
        if not self._caminho.exists():
            return []
        resultado: list[tuple[Ancora, str]] = []
        anterior = _INICIO
        for texto in self._caminho.read_text(encoding="utf-8").splitlines():
            try:
                bruto = json.loads(texto)
                elo = bruto.pop("elo")
                ancora = Ancora(
                    UUID(bruto["tenant"]),
                    int(bruto["seq"]),
                    str(bruto["hash"]),
                    datetime.fromisoformat(bruto["em"]),
                )
            except (ValueError, KeyError, TypeError, AttributeError) as erro:
                raise ErroDeAncora("linha ilegível na âncora") from erro
            if elo != _elo(anterior, bruto):
                raise ErroDeAncora("âncora adulterada: o elo não confere")
            resultado.append((ancora, elo))
            anterior = elo
        return resultado
