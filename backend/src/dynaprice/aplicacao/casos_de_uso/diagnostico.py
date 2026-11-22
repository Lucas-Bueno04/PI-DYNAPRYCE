"""Diagnóstico da carteira gravada: a mesma análise do relatório do laboratório (m_diag)."""

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.recalibrar import JANELA_MESES
from dynaprice.aplicacao.portas import AnalisadorDeCarteira, FabricaDeUnidades
from dynaprice.dominio.modelos import Competencia, Relatorio
from dynaprice.dominio.modelos.autenticacao import Principal


class ConsultarDiagnostico:
    def __init__(self, fabrica: FabricaDeUnidades, analisador: AnalisadorDeCarteira) -> None:
        self._fabrica = fabrica
        self._analisador = analisador

    def executar(self, principal: Principal, referencia: Competencia) -> Relatorio:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            carteira = uow.fatos.carteira(referencia.somar(1 - JANELA_MESES), referencia)
        return self._analisador.analisar(carteira, referencia)
