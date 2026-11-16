"""Conciliação (uc_conc): compara o aprovado com o cobrado e trata as divergências."""

from collections.abc import Callable
from uuid import UUID, uuid4

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.erros import NaoEncontrado
from dynaprice.aplicacao.portas import FabricaDeUnidades
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.modelos.divergencia import Divergencia


class Conciliar:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, tenant_id: UUID, competencia: Competencia) -> int:
        """Devolve quantas divergências novas abriu."""
        abertas = 0
        with self._fabrica.para_tenant(tenant_id) as uow:
            for honorario in uow.fatos.honorarios_da_competencia(competencia):
                aprovada = uow.recomendacoes.ultima_exportada(honorario.contrato_id, competencia)
                if aprovada is None or aprovada.preco_proposto == honorario.valor:
                    continue
                divergencia = Divergencia(
                    uuid4(),
                    honorario.contrato_id,
                    competencia,
                    aprovada.preco_proposto,
                    honorario.valor,
                )
                if uow.divergencias.abrir(divergencia, aprovada.id):
                    abertas += 1
                    uow.alertas.registrar("divergencia", honorario.contrato_id)
        return abertas


class TratarDivergencia:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def justificar(self, principal: Principal, divergencia_id: UUID, texto: str) -> None:
        self._transitar(
            principal, divergencia_id, lambda d: d.justificar(texto), "divergencia_justificada"
        )

    def resolver(self, principal: Principal, divergencia_id: UUID) -> None:
        self._transitar(principal, divergencia_id, Divergencia.resolver, "divergencia_resolvida")

    def _transitar(
        self,
        principal: Principal,
        divergencia_id: UUID,
        transicao: Callable[[Divergencia], Divergencia],
        tipo: str,
    ) -> None:
        autorizar(principal, Acao.TRATAR_DIVERGENCIA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            atual = uow.divergencias.obter(divergencia_id)
            if atual is None:
                raise NaoEncontrado("divergência")
            nova = transicao(atual)
            uow.divergencias.salvar(nova)
            uow.auditoria.registrar(
                tipo,
                {"divergencia": str(divergencia_id), "justificativa": nova.justificativa},
                usuario_id=principal.usuario_id,
            )
