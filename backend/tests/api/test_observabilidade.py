"""F1.41: alerta visível ao administrador e métricas de requisição e de job."""

import logging
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from dynaprice.adaptadores.entrada.worker import LacoDoWorker
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.adaptadores.test_laco_worker import FilaDeTeste
from tests.fakes import RelogioFixo


def _admin(cliente: TestClient, tenant: UUID) -> dict[str, str]:
    principal = Principal(uuid4(), tenant, frozenset({Papel.ADMINISTRAR}), True)
    emissor = cliente.app.state.servicos.auth.emissor  # type: ignore[attr-defined]
    return {"Authorization": f"Bearer {emissor.emitir(principal)}"}


def test_metricas_de_requisicao_usam_a_rota_e_nao_o_id(
    cliente: TestClient, novo_tenant: UUID
) -> None:
    cabecalho = _admin(cliente, novo_tenant)
    cliente.get("/api/v1/saude")
    cliente.get(f"/api/v1/usuarios/{uuid4()}/redefinicao", headers=cabecalho)
    corpo = cliente.get("/api/v1/metricas", headers=cabecalho).json()
    assert corpo["GET /api/v1/saude 200"]["quantidade"] >= 1
    assert corpo["GET /api/v1/saude 200"]["duracao_total_s"] >= 0
    assert not any(str(novo_tenant) in chave for chave in corpo)


def test_metricas_exigem_administrador(cliente: TestClient) -> None:
    assert cliente.get("/api/v1/metricas").status_code == 401


def test_job_falho_aparece_nos_alertas(cliente: TestClient, novo_tenant: UUID) -> None:
    auth = cliente.app.state.servicos.auth  # type: ignore[attr-defined]
    with auth.fabrica.para_tenant(novo_tenant) as uow:
        uow.alertas.registrar("job_falhou", "abc")
    (alerta,) = cliente.get("/api/v1/alertas", headers=_admin(cliente, novo_tenant)).json()
    assert (alerta["tipo"], alerta["referencia"]) == ("job_falhou", "abc")


def test_worker_registra_a_duracao_do_job(caplog: pytest.LogCaptureFixture) -> None:
    fila = FilaDeTeste()
    laco = LacoDoWorker(fila, {"extrair": lambda _: None}, RelogioFixo())
    with caplog.at_level(logging.INFO):
        laco.executar_um()
    (registro,) = [r for r in caplog.records if r.getMessage() == "job_concluido"]
    assert registro.__dict__["tipo"] == "extrair"
    assert registro.__dict__["duracao_s"] >= 0
