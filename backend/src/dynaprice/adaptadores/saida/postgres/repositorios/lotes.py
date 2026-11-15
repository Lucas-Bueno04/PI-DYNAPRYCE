"""Lotes de exportação: um lote por conjunto de recomendações (idempotência da exportação)."""

from datetime import datetime
from uuid import UUID, uuid4

from dynaprice.adaptadores.saida.postgres.conexao import Conexao


class RepositorioDeLotesPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def criar(self, hash_recomendacoes: str) -> UUID:
        self.criar_com_id(uuid4(), hash_recomendacoes)
        linha = self._conexao.execute(
            "SELECT id FROM core.lote_exportacao WHERE hash_recomendacoes = %s",
            (hash_recomendacoes,),
        ).fetchone()
        assert linha is not None
        lote: UUID = linha[0]
        return lote

    def criar_com_id(self, lote_id: UUID, hash_recomendacoes: str) -> None:
        self._conexao.execute(
            """INSERT INTO core.lote_exportacao (tenant_id, id, hash_recomendacoes)
               VALUES (core.tenant_atual(), %s, %s)
               ON CONFLICT (tenant_id, hash_recomendacoes) DO NOTHING""",
            (lote_id, hash_recomendacoes),
        )

    def hash_de(self, lote_id: UUID) -> str | None:
        linha = self._conexao.execute(
            "SELECT hash_recomendacoes FROM core.lote_exportacao WHERE id = %s", (lote_id,)
        ).fetchone()
        return None if linha is None else str(linha[0])

    def gravar_arquivo(self, lote_id: UUID, arquivo: bytes, sha256: str, agora: datetime) -> None:
        self._conexao.execute(
            """UPDATE core.lote_exportacao SET arquivo = %s, arquivo_sha256 = %s, gerado_em = %s
               WHERE id = %s""",
            (arquivo, sha256, agora, lote_id),
        )

    def arquivo(self, lote_id: UUID) -> bytes | None:
        linha = self._conexao.execute(
            "SELECT arquivo FROM core.lote_exportacao WHERE id = %s", (lote_id,)
        ).fetchone()
        return None if linha is None or linha[0] is None else bytes(linha[0])
