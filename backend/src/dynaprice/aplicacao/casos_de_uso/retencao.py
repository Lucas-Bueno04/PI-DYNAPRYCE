"""Retenção (decisão D6): job mensal; a auditoria nunca é apagada pela aplicação."""

from datetime import timedelta

from dynaprice.aplicacao.portas import FabricaDeUnidades, JobReservado, Relogio

RAW_SUBSTITUIDO = timedelta(days=730)
SESSOES_EXPIRADAS = timedelta(days=30)
COTACOES_NAO_CONVERTIDAS = timedelta(days=365)


class AplicarRetencao:
    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(self, job: JobReservado) -> dict[str, int]:
        agora = self._relogio.agora()
        with self._fabrica.para_tenant(job.tenant_id) as uow:
            resultado = {
                "raw": uow.retencao.apagar_raw_substituido(agora - RAW_SUBSTITUIDO),
                "refresh": uow.retencao.apagar_refresh_expirado(
                    job.tenant_id, agora - SESSOES_EXPIRADAS
                ),
                "cotacoes": uow.retencao.apagar_cotacoes(agora - COTACOES_NAO_CONVERTIDAS),
            }
            uow.auditoria.registrar("retencao_aplicada", resultado)
        return resultado
