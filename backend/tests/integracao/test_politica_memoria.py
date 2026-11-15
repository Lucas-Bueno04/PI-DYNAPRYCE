"""F1.21: política em memória na api; NOTIFY perdido não deixa cotar com versão velha."""

from uuid import UUID

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres import EscutaDePoliticas, FabricaDeUnidadesPostgres
from dynaprice.aplicacao.politica_em_memoria import PoliticaEmMemoria
from tests.conftest import Banco
from tests.dominio.modelos.documentos import documento_tabela_7
from tests.fakes import RelogioFixo


@pytest.fixture
def fabrica(pool: ConnectionPool) -> FabricaDeUnidadesPostgres:
    return FabricaDeUnidadesPostgres(pool, RelogioFixo())


def _publicar(fabrica: FabricaDeUnidadesPostgres, tenant: UUID) -> int:
    with fabrica.para_tenant(tenant) as uow:
        versao = uow.politicas.salvar_rascunho(documento_tabela_7())
        uow.politicas.publicar(versao, None, RelogioFixo().agora())
    return versao


def test_sem_politica_publicada_retorna_none(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    with fabrica.para_tenant(novo_tenant) as uow:
        assert PoliticaEmMemoria().vigente(uow, novo_tenant) is None


def test_reaproveita_enquanto_a_versao_nao_muda(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    _publicar(fabrica, novo_tenant)
    memoria = PoliticaEmMemoria()
    with fabrica.para_tenant(novo_tenant) as uow:
        primeira = memoria.vigente(uow, novo_tenant)
    with fabrica.para_tenant(novo_tenant) as uow:
        segunda = memoria.vigente(uow, novo_tenant)
    assert primeira is segunda


def test_notify_perdido_a_requisicao_confere_a_versao(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    _publicar(fabrica, novo_tenant)
    memoria = PoliticaEmMemoria()
    with fabrica.para_tenant(novo_tenant) as uow:
        memoria.vigente(uow, novo_tenant)
    # Publicação nova sem ninguém escutando: nenhuma notificação chega à memória.
    _publicar(fabrica, novo_tenant)
    with fabrica.para_tenant(novo_tenant) as uow:
        atual = memoria.vigente(uow, novo_tenant)
    assert atual is not None
    assert atual.politica.versao == 2


def test_notify_entregue_invalida_a_memoria(
    banco: Banco, fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    memoria = PoliticaEmMemoria()
    with EscutaDePoliticas(banco.app, memoria) as escuta:
        _publicar(fabrica, novo_tenant)
        with fabrica.para_tenant(novo_tenant) as uow:
            memoria.vigente(uow, novo_tenant)
        assert memoria.versao_em_memoria(novo_tenant) == 1
        _publicar(fabrica, novo_tenant)
        assert escuta.processar(tempo_s=5) >= 1
    assert memoria.versao_em_memoria(novo_tenant) is None


def test_reconexao_descarta_tudo(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID, banco: Banco
) -> None:
    _publicar(fabrica, novo_tenant)
    memoria = PoliticaEmMemoria()
    with fabrica.para_tenant(novo_tenant) as uow:
        memoria.vigente(uow, novo_tenant)
    with EscutaDePoliticas(banco.app, memoria) as escuta:
        assert memoria.versao_em_memoria(novo_tenant) is None
        with psycopg.connect(banco.superusuario, autocommit=True) as s:
            s.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query LIKE 'LISTEN%%'"
            )
        with fabrica.para_tenant(novo_tenant) as uow:
            memoria.vigente(uow, novo_tenant)
        assert memoria.versao_em_memoria(novo_tenant) == 1
        escuta.processar(tempo_s=1)
        assert escuta.reconexoes == 1
        assert memoria.versao_em_memoria(novo_tenant) is None
