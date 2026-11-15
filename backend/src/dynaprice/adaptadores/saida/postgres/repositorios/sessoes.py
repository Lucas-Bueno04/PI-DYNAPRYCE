"""Sessões, recuperação e limite por IP do esquema auth."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.dominio.modelos.autenticacao import RegistroDeRefresh


class RepositorioDeSessoesPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def criar_familia(
        self,
        usuario_id: UUID,
        tenant_id: UUID,
        mfa_verificado: bool,
        agora: datetime,
        expira_em: datetime,
    ) -> UUID:
        linha = self._conexao.execute(
            """INSERT INTO auth.sessao_familia (usuario_id, tenant_id, mfa_verificado, criada_em,
                   ultima_atividade, expira_em)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (usuario_id, tenant_id, mfa_verificado, agora, agora, expira_em),
        ).fetchone()
        assert linha is not None
        familia: UUID = linha[0]
        return familia

    def registrar_token(
        self, hash_sha256: bytes, familia_id: UUID, agora: datetime, expira_em: datetime
    ) -> None:
        self._conexao.execute(
            """INSERT INTO auth.refresh_token (hash_sha256, familia_id, emitido_em, expira_em)
               VALUES (%s, %s, %s, %s)""",
            (hash_sha256, familia_id, agora, expira_em),
        )

    def travar_token(self, hash_sha256: bytes) -> RegistroDeRefresh | None:
        # A trava serializa renovações concorrentes do mesmo token.
        linha = self._conexao.execute(
            """SELECT t.hash_sha256, f.id, f.usuario_id, f.tenant_id, f.mfa_verificado,
                      t.usado_em, t.expira_em, f.expira_em, f.revogada_em
               FROM auth.refresh_token t JOIN auth.sessao_familia f ON f.id = t.familia_id
               WHERE t.hash_sha256 = %s FOR UPDATE""",
            (hash_sha256,),
        ).fetchone()
        return None if linha is None else RegistroDeRefresh(bytes(linha[0]), *linha[1:])

    def marcar_usado(self, hash_sha256: bytes, familia_id: UUID, agora: datetime) -> None:
        self._conexao.execute(
            "UPDATE auth.refresh_token SET usado_em = %s WHERE hash_sha256 = %s",
            (agora, hash_sha256),
        )
        self._conexao.execute(
            "UPDATE auth.sessao_familia SET ultima_atividade = %s WHERE id = %s",
            (agora, familia_id),
        )

    def revogar_familia(self, familia_id: UUID, agora: datetime, motivo: str) -> None:
        self._conexao.execute(
            """UPDATE auth.sessao_familia SET revogada_em = %s, motivo_revogacao = %s
               WHERE id = %s AND revogada_em IS NULL""",
            (agora, motivo, familia_id),
        )

    def revogar_no_inquilino(
        self, usuario_id: UUID, tenant_id: UUID, agora: datetime, motivo: str
    ) -> None:
        self._conexao.execute(
            """UPDATE auth.sessao_familia SET revogada_em = %s, motivo_revogacao = %s
               WHERE usuario_id = %s AND tenant_id = %s AND revogada_em IS NULL""",
            (agora, motivo, usuario_id, tenant_id),
        )

    def revogar_do_usuario(self, usuario_id: UUID, agora: datetime, motivo: str) -> None:
        self._conexao.execute(
            """UPDATE auth.sessao_familia SET revogada_em = %s, motivo_revogacao = %s
               WHERE usuario_id = %s AND revogada_em IS NULL""",
            (agora, motivo, usuario_id),
        )


class RepositorioDeRecuperacaoPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def substituir_codigos(self, usuario_id: UUID, codigos: Sequence[tuple[UUID, str]]) -> None:
        self._conexao.execute(
            "DELETE FROM auth.codigo_recuperacao WHERE usuario_id = %s", (usuario_id,)
        )
        for codigo_id, hash_argon in codigos:
            self._conexao.execute(
                """INSERT INTO auth.codigo_recuperacao (id, usuario_id, hash_argon2id)
                   VALUES (%s, %s, %s)""",
                (codigo_id, usuario_id, hash_argon),
            )

    def hash_do_codigo(self, usuario_id: UUID, codigo_id: UUID) -> str | None:
        linha = self._conexao.execute(
            """SELECT hash_argon2id FROM auth.codigo_recuperacao
               WHERE id = %s AND usuario_id = %s AND usado_em IS NULL""",
            (codigo_id, usuario_id),
        ).fetchone()
        return None if linha is None else str(linha[0])

    def consumir_codigo(self, codigo_id: UUID, agora: datetime) -> bool:
        cursor = self._conexao.execute(
            "UPDATE auth.codigo_recuperacao SET usado_em = %s WHERE id = %s AND usado_em IS NULL",
            (agora, codigo_id),
        )
        return cursor.rowcount == 1

    def invalidar_redefinicoes(self, usuario_id: UUID) -> None:
        self._conexao.execute(
            "DELETE FROM auth.redefinicao_senha WHERE usuario_id = %s", (usuario_id,)
        )

    def criar_redefinicao(self, hash_sha256: bytes, usuario_id: UUID, expira_em: datetime) -> None:
        self._conexao.execute(
            """INSERT INTO auth.redefinicao_senha (hash_sha256, usuario_id, expira_em)
               VALUES (%s, %s, %s)""",
            (hash_sha256, usuario_id, expira_em),
        )

    def consumir_redefinicao(self, hash_sha256: bytes, agora: datetime) -> UUID | None:
        linha = self._conexao.execute(
            """UPDATE auth.redefinicao_senha SET usado_em = %s
               WHERE hash_sha256 = %s AND usado_em IS NULL AND expira_em > %s
               RETURNING usuario_id""",
            (agora, hash_sha256, agora),
        ).fetchone()
        return None if linha is None else linha[0]


class LimiteDeTentativasPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def bloqueado_ate(self, ip_hash: bytes) -> datetime | None:
        linha = self._conexao.execute(
            "SELECT bloqueado_ate FROM auth.limite_ip WHERE ip_hash = %s", (ip_hash,)
        ).fetchone()
        return None if linha is None else linha[0]

    def registrar_falha(self, ip_hash: bytes, agora: datetime, desde: datetime) -> int:
        linha = self._conexao.execute(
            """INSERT INTO auth.limite_ip AS l (ip_hash, falhas, atualizado_em) VALUES (%s, 1, %s)
               ON CONFLICT (ip_hash) DO UPDATE SET
                   falhas = CASE WHEN l.atualizado_em < %s THEN 1 ELSE l.falhas + 1 END,
                   atualizado_em = EXCLUDED.atualizado_em
               RETURNING falhas""",
            (ip_hash, agora, desde),
        ).fetchone()
        assert linha is not None
        return int(linha[0])

    def bloquear(self, ip_hash: bytes, ate: datetime) -> None:
        self._conexao.execute(
            "UPDATE auth.limite_ip SET bloqueado_ate = %s WHERE ip_hash = %s", (ate, ip_hash)
        )
