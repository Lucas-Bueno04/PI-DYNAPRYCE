"""Vínculos empresa ↔ contrato e fila de pendências (uc_vinc, ADR-003)."""

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.portas import FabricaDeUnidades
from dynaprice.dominio.modelos import Competencia, Vinculo
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.precificacao import empresas_sem_vinculo


class CriarVinculo:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, vinculo: Vinculo) -> None:
        autorizar(principal, Acao.GERIR_VINCULOS)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            uow.vinculos.salvar(vinculo)
            uow.auditoria.registrar(
                "vinculo_criado",
                {"empresa": vinculo.empresa_id, "contrato": vinculo.contrato_id},
                usuario_id=principal.usuario_id,
            )


class ListarPendencias:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, competencia: Competencia) -> list[str]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            fatos = uow.fatos.direcionadores_do_regime_atual(competencia, competencia)
            return empresas_sem_vinculo(competencia, uow.vinculos.listar(), fatos)
