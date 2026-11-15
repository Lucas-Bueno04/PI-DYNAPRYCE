"""F1.40: regras de retenção da decisão D6, como job."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from dynaprice.aplicacao.casos_de_uso.conectores import AgendarCiclo
from dynaprice.aplicacao.casos_de_uso.retencao import AplicarRetencao
from dynaprice.aplicacao.portas import JobReservado
from tests.conftest import Banco
from tests.fakes import RelogioFixo

AGORA = datetime(2027, 2, 10, 12, tzinfo=UTC)


def _dias(n: int) -> datetime:
    return AGORA - timedelta(days=n)


def _extracao(
    s: psycopg.Connection[tuple[object, ...]],
    tenant: UUID,
    versao: int,
    antiga: bool,
    substituida: bool,
) -> UUID:
    identificador = uuid4()
    s.execute(
        """INSERT INTO raw.extracao (tenant_id, id, fonte, competencia, versao, origem,
               hash_conteudo, conteudo, substituida, extraido_em)
           VALUES (%s, %s, 'f', '2024-01-01', %s, 'conector', %s, '{}', %s, %s)""",
        (
            tenant,
            identificador,
            versao,
            str(identificador),
            substituida,
            _dias(800 if antiga else 10),
        ),
    )
    return identificador


def _aplicar(pool: ConnectionPool, tenant: UUID) -> dict[str, int]:
    fabrica = FabricaDeUnidadesPostgres(pool, RelogioFixo(AGORA))
    job = JobReservado(uuid4(), tenant, "retencao", {}, 1)
    return AplicarRetencao(fabrica, RelogioFixo(AGORA)).executar(job)


def test_raw_substituido_ha_mais_de_24_meses_sai_e_o_vigente_fica(
    banco: Banco, pool: ConnectionPool, novo_tenant: UUID
) -> None:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        velha = _extracao(s, novo_tenant, 1, antiga=True, substituida=True)
        s.execute(
            "INSERT INTO raw.quarentena (tenant_id, extracao_id, linha, motivo) "
            "VALUES (%s, %s, '{}', 'm')",
            (novo_tenant, velha),
        )
        recente = _extracao(s, novo_tenant, 2, antiga=False, substituida=True)
        vigente_antiga = _extracao(s, novo_tenant, 3, antiga=True, substituida=False)
    resultado = _aplicar(pool, novo_tenant)
    assert resultado["raw"] == 1
    with psycopg.connect(banco.superusuario) as s:
        linhas = s.execute(
            "SELECT id FROM raw.extracao WHERE tenant_id=%s", (novo_tenant,)
        ).fetchall()
    assert {linha[0] for linha in linhas} == {recente, vigente_antiga}


def test_refresh_expirado_ha_30_dias_sai(
    banco: Banco, pool: ConnectionPool, novo_tenant: UUID
) -> None:
    usuario = uuid4()
    familia = uuid4()
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute(
            "INSERT INTO auth.usuario (id, email, senha_argon2id) VALUES (%s, %s, 'h')",
            (usuario, f"{usuario}@t.com"),
        )
        s.execute(
            """INSERT INTO auth.sessao_familia (id, usuario_id, tenant_id, criada_em,
                   ultima_atividade, expira_em) VALUES (%s, %s, %s, %s, %s, %s)""",
            (familia, usuario, novo_tenant, _dias(60), _dias(60), _dias(40)),
        )
        for hash_, expira in ((b"velho", _dias(31)), (b"novo", _dias(5))):
            s.execute(
                """INSERT INTO auth.refresh_token (hash_sha256, familia_id, emitido_em, expira_em)
                   VALUES (%s, %s, %s, %s)""",
                (hash_ + usuario.bytes, familia, _dias(60), expira),
            )
    assert _aplicar(pool, novo_tenant)["refresh"] == 1


def test_cotacao_com_mais_de_12_meses_sai(
    banco: Banco, pool: ConnectionPool, novo_tenant: UUID
) -> None:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute(
            "INSERT INTO core.politica_versao (tenant_id, versao, documento) VALUES (%s, 1, '{}')",
            (novo_tenant,),
        )
        for criada in (_dias(400), _dias(30)):
            s.execute(
                """INSERT INTO core.cotacao (tenant_id, regime, politica_versao, entradas, preco,
                       decomposicao, criada_em) VALUES (%s, 'LP', 1, '{}', 1, '{}', %s)""",
                (novo_tenant, criada),
            )
    assert _aplicar(pool, novo_tenant)["cotacoes"] == 1


def test_auditoria_nunca_e_apagada_pela_aplicacao(
    banco: Banco, pool: ConnectionPool, novo_tenant: UUID
) -> None:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute(
            "INSERT INTO audit.evento VALUES (%s, 1, NULL, NULL, 't', '{}', %s, '', '')",
            (novo_tenant, _dias(365 * 10)),
        )
    resultado = _aplicar(pool, novo_tenant)
    assert "auditoria" not in resultado
    with psycopg.connect(banco.superusuario) as s:
        linha = s.execute(
            "SELECT count(*), has_table_privilege('dynaprice_app', 'audit.evento', 'DELETE') "
            "FROM audit.evento WHERE tenant_id = %s AND seq = 1",
            (novo_tenant,),
        ).fetchone()
    assert linha == (1, False)


def test_retencao_e_agendada_uma_vez_por_mes(
    banco: Banco, pool: ConnectionPool, novo_tenant: UUID
) -> None:
    relogio = RelogioFixo(datetime(2027, 3, 6, 12, tzinfo=UTC))
    agenda = AgendarCiclo(FabricaDeUnidadesPostgres(pool, relogio), relogio)
    agenda.executar(novo_tenant)
    agenda.executar(novo_tenant)
    with psycopg.connect(banco.superusuario) as s:
        linhas = s.execute(
            "SELECT chave_idempotencia FROM job.job WHERE tenant_id=%s", (novo_tenant,)
        ).fetchall()
    assert linhas == [("retencao:2027-03",)]
