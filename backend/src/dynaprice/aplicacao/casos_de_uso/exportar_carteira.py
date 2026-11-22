"""Caso de uso: extrair a carteira de uma fonte e entregá-la a um escritor (lab sintetico)."""

from dataclasses import dataclass

from dynaprice.aplicacao.portas import EscritorDeCarteira, FonteDeCarteira
from dynaprice.dominio.modelos import Competencia


@dataclass(frozen=True, slots=True)
class ResumoCarteira:
    contratos: int
    empresas: int
    vinculos: int
    meses_empresa: int


class ExportarCarteira:
    def __init__(self, fonte: FonteDeCarteira, escritor: EscritorDeCarteira) -> None:
        self._fonte = fonte
        self._escritor = escritor

    def executar(self, inicio: Competencia, fim: Competencia) -> ResumoCarteira:
        carteira = self._fonte.extrair(inicio, fim)
        self._escritor.escrever(carteira)
        return ResumoCarteira(
            contratos=len(carteira.contratos),
            empresas=len(carteira.empresas),
            vinculos=len(carteira.vinculos),
            meses_empresa=len(carteira.direcionadores),
        )
