"""Trilha de auditoria encadeada por hash, serializada por inquilino (RNF06, D-HASH)."""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.aplicacao.portas import Relogio

INICIO_DA_CADEIA = bytes(32)


def _hash(anterior: bytes, campos: Mapping[str, Any]) -> bytes:
    canonico = json.dumps(campos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(anterior + canonico.encode()).digest()


def _campos(
    seq: int,
    usuario_id: UUID | None,
    request_id: str | None,
    tipo: str,
    conteudo: Any,
    criado_em: datetime,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "usuario_id": None if usuario_id is None else str(usuario_id),
        "request_id": request_id,
        "tipo": tipo,
        "conteudo": conteudo,
        "criado_em": criado_em.astimezone(UTC).isoformat(),
    }


class TrilhaDeAuditoriaPostgres:
    def __init__(self, conexao: Conexao, relogio: Relogio) -> None:
        self._conexao = conexao
        self._relogio = relogio

    def registrar(
        self,
        tipo: str,
        conteudo: Mapping[str, Any],
        *,
        usuario_id: UUID | None = None,
        request_id: str | None = None,
    ) -> None:
        # O lock vale até o fim da transação: dois escritores não leem o mesmo último elo.
        self._conexao.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(core.tenant_atual()::text, 0))"
        )
        linha = self._conexao.execute(
            "SELECT seq, hash FROM audit.evento ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        seq, anterior = (1, INICIO_DA_CADEIA) if linha is None else (linha[0] + 1, bytes(linha[1]))
        normalizado = json.loads(json.dumps(conteudo, default=str))
        criado_em = self._relogio.agora()
        selo = _hash(anterior, _campos(seq, usuario_id, request_id, tipo, normalizado, criado_em))
        self._conexao.execute(
            """INSERT INTO audit.evento (tenant_id, seq, usuario_id, request_id, tipo, conteudo,
                   criado_em, hash_anterior, hash)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s, %s, %s)""",
            (seq, usuario_id, request_id, tipo, Jsonb(normalizado), criado_em, anterior, selo),
        )

    def primeira_quebra(self) -> int | None:
        anterior, esperado = INICIO_DA_CADEIA, 1
        for linha in self._conexao.execute(
            "SELECT seq, usuario_id, request_id, tipo, conteudo, criado_em, hash_anterior, hash "
            "FROM audit.evento ORDER BY seq"
        ):
            seq, usuario, request, tipo, conteudo, criado_em, elo, selo = linha
            calculado = _hash(anterior, _campos(seq, usuario, request, tipo, conteudo, criado_em))
            if seq != esperado or bytes(elo) != anterior or bytes(selo) != calculado:
                return int(seq)
            anterior, esperado = bytes(selo), esperado + 1
        return None

    def cabeca(self) -> tuple[int, str] | None:
        linha = self._conexao.execute(
            "SELECT seq, hash FROM audit.evento ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return None if linha is None else (int(linha[0]), bytes(linha[1]).hex())

    def hash_em(self, seq: int) -> str | None:
        linha = self._conexao.execute(
            "SELECT hash FROM audit.evento WHERE seq = %s", (seq,)
        ).fetchone()
        return None if linha is None else bytes(linha[0]).hex()
