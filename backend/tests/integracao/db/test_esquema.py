"""F1.9: papéis, RLS forçada e migrações (RNF03). Tudo lido do catálogo."""

from typing import Any

import psycopg

from dynaprice.adaptadores.saida.postgres.migracoes import migrar
from tests.conftest import Banco

ESQUEMAS_COM_RLS = ("core", "raw", "job", "audit")
# Dado global (D-INDICE) e a própria raiz do inquilino, isolada pela coluna id.
SEM_TENANT_ID = {"core.indice_inflacao", "core.tenant"}


def _tabelas(conexao: psycopg.Connection[Any]) -> list[Any]:
    return conexao.execute(
        """SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE c.relkind = 'r' AND n.nspname = ANY(%s)""",
        (list(ESQUEMAS_COM_RLS),),
    ).fetchall()


def test_papel_da_aplicacao_nao_contorna_rls_nem_cria_objetos(banco: Banco) -> None:
    with psycopg.connect(banco.superusuario) as c:
        linha = c.execute(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = 'dynaprice_app'"
        ).fetchone()
        com_create = c.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' "
            "AND nspname <> 'information_schema' "
            "AND has_schema_privilege('dynaprice_app', oid, 'CREATE')"
        ).fetchall()
    assert linha == (False, False, False, False)
    assert com_create == []


def test_toda_tabela_tem_rls_forcada(banco: Banco) -> None:
    with psycopg.connect(banco.superusuario) as c:
        tabelas = _tabelas(c)
    assert len(tabelas) >= 15
    sem_rls = [f"{e}.{t}" for e, t, rls, forca in tabelas if not (rls and forca)]
    assert set(sem_rls) <= {"core.indice_inflacao"}


def test_toda_tabela_tem_tenant_id(banco: Banco) -> None:
    with psycopg.connect(banco.superusuario) as c:
        tabelas = {f"{e}.{t}" for e, t, *_ in _tabelas(c)}
        com_coluna = {
            f"{e}.{t}"
            for e, t in c.execute(
                "SELECT table_schema, table_name FROM information_schema.columns "
                "WHERE column_name = 'tenant_id' AND table_schema = ANY(%s)",
                (list(ESQUEMAS_COM_RLS),),
            ).fetchall()
        }
    assert tabelas - com_coluna == SEM_TENANT_ID


def test_aplicacao_nao_escreve_em_dado_global(banco: Banco) -> None:
    with psycopg.connect(banco.superusuario) as c:
        linha = c.execute(
            "SELECT has_table_privilege('dynaprice_app', 'core.indice_inflacao', 'INSERT'),"
            " has_table_privilege('dynaprice_app', 'core.indice_inflacao', 'SELECT')"
        ).fetchone()
    assert linha == (False, True)


def test_auditoria_nao_aceita_update_nem_delete_pela_aplicacao(banco: Banco) -> None:
    with psycopg.connect(banco.superusuario) as c:
        linha = c.execute(
            "SELECT has_table_privilege('dynaprice_app', 'audit.evento', 'UPDATE'),"
            " has_table_privilege('dynaprice_app', 'audit.evento', 'DELETE')"
        ).fetchone()
    assert linha == (False, False)


def test_migracao_e_idempotente(banco: Banco) -> None:
    migrar(banco.migrador)
