"""Limpeza conforme D6: cada DELETE é limitado ao inquilino (RLS ou filtro explícito)."""

from datetime import datetime
from uuid import UUID

from dynaprice.adaptadores.saida.postgres.conexao import Conexao


class RetencaoPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def apagar_raw_substituido(self, antes_de: datetime) -> int:
        self._conexao.execute(
            """DELETE FROM raw.quarentena q USING raw.extracao e
               WHERE q.tenant_id = e.tenant_id AND q.extracao_id = e.id
                 AND e.substituida AND e.extraido_em < %s""",
            (antes_de,),
        )
        cursor = self._conexao.execute(
            "DELETE FROM raw.extracao WHERE substituida AND extraido_em < %s", (antes_de,)
        )
        return cursor.rowcount

    def apagar_refresh_expirado(self, tenant_id: UUID, antes_de: datetime) -> int:
        cursor = self._conexao.execute(
            """DELETE FROM auth.refresh_token t USING auth.sessao_familia f
               WHERE t.familia_id = f.id AND f.tenant_id = %s AND t.expira_em < %s""",
            (tenant_id, antes_de),
        )
        return cursor.rowcount

    def apagar_cotacoes(self, antes_de: datetime) -> int:
        cursor = self._conexao.execute("DELETE FROM core.cotacao WHERE criada_em < %s", (antes_de,))
        return cursor.rowcount
