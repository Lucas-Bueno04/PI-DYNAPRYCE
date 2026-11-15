"""Usuários e papéis do esquema auth (fora da RLS por inquilino, ADR-002)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.dominio.modelos.autenticacao import Papel, Usuario

_COLUNAS = (
    "id, email, senha_argon2id, totp_cifrado, totp_ultimo_passo, mfa_ativo, ativo, "
    "falhas_login, bloqueado_ate"
)


def _usuario(linha: tuple[Any, ...]) -> Usuario:
    identificador, email, senha, totp, passo, mfa, ativo, falhas, bloqueado = linha
    return Usuario(
        identificador,
        email,
        senha,
        None if totp is None else bytes(totp),
        passo,
        mfa,
        ativo,
        falhas,
        bloqueado,
    )


class RepositorioDeUsuariosPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def obter(self, usuario_id: UUID) -> Usuario | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS} FROM auth.usuario WHERE id = %s", (usuario_id,)
        ).fetchone()
        return None if linha is None else _usuario(linha)

    def obter_travado(self, usuario_id: UUID) -> Usuario | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS} FROM auth.usuario WHERE id = %s FOR UPDATE", (usuario_id,)
        ).fetchone()
        return None if linha is None else _usuario(linha)

    def obter_por_email(self, email: str) -> Usuario | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS} FROM auth.usuario WHERE lower(email) = lower(%s)", (email,)
        ).fetchone()
        return None if linha is None else _usuario(linha)

    def criar(self, usuario: Usuario) -> None:
        self._conexao.execute(
            """INSERT INTO auth.usuario (id, email, senha_argon2id, totp_cifrado,
                   totp_ultimo_passo, mfa_ativo, ativo, falhas_login, bloqueado_ate)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                usuario.id,
                usuario.email,
                usuario.senha_hash,
                usuario.totp_cifrado,
                usuario.totp_ultimo_passo,
                usuario.mfa_ativo,
                usuario.ativo,
                usuario.falhas_login,
                usuario.bloqueado_ate,
            ),
        )

    def registrar_falha_login(self, usuario_id: UUID) -> int:
        linha = self._conexao.execute(
            "UPDATE auth.usuario SET falhas_login = falhas_login + 1 WHERE id = %s "
            "RETURNING falhas_login",
            (usuario_id,),
        ).fetchone()
        return 0 if linha is None else int(linha[0])

    def bloquear(self, usuario_id: UUID, ate: datetime) -> None:
        self._conexao.execute(
            "UPDATE auth.usuario SET bloqueado_ate = %s WHERE id = %s", (ate, usuario_id)
        )

    def zerar_falhas(self, usuario_id: UUID) -> None:
        self._conexao.execute(
            "UPDATE auth.usuario SET falhas_login = 0, bloqueado_ate = NULL WHERE id = %s",
            (usuario_id,),
        )

    def trocar_hash_se_igual(self, usuario_id: UUID, antigo: str, novo: str) -> None:
        self._conexao.execute(
            "UPDATE auth.usuario SET senha_argon2id = %s WHERE id = %s AND senha_argon2id = %s",
            (novo, usuario_id, antigo),
        )

    def registrar_passo_totp(self, usuario_id: UUID, passo: int) -> bool:
        cursor = self._conexao.execute(
            """UPDATE auth.usuario SET totp_ultimo_passo = %s
               WHERE id = %s AND (totp_ultimo_passo IS NULL OR totp_ultimo_passo < %s)""",
            (passo, usuario_id, passo),
        )
        return cursor.rowcount == 1

    def iniciar_cadastro_mfa(self, usuario_id: UUID, totp_cifrado: bytes) -> None:
        self._conexao.execute(
            "UPDATE auth.usuario SET totp_cifrado = %s WHERE id = %s AND NOT mfa_ativo",
            (totp_cifrado, usuario_id),
        )

    def ativar_mfa(self, usuario_id: UUID, passo: int, totp_verificado: bytes) -> bool:
        cursor = self._conexao.execute(
            """UPDATE auth.usuario SET mfa_ativo = true, totp_ultimo_passo = %s
               WHERE id = %s AND NOT mfa_ativo AND totp_cifrado = %s""",
            (passo, usuario_id, totp_verificado),
        )
        return cursor.rowcount == 1

    def desligar_mfa(self, usuario_id: UUID) -> None:
        self._conexao.execute(
            """UPDATE auth.usuario SET mfa_ativo = false, totp_cifrado = NULL,
                   totp_ultimo_passo = NULL WHERE id = %s""",
            (usuario_id,),
        )

    def desativar(self, usuario_id: UUID) -> None:
        self._conexao.execute("UPDATE auth.usuario SET ativo = false WHERE id = %s", (usuario_id,))

    def redefinir_senha(self, usuario_id: UUID, senha_hash: str) -> None:
        self._conexao.execute(
            """UPDATE auth.usuario SET senha_argon2id = %s, falhas_login = 0,
                   bloqueado_ate = NULL WHERE id = %s""",
            (senha_hash, usuario_id),
        )

    def papeis(self, usuario_id: UUID, tenant_id: UUID) -> frozenset[Papel]:
        linhas = self._conexao.execute(
            "SELECT papel FROM auth.usuario_papel WHERE usuario_id = %s AND tenant_id = %s",
            (usuario_id, tenant_id),
        ).fetchall()
        return frozenset(Papel(linha[0]) for linha in linhas)

    def inquilinos(self, usuario_id: UUID) -> Sequence[UUID]:
        linhas = self._conexao.execute(
            "SELECT DISTINCT tenant_id FROM auth.usuario_papel WHERE usuario_id = %s "
            "ORDER BY tenant_id",
            (usuario_id,),
        ).fetchall()
        return [linha[0] for linha in linhas]

    def definir_papeis(self, usuario_id: UUID, tenant_id: UUID, papeis: frozenset[Papel]) -> None:
        self._conexao.execute(
            "DELETE FROM auth.usuario_papel WHERE usuario_id = %s AND tenant_id = %s",
            (usuario_id, tenant_id),
        )
        for papel in sorted(papeis):
            self._conexao.execute(
                "INSERT INTO auth.usuario_papel (usuario_id, tenant_id, papel) VALUES (%s, %s, %s)",
                (usuario_id, tenant_id, papel.value),
            )

    def listar_do_inquilino(self, tenant_id: UUID) -> Sequence[Usuario]:
        colunas = ", ".join(f"u.{coluna}" for coluna in _COLUNAS.split(", "))
        linhas = self._conexao.execute(
            f"""SELECT DISTINCT {colunas} FROM auth.usuario u
                JOIN auth.usuario_papel p ON p.usuario_id = u.id
                WHERE p.tenant_id = %s ORDER BY u.email""",
            (tenant_id,),
        ).fetchall()
        return [_usuario(linha) for linha in linhas]

    def existe_administrador(self) -> bool:
        linha = self._conexao.execute(
            "SELECT EXISTS (SELECT 1 FROM auth.usuario_papel WHERE papel = 'administrar')"
        ).fetchone()
        return bool(linha and linha[0])

    def criar_inquilino(self, tenant_id: UUID, nome: str) -> None:
        self._conexao.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        self._conexao.execute(
            "INSERT INTO core.tenant (id, nome) VALUES (%s, %s)", (tenant_id, nome)
        )

    def inquilinos_ativos(self) -> Sequence[UUID]:
        linhas = self._conexao.execute("SELECT job.listar_tenants_ativos()").fetchall()
        return [linha[0] for linha in linhas]

    def com_totp(self) -> Sequence[tuple[UUID, bytes]]:
        linhas = self._conexao.execute(
            "SELECT id, totp_cifrado FROM auth.usuario WHERE totp_cifrado IS NOT NULL"
        ).fetchall()
        return [(linha[0], bytes(linha[1])) for linha in linhas]

    def trocar_totp(self, usuario_id: UUID, totp_cifrado: bytes) -> None:
        self._conexao.execute(
            "UPDATE auth.usuario SET totp_cifrado = %s WHERE id = %s", (totp_cifrado, usuario_id)
        )
