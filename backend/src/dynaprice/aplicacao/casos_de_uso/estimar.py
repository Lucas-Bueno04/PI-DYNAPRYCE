"""Estimação anual (uc_estimar): só produz rascunho; publicar é decisão humana (F1.30)."""

from dynaprice.aplicacao.portas import EstimadorDePolitica, FabricaDeUnidades, JobReservado
from dynaprice.dominio.modelos import Competencia


class EstimarPolitica:
    def __init__(self, fabrica: FabricaDeUnidades, estimador: EstimadorDePolitica) -> None:
        self._fabrica = fabrica
        self._estimador = estimador

    def executar(self, job: JobReservado) -> None:
        ano = int(job.parametros["ano"])
        with self._fabrica.para_tenant(job.tenant_id) as uow:
            if any(r.relatorio and r.relatorio.get("ano") == ano for r in uow.politicas.listar()):
                return
            carteira = uow.fatos.carteira(Competencia(ano, 1), Competencia(ano, 12))
            vigente = uow.politicas.publicada()
        estimativa = self._estimador.estimar(carteira, Competencia(ano, 12), vigente)
        with self._fabrica.para_tenant(job.tenant_id) as uow:
            versao = uow.politicas.salvar_rascunho(
                estimativa.documento,
                estimativa.portao_aceite,
                {**estimativa.relatorio, "ano": ano},
            )
            if not estimativa.portao_aceite:
                uow.alertas.registrar("portao_reprovado", str(versao))
            uow.auditoria.registrar(
                "politica_estimada", {"versao": versao, "aceite": estimativa.portao_aceite}
            )
