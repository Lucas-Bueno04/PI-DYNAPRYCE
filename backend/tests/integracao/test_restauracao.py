"""F1.39: restauração do backup reproduz a última recomendação e a cadeia de auditoria."""

from uuid import UUID

import psycopg
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from dynaprice.aplicacao.casos_de_uso.decidir import Aprovar, DecidirRecomendacao
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco
from tests.conftest import Banco
from tests.fakes import RelogioFixo


def _rodar(banco: Banco, *comando: str) -> None:
    saida = banco.conteiner.exec(list(comando))
    assert saida.exit_code == 0, saida.output.decode(errors="replace")


def test_restaurar_reproduz_recomendacao_e_cadeia(preco: CenarioDePreco, banco: Banco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)
    (linha,) = preco.consulta("SELECT id FROM core.recomendacao WHERE tenant_id=%s", preco.tenant)
    DecidirRecomendacao(preco.fabrica, preco.relogio).executar(
        preco.aprovador, linha[0], 1, Aprovar()
    )
    usuario = banco.conteiner.username
    _rodar(banco, "pg_dump", "-U", usuario, "-d", "dynaprice", "-Fc", "-f", "/tmp/backup.dump")
    _rodar(banco, "dropdb", "-U", usuario, "--if-exists", "restaurado")
    _rodar(banco, "createdb", "-U", usuario, "-O", "dynaprice_migrador", "restaurado")
    _rodar(banco, "pg_restore", "-U", usuario, "-d", "restaurado", "/tmp/backup.dump")
    url = banco.app.rsplit("/", 1)[0] + "/restaurado"
    tenant: UUID = preco.tenant
    with ConnectionPool(url, min_size=1, max_size=1, open=True) as pool:
        fabrica = FabricaDeUnidadesPostgres(pool, RelogioFixo())
        with fabrica.para_tenant(tenant) as uow:
            recomendacoes = uow.recomendacoes.listar()
            quebra = uow.auditoria.primeira_quebra()
    assert [(r.estado.value, str(r.preco_proposto)) for r in recomendacoes] == [
        ("aprovada", "502.55")
    ]
    assert quebra is None
    original = preco.consulta(
        "SELECT seq, hash FROM audit.evento WHERE tenant_id=%s ORDER BY seq", tenant
    )
    with psycopg.connect(banco.superusuario.rsplit("/", 1)[0] + "/restaurado") as s:
        restaurado = s.execute(
            "SELECT seq, hash FROM audit.evento WHERE tenant_id=%s ORDER BY seq", (tenant,)
        ).fetchall()
    assert restaurado == original
    # RLS continua valendo depois da restauração.
    with psycopg.connect(url) as app:
        assert app.execute("SELECT count(*) FROM core.recomendacao").fetchone() == (0,)
