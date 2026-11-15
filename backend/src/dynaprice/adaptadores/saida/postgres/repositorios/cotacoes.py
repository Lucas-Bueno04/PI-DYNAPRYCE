"""Repositório de cotações (core.cotacao): entradas, versão da política e decomposição."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.aplicacao.portas import CotacaoRegistrada


class RepositorioDeCotacoesPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def gravar(
        self,
        regime: str,
        politica_versao: int,
        entradas: Mapping[str, Any],
        preco: Decimal,
        decomposicao: Mapping[str, Any],
        criada_por: UUID,
    ) -> UUID:
        linha = self._conexao.execute(
            """INSERT INTO core.cotacao (tenant_id, regime, politica_versao, entradas, preco,
                   decomposicao, criada_por)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                regime,
                politica_versao,
                Jsonb(dict(entradas)),
                preco,
                Jsonb(dict(decomposicao)),
                criada_por,
            ),
        ).fetchone()
        assert linha is not None
        return UUID(str(linha[0]))

    def obter(self, cotacao_id: UUID) -> CotacaoRegistrada | None:
        linha = self._conexao.execute(
            """SELECT id, regime, politica_versao, entradas, preco, decomposicao
               FROM core.cotacao WHERE id = %s""",
            (cotacao_id,),
        ).fetchone()
        return None if linha is None else CotacaoRegistrada(*linha)
