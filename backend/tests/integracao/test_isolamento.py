"""F1.11: isolamento entre inquilinos (RNF03), simulação mw9kw9i514upw:18.

A lista de tabelas vem do catálogo: uma tabela nova sem linha de semente faz o teste falhar.
"""

import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.errors import InsufficientPrivilege

from tests.conftest import Banco

GLOBAIS = {"core.indice_inflacao"}

SEMENTE = """
INSERT INTO core.empresa (tenant_id, id, regime) VALUES (%(t)s, 'E', 'LP');
INSERT INTO core.contrato (tenant_id, id, preco_vigente) VALUES (%(t)s, 'C', 1);
INSERT INTO core.vinculo (tenant_id, contrato_id, empresa_id, desde)
  VALUES (%(t)s, 'C', 'E', '2026-01-01');
INSERT INTO core.empresa_mes (tenant_id, empresa_id, competencia, versao_extracao, direcionadores)
  VALUES (%(t)s, 'E', '2026-01-01', 1, '{}');
INSERT INTO core.honorario_mes (tenant_id, contrato_id, competencia, valor_cobrado)
  VALUES (%(t)s, 'C', '2026-01-01', 1);
INSERT INTO core.politica_versao (tenant_id, versao, documento) VALUES (%(t)s, 1, '{}');
INSERT INTO core.preco_alvo (tenant_id, id, contrato_id, competencia, politica_versao,
    nivel_informacao, entradas, preco_alvo)
  VALUES (%(t)s, %(u)s, 'C', '2026-01-01', 1, 2, '{}', 1);
INSERT INTO core.lote_exportacao (tenant_id, id, hash_recomendacoes) VALUES (%(t)s, %(u)s, 'h');
INSERT INTO core.recomendacao (tenant_id, id, contrato_id, preco_alvo_id, politica_versao,
    competencia, preco_vigente, preco_proposto, data_efeito, trajetoria)
  VALUES (%(t)s, %(u)s, 'C', %(u)s, 1, '2026-01-01', 1, 2, '2026-03-01', '[]');
INSERT INTO core.divergencia_cobranca (tenant_id, contrato_id, competencia, aprovado, cobrado)
  VALUES (%(t)s, 'C', '2026-01-01', 1, 2);
INSERT INTO core.cotacao (tenant_id, regime, politica_versao, entradas, preco, decomposicao)
  VALUES (%(t)s, 'LP', 1, '{}', 1, '{}');
INSERT INTO core.conector_config (tenant_id, tipo) VALUES (%(t)s, 'dominio');
INSERT INTO core.alerta (tenant_id, tipo, referencia) VALUES (%(t)s, 'x', 'y');
INSERT INTO raw.extracao (tenant_id, id, fonte, competencia, versao, origem, hash_conteudo,
    conteudo, extraido_em)
  VALUES (%(t)s, %(u)s, 'dominio', '2026-01-01', 1, 'conector', 'h', '{}', now());
INSERT INTO raw.quarentena (tenant_id, extracao_id, linha, motivo)
  VALUES (%(t)s, %(u)s, '{}', 'm');
INSERT INTO job.job (tenant_id, tipo, chave_idempotencia, proxima_tentativa_em)
  VALUES (%(t)s, 'x', 'k', now());
INSERT INTO audit.evento VALUES (%(t)s, 1, NULL, NULL, 't', '{}', now(), '', '');
"""


def _tabelas_do_catalogo(conexao: psycopg.Connection[tuple[str, str]]) -> list[str]:
    linhas = conexao.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' AND table_schema = ANY(%s)",
        (["core", "raw", "job", "audit"],),
    ).fetchall()
    return sorted({f"{e}.{t}" for e, t in linhas} - GLOBAIS)


@pytest.fixture
def tenant_b(banco: Banco, novo_tenant: UUID) -> UUID:
    with psycopg.connect(banco.superusuario) as c:
        for comando in filter(str.strip, SEMENTE.split(";\n")):
            c.execute(comando.encode(), _p(novo_tenant))
    return novo_tenant


_UUIDS: dict[UUID, UUID] = {}


def _p(tenant: UUID) -> dict[str, UUID]:
    return {"t": tenant, "u": _UUIDS.setdefault(tenant, uuid4())}


@pytest.fixture
def app_no_tenant_a(banco: Banco) -> Iterator[psycopg.Connection[tuple[int]]]:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        tenant_a = uuid4()
        s.execute("INSERT INTO core.tenant (id, nome) VALUES (%s, 'A')", (tenant_a,))
    with psycopg.connect(banco.app) as conexao:
        conexao.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_a),))
        conexao.commit()
        yield conexao


def _identificador(tabela: str) -> sql.Identifier:
    esquema, nome = tabela.split(".")
    return sql.Identifier(esquema, nome)


def test_passo2_leitura_do_outro_tenant_nao_retorna_linhas(
    banco: Banco, tenant_b: UUID, app_no_tenant_a: psycopg.Connection[tuple[int]]
) -> None:
    with psycopg.connect(banco.superusuario) as s:
        tabelas = _tabelas_do_catalogo(s)
        vazias = [
            t
            for t in tabelas
            if t != "core.tenant"
            and s.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s").format(_identificador(t)),
                (tenant_b,),
            ).fetchone()
            == (0,)
        ]
    assert vazias == [], "tabela nova sem semente de teste"
    for tabela in tabelas:
        coluna = sql.Identifier("id" if tabela == "core.tenant" else "tenant_id")
        linha = app_no_tenant_a.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE {} = %s").format(_identificador(tabela), coluna),
            (tenant_b,),
        ).fetchone()
        assert linha == (0,), tabela
    app_no_tenant_a.rollback()


def _pode(conexao: psycopg.Connection[tuple[bool]], tabela: str, privilegio: str) -> bool:
    linha = conexao.execute(
        "SELECT has_table_privilege('dynaprice_app', %s, %s)", (tabela, privilegio)
    ).fetchone()
    return bool(linha and linha[0])


def test_passo3_escrita_no_outro_tenant_e_recusada(
    banco: Banco, tenant_b: UUID, app_no_tenant_a: psycopg.Connection[tuple[int]]
) -> None:
    with psycopg.connect(banco.superusuario) as s:
        tabelas = [t for t in _tabelas_do_catalogo(s) if t != "core.tenant"]
        amostras = {
            t: s.execute(
                sql.SQL("SELECT to_json(x) FROM {} x WHERE tenant_id = %s LIMIT 1").format(
                    _identificador(t)
                ),
                (tenant_b,),
            ).fetchone()
            for t in tabelas
        }
    for tabela, amostra in amostras.items():
        assert amostra is not None
        with pytest.raises(InsufficientPrivilege):
            app_no_tenant_a.execute(
                sql.SQL("INSERT INTO {t} SELECT * FROM json_populate_record(null::{t}, %s)").format(
                    t=_identificador(tabela)
                ),
                (json.dumps(amostra[0]),),
            )
        app_no_tenant_a.rollback()


def test_alterar_e_apagar_no_outro_tenant_nao_afetam_linhas(
    banco: Banco, tenant_b: UUID, app_no_tenant_a: psycopg.Connection[tuple[int]]
) -> None:
    with psycopg.connect(banco.superusuario) as s:
        tabelas = [t for t in _tabelas_do_catalogo(s) if t != "core.tenant"]
        privilegios = {t: (_pode(s, t, "UPDATE"), _pode(s, t, "DELETE")) for t in tabelas}
    for tabela, (pode_alterar, pode_apagar) in privilegios.items():
        alvo = _identificador(tabela)
        if pode_alterar and tabela != "raw.extracao":
            cursor = app_no_tenant_a.execute(
                sql.SQL("UPDATE {} SET tenant_id = tenant_id WHERE tenant_id = %s").format(alvo),
                (tenant_b,),
            )
            assert cursor.rowcount == 0, tabela
        if pode_apagar:
            cursor = app_no_tenant_a.execute(
                sql.SQL("DELETE FROM {} WHERE tenant_id = %s").format(alvo), (tenant_b,)
            )
            assert cursor.rowcount == 0, tabela
    app_no_tenant_a.rollback()


def test_passo4_sem_tenant_definido_nada_aparece(banco: Banco, tenant_b: UUID) -> None:
    with psycopg.connect(banco.app) as conexao:
        linha = conexao.execute("SELECT count(*) FROM core.contrato").fetchone()
    assert linha == (0,)


def test_passo5_toda_tabela_coberta(banco: Banco) -> None:
    with psycopg.connect(banco.superusuario) as s:
        linha = s.execute(
            """SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE c.relkind = 'r' AND n.nspname = ANY(%s)
                 AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
                 AND n.nspname || '.' || c.relname <> ALL(%s)""",
            (["core", "raw", "job", "audit"], list(GLOBAIS)),
        ).fetchone()
    assert linha == (0,)
