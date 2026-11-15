"""F1.12: trilha de auditoria encadeada por hash (RNF06)."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import psycopg

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from tests.conftest import Banco


def _registrar(fabrica: FabricaDeUnidadesPostgres, tenant: UUID, n: int) -> None:
    with fabrica.para_tenant(tenant) as uow:
        uow.auditoria.registrar("evento", {"n": n, "valor": "502.55"})


def test_cadeia_integra_e_verificavel(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    for n in range(3):
        _registrar(fabrica, novo_tenant, n)
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.auditoria.primeira_quebra() is None


def test_alterar_evento_quebra_a_cadeia(
    banco: Banco, fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    for n in range(3):
        _registrar(fabrica, novo_tenant, n)
    with psycopg.connect(banco.superusuario) as s:
        s.execute(
            """UPDATE audit.evento SET conteudo = '{"n": 99}'
               WHERE tenant_id = %s AND seq = 2""",
            (novo_tenant,),
        )
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.auditoria.primeira_quebra() == 2


def test_apagar_evento_do_meio_quebra_a_cadeia(
    banco: Banco, fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    for n in range(3):
        _registrar(fabrica, novo_tenant, n)
    with psycopg.connect(banco.superusuario) as s:
        s.execute("DELETE FROM audit.evento WHERE tenant_id = %s AND seq = 2", (novo_tenant,))
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.auditoria.primeira_quebra() == 3


def test_escritores_concorrentes_nao_bifurcam(
    banco: Banco, fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    with ThreadPoolExecutor(6) as executor:
        list(executor.map(lambda n: _registrar(fabrica, novo_tenant, n), range(40)))
    with psycopg.connect(banco.superusuario) as s:
        linhas = s.execute(
            "SELECT seq FROM audit.evento WHERE tenant_id = %s ORDER BY seq", (novo_tenant,)
        ).fetchall()
    assert [linha[0] for linha in linhas] == list(range(1, 41))
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.auditoria.primeira_quebra() is None
