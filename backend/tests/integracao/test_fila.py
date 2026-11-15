"""F1.13: fila de jobs e simulação mw9kw9i514upw:19 (worker que morre no meio do job)."""

from collections.abc import Iterator
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.entrada.worker import LacoDoWorker
from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres, FilaPostgres
from dynaprice.aplicacao.portas import ErroPermanente, ErroTransitorio, LeasePerdido
from dynaprice.dominio.modelos.fila import ParametrosDeFila
from tests.conftest import Banco
from tests.fakes import RelogioFixo

PARAMETROS = ParametrosDeFila(max_tentativas=3, variacao=0.0)


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo()


@pytest.fixture
def fila(pool: ConnectionPool, relogio: RelogioFixo) -> Iterator[FilaPostgres]:
    yield FilaPostgres(pool, relogio, PARAMETROS, dono="w1")


@pytest.fixture(autouse=True)
def fila_vazia(banco: Banco) -> None:
    """A fila distribui entre inquilinos: cada teste começa sem jobs dos anteriores."""
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute("DELETE FROM job.job")


def _enfileirar(
    fabrica: FabricaDeUnidadesPostgres, relogio: RelogioFixo, tenant: UUID, chave: str = "k"
) -> bool:
    with fabrica.para_tenant(tenant) as uow:
        return uow.fila.enfileirar("extrair", chave, {"a": 1}, relogio.agora())


def _linha(banco: Banco, tenant: UUID) -> tuple[str, int, str | None]:
    with psycopg.connect(banco.superusuario) as s:
        linha = s.execute(
            "SELECT estado, tentativas, lease_dono FROM job.job WHERE tenant_id = %s", (tenant,)
        ).fetchone()
    assert linha is not None
    return linha


def _alertas(banco: Banco, tenant: UUID) -> list[str]:
    with psycopg.connect(banco.superusuario) as s:
        linhas = s.execute(
            "SELECT tipo FROM core.alerta WHERE tenant_id = %s", (tenant,)
        ).fetchall()
    return [linha[0] for linha in linhas]


def test_enfileirar_duas_vezes_nao_duplica(
    fabrica: FabricaDeUnidadesPostgres, relogio: RelogioFixo, novo_tenant: UUID, banco: Banco
) -> None:
    assert _enfileirar(fabrica, relogio, novo_tenant) is True
    assert _enfileirar(fabrica, relogio, novo_tenant) is False
    with psycopg.connect(banco.superusuario) as s:
        linha = s.execute(
            "SELECT count(*) FROM job.job WHERE tenant_id = %s", (novo_tenant,)
        ).fetchone()
    assert linha == (1,)


def test_erro_transitorio_volta_com_backoff(
    fabrica: FabricaDeUnidadesPostgres,
    fila: FilaPostgres,
    relogio: RelogioFixo,
    novo_tenant: UUID,
    banco: Banco,
) -> None:
    _enfileirar(fabrica, relogio, novo_tenant)
    job = fila.reservar()
    assert job is not None
    fila.falhar(job, "tempo esgotado", permanente=False)
    assert _linha(banco, novo_tenant)[0] == "pendente"
    assert fila.reservar() is None
    relogio.avancar(61)
    assert fila.reservar() is not None


def test_tentativas_esgotadas_falham_com_alerta(
    fabrica: FabricaDeUnidadesPostgres,
    fila: FilaPostgres,
    relogio: RelogioFixo,
    novo_tenant: UUID,
    banco: Banco,
) -> None:
    _enfileirar(fabrica, relogio, novo_tenant)
    for _ in range(PARAMETROS.max_tentativas):
        job = fila.reservar()
        assert job is not None
        fila.falhar(job, "tempo esgotado", permanente=False)
        relogio.avancar(3600)
    assert _linha(banco, novo_tenant)[:2] == ("falhou", PARAMETROS.max_tentativas)
    assert _alertas(banco, novo_tenant) == ["job_falhou"]


def test_erro_permanente_nao_repete(
    fabrica: FabricaDeUnidadesPostgres,
    fila: FilaPostgres,
    relogio: RelogioFixo,
    novo_tenant: UUID,
    banco: Banco,
) -> None:
    _enfileirar(fabrica, relogio, novo_tenant)
    job = fila.reservar()
    assert job is not None
    fila.falhar(job, "credencial recusada", permanente=True)
    assert _linha(banco, novo_tenant)[:2] == ("falhou", 1)


def test_cada_job_roda_com_o_tenant_dele(
    fabrica: FabricaDeUnidadesPostgres,
    fila: FilaPostgres,
    relogio: RelogioFixo,
    novo_tenant: UUID,
    pool: ConnectionPool,
    banco: Banco,
) -> None:
    from dynaprice.dominio.modelos import Contrato, Dinheiro

    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        linha = s.execute("INSERT INTO core.tenant (nome) VALUES ('B') RETURNING id").fetchone()
    assert linha is not None
    outro: UUID = linha[0]
    with fabrica.para_tenant(novo_tenant) as uow:
        uow.contratos.salvar(Contrato("C-A", Dinheiro.de(1)))
    with fabrica.para_tenant(outro) as uow:
        uow.contratos.salvar(Contrato("C-B", Dinheiro.de(1)))
    _enfileirar(fabrica, relogio, novo_tenant)
    _enfileirar(fabrica, relogio, outro)
    vistos: dict[UUID, list[str]] = {}

    def manipular(job_tenant: UUID) -> None:
        with fabrica.para_tenant(job_tenant) as uow:
            vistos[job_tenant] = [c.id for c in uow.contratos.listar()]

    laco = LacoDoWorker(fila, {"extrair": lambda job: manipular(job.tenant_id)}, relogio)
    assert laco.executar_um() is True
    assert laco.executar_um() is True
    assert vistos == {novo_tenant: ["C-A"], outro: ["C-B"]}


def test_laco_mapeia_erros_para_a_fila(
    fabrica: FabricaDeUnidadesPostgres,
    fila: FilaPostgres,
    relogio: RelogioFixo,
    novo_tenant: UUID,
    banco: Banco,
) -> None:
    def transitorio(_: object) -> None:
        raise ErroTransitorio("Domínio fora do ar")

    def permanente(_: object) -> None:
        raise ErroPermanente("credencial")

    _enfileirar(fabrica, relogio, novo_tenant)
    assert LacoDoWorker(fila, {"extrair": transitorio}, relogio).executar_um() is True
    assert _linha(banco, novo_tenant)[0] == "pendente"
    relogio.avancar(120)
    assert LacoDoWorker(fila, {"extrair": permanente}, relogio).executar_um() is True
    assert _linha(banco, novo_tenant)[0] == "falhou"


def test_laco_sem_job_retorna_falso(fila: FilaPostgres, relogio: RelogioFixo) -> None:
    assert LacoDoWorker(fila, {}, relogio).executar_um() is False


def test_tipo_desconhecido_falha_sem_repetir(
    fabrica: FabricaDeUnidadesPostgres,
    fila: FilaPostgres,
    relogio: RelogioFixo,
    novo_tenant: UUID,
    banco: Banco,
) -> None:
    _enfileirar(fabrica, relogio, novo_tenant)
    assert LacoDoWorker(fila, {}, relogio).executar_um() is True
    assert _linha(banco, novo_tenant)[0] == "falhou"


class TestSimulacaoWorkerQueMorre:
    """Simulação mw9kw9i514upw:19, passo a passo."""

    def test_cinco_passos(
        self,
        fabrica: FabricaDeUnidadesPostgres,
        pool: ConnectionPool,
        relogio: RelogioFixo,
        novo_tenant: UUID,
        banco: Banco,
    ) -> None:
        w1 = FilaPostgres(pool, relogio, PARAMETROS, dono="w1")
        w2 = FilaPostgres(pool, relogio, PARAMETROS, dono="w2")
        _enfileirar(fabrica, relogio, novo_tenant)
        # Passo 1: worker 1 pega o job.
        job_w1 = w1.reservar()
        assert job_w1 is not None
        assert _linha(banco, novo_tenant) == ("em_execucao", 1, "w1")
        # Passo 2: heartbeat mantém o lease; depois o worker morre e o lease vence.
        relogio.avancar(200)
        w1.heartbeat(job_w1)
        assert w2.recuperar_orfaos() == 0
        relogio.avancar(timedelta(seconds=PARAMETROS.lease_s + 1).total_seconds())
        # Passo 3: a varredura devolve o job à fila.
        assert w2.recuperar_orfaos() == 1
        assert _linha(banco, novo_tenant) == ("pendente", 1, None)
        # Passo 4: worker 2 conclui.
        job_w2 = w2.reservar()
        assert job_w2 is not None
        w2.concluir(job_w2)
        assert _linha(banco, novo_tenant) == ("concluido", 2, "w2")
        # Passo 5: worker 1 volta atrasado e não consegue concluir.
        with pytest.raises(LeasePerdido):
            w1.concluir(job_w1)
        assert _linha(banco, novo_tenant) == ("concluido", 2, "w2")

    def test_orfao_na_ultima_tentativa_falha_com_alerta(
        self,
        fabrica: FabricaDeUnidadesPostgres,
        pool: ConnectionPool,
        relogio: RelogioFixo,
        novo_tenant: UUID,
        banco: Banco,
    ) -> None:
        w1 = FilaPostgres(pool, relogio, PARAMETROS, dono="w1")
        _enfileirar(fabrica, relogio, novo_tenant)
        for _ in range(PARAMETROS.max_tentativas):
            assert w1.reservar() is not None
            relogio.avancar(PARAMETROS.lease_s + 1)
            assert w1.recuperar_orfaos() == 1
        assert _linha(banco, novo_tenant)[0] == "falhou"
        assert _alertas(banco, novo_tenant) == ["job_falhou"]
