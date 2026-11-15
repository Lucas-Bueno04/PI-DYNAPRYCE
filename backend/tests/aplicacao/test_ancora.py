"""F3.5: a cadeia verificada contra a âncora detecta a alteração de um evento (RNF06)."""

from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from dynaprice.adaptadores.saida.arquivos.ancora import AncoraEmArquivo
from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from dynaprice.aplicacao.casos_de_uso.ancora import (
    AncorarAuditoria,
    ResultadoDaVerificacao,
    VerificarAuditoria,
)
from tests.conftest import Banco
from tests.fakes import RelogioFixo


@pytest.fixture
def ancora(tmp_path: Path) -> AncoraEmArquivo:
    return AncoraEmArquivo(tmp_path / "ancoras.jsonl")


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo()


def _eventos(fabrica: FabricaDeUnidadesPostgres, tenant: UUID, de: int, ate: int) -> None:
    for n in range(de, ate):
        with fabrica.para_tenant(tenant) as uow:
            uow.auditoria.registrar("evento", {"n": n})


def _veredito(
    fabrica: FabricaDeUnidadesPostgres, ancora: AncoraEmArquivo, tenant: UUID
) -> ResultadoDaVerificacao:
    resultados = VerificarAuditoria(fabrica, ancora).executar()
    (resultado,) = [r for r in resultados if r.tenant_id == tenant]
    return resultado


def test_ancora_registra_a_cabeca_e_nao_repete_sem_novidade(
    fabrica: FabricaDeUnidadesPostgres,
    novo_tenant: UUID,
    ancora: AncoraEmArquivo,
    relogio: RelogioFixo,
) -> None:
    _eventos(fabrica, novo_tenant, 0, 3)
    caso = AncorarAuditoria(fabrica, ancora, relogio)
    assert caso.executar() >= 1
    (registrada,) = [a for a in ancora.listar(novo_tenant)]
    assert registrada.seq == 3 and len(registrada.hash_hex) == 64
    assert caso.executar() == 0  # nada novo desde a última âncora
    _eventos(fabrica, novo_tenant, 3, 5)
    caso.executar()
    assert [a.seq for a in ancora.listar(novo_tenant)] == [3, 5]


def test_cadeia_integra_confere_com_a_ancora(
    fabrica: FabricaDeUnidadesPostgres,
    novo_tenant: UUID,
    ancora: AncoraEmArquivo,
    relogio: RelogioFixo,
) -> None:
    _eventos(fabrica, novo_tenant, 0, 4)
    AncorarAuditoria(fabrica, ancora, relogio).executar()
    r = _veredito(fabrica, ancora, novo_tenant)
    assert (r.integro, r.quebra_interna, r.divergencias) == (True, None, ())


def test_alterar_evento_e_detectado(
    banco: Banco,
    fabrica: FabricaDeUnidadesPostgres,
    novo_tenant: UUID,
    ancora: AncoraEmArquivo,
    relogio: RelogioFixo,
) -> None:
    _eventos(fabrica, novo_tenant, 0, 4)
    AncorarAuditoria(fabrica, ancora, relogio).executar()
    with psycopg.connect(banco.superusuario) as s:
        s.execute(
            "UPDATE audit.evento SET conteudo = '{\"n\": 99}' WHERE tenant_id = %s AND seq = 2",
            (novo_tenant,),
        )
    r = _veredito(fabrica, ancora, novo_tenant)
    assert r.integro is False and r.quebra_interna == 2


def test_cadeia_reescrita_de_forma_consistente_so_a_ancora_denuncia(
    banco: Banco,
    fabrica: FabricaDeUnidadesPostgres,
    novo_tenant: UUID,
    ancora: AncoraEmArquivo,
    relogio: RelogioFixo,
) -> None:
    """Quem apaga do evento 3 em diante e reescreve com o mesmo mecanismo refaz os hashes."""
    _eventos(fabrica, novo_tenant, 0, 4)
    AncorarAuditoria(fabrica, ancora, relogio).executar()
    with psycopg.connect(banco.superusuario) as s:
        s.execute("DELETE FROM audit.evento WHERE tenant_id = %s AND seq >= 3", (novo_tenant,))
    _eventos(fabrica, novo_tenant, 100, 102)  # seq 3 e 4 com outro conteúdo, cadeia consistente
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.auditoria.primeira_quebra() is None  # a cadeia sozinha não vê nada
    r = _veredito(fabrica, ancora, novo_tenant)
    assert r.integro is False and r.quebra_interna is None
    assert [d.seq for d in r.divergencias] == [4]


def test_evento_ancorado_que_sumiu_e_detectado(
    banco: Banco,
    fabrica: FabricaDeUnidadesPostgres,
    novo_tenant: UUID,
    ancora: AncoraEmArquivo,
    relogio: RelogioFixo,
) -> None:
    _eventos(fabrica, novo_tenant, 0, 3)
    AncorarAuditoria(fabrica, ancora, relogio).executar()
    with psycopg.connect(banco.superusuario) as s:
        s.execute("DELETE FROM audit.evento WHERE tenant_id = %s AND seq = 3", (novo_tenant,))
    r = _veredito(fabrica, ancora, novo_tenant)
    assert r.integro is False and [d.seq for d in r.divergencias] == [3]
