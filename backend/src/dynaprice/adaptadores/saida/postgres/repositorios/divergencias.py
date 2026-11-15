"""Repositório de divergências de cobrança (uc_conc)."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.adaptadores.saida.postgres.repositorios.cadastro import (
    competencia_da_data,
    data_da_competencia,
)
from dynaprice.dominio.modelos import Dinheiro
from dynaprice.dominio.modelos.divergencia import Divergencia, SituacaoDivergencia

_COLUNAS_DIVERGENCIA = "id, contrato_id, competencia, aprovado, cobrado, situacao, justificativa"


def _divergencia(linha: tuple[Any, ...]) -> Divergencia:
    return Divergencia(
        linha[0],
        linha[1],
        competencia_da_data(linha[2]),
        Dinheiro(linha[3]),
        Dinheiro(linha[4]),
        SituacaoDivergencia(linha[5]),
        linha[6],
    )


class RepositorioDeDivergenciasPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def abrir(self, divergencia: Divergencia, recomendacao_id: UUID) -> bool:
        d = divergencia
        cursor = self._conexao.execute(
            """INSERT INTO core.divergencia_cobranca (tenant_id, id, contrato_id, recomendacao_id,
                   competencia, aprovado, cobrado)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s)
               ON CONFLICT (tenant_id, contrato_id, competencia) DO NOTHING""",
            (
                d.id,
                d.contrato_id,
                recomendacao_id,
                data_da_competencia(d.competencia),
                d.aprovado.valor,
                d.cobrado.valor,
            ),
        )
        return cursor.rowcount == 1

    def obter(self, divergencia_id: UUID) -> Divergencia | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS_DIVERGENCIA} FROM core.divergencia_cobranca WHERE id = %s",
            (divergencia_id,),
        ).fetchone()
        return None if linha is None else _divergencia(linha)

    def salvar(self, divergencia: Divergencia) -> None:
        self._conexao.execute(
            "UPDATE core.divergencia_cobranca SET situacao = %s, justificativa = %s WHERE id = %s",
            (divergencia.situacao.value, divergencia.justificativa, divergencia.id),
        )

    def listar(self) -> Sequence[Divergencia]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_DIVERGENCIA} FROM core.divergencia_cobranca "
            "ORDER BY competencia DESC, contrato_id"
        ).fetchall()
        return [_divergencia(linha) for linha in linhas]
