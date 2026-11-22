"""Caso de uso: relatório do laboratório (uc_simular + m_diag) sobre uma janela da carteira."""

from dynaprice.aplicacao.portas import AnalisadorDeCarteira, EscritorDeRelatorio, FonteDeCarteira
from dynaprice.dominio.modelos import Competencia, Relatorio


class GerarRelatorioDoLaboratorio:
    def __init__(
        self,
        fonte: FonteDeCarteira,
        analisador: AnalisadorDeCarteira,
        escritor: EscritorDeRelatorio,
    ) -> None:
        self._fonte = fonte
        self._analisador = analisador
        self._escritor = escritor

    def executar(self, inicio: Competencia, fim: Competencia) -> Relatorio:
        relatorio = self._analisador.analisar(self._fonte.extrair(inicio, fim), fim)
        self._escritor.escrever(relatorio)
        return relatorio
