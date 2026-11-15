"""Carga do índice de inflação: a fonte nunca sobrescreve o que já foi gravado (e auditado)."""

from dataclasses import dataclass

from dynaprice.aplicacao.portas.inflacao import Divergencia, FonteDeInflacao, RepositorioDeIndices
from dynaprice.dominio.modelos import Competencia


@dataclass(frozen=True, slots=True)
class ResumoDaCargaDoIndice:
    inseridos: int
    iguais: int
    divergentes: tuple[Divergencia, ...]


class AtualizarIndiceDeInflacao:
    def __init__(self, fonte: FonteDeInflacao, indices: RepositorioDeIndices, origem: str) -> None:
        self._fonte = fonte
        self._indices = indices
        self._origem = origem

    def executar(self, inicio: Competencia, fim: Competencia) -> ResumoDaCargaDoIndice:
        inseridos, iguais = 0, 0
        divergentes: list[Divergencia] = []
        for variacao in self._fonte.variacoes(inicio, fim):
            existente = self._indices.gravar_se_ausente(variacao, self._origem)
            if existente is None:
                inseridos += 1
            elif existente == variacao.variacao:
                iguais += 1
            else:
                divergentes.append(Divergencia(variacao.competencia, existente, variacao.variacao))
        return ResumoDaCargaDoIndice(inseridos, iguais, tuple(divergentes))
