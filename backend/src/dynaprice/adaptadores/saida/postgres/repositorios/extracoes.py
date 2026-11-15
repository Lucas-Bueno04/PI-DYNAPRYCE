"""Raw versionado (imutável), quarentena e configuração dos conectores."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.adaptadores.saida.postgres.repositorios.cadastro import data_da_competencia
from dynaprice.aplicacao.portas import ConfiguracaoDeConector
from dynaprice.dominio.modelos import Competencia


class RepositorioDeExtracoesPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def versao_do_hash(
        self, fonte: str, competencia: Competencia, hash_conteudo: str
    ) -> int | None:
        linha = self._conexao.execute(
            "SELECT versao FROM raw.extracao "
            "WHERE fonte = %s AND competencia = %s AND hash_conteudo = %s",
            (fonte, data_da_competencia(competencia), hash_conteudo),
        ).fetchone()
        return None if linha is None else int(linha[0])

    def proxima_versao(self, fonte: str, competencia: Competencia) -> int:
        linha = self._conexao.execute(
            "SELECT COALESCE(MAX(versao), 0) + 1 FROM raw.extracao "
            "WHERE fonte = %s AND competencia = %s",
            (fonte, data_da_competencia(competencia)),
        ).fetchone()
        assert linha is not None
        return int(linha[0])

    def gravar(
        self,
        fonte: str,
        competencia: Competencia,
        versao: int,
        origem: str,
        hash_conteudo: str,
        conteudo: Mapping[str, Any],
        agora: datetime,
    ) -> UUID:
        data = data_da_competencia(competencia)
        self._conexao.execute(
            "UPDATE raw.extracao SET substituida = true WHERE fonte = %s AND competencia = %s",
            (fonte, data),
        )
        linha = self._conexao.execute(
            """INSERT INTO raw.extracao (tenant_id, fonte, competencia, versao, origem,
                   hash_conteudo, conteudo, extraido_em)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (fonte, data, versao, origem, hash_conteudo, Jsonb(dict(conteudo)), agora),
        ).fetchone()
        assert linha is not None
        identificador: UUID = linha[0]
        return identificador

    def quarentenar(self, extracao_id: UUID, arquivo: str, linha: int, motivo: str) -> None:
        self._conexao.execute(
            "INSERT INTO raw.quarentena (tenant_id, extracao_id, linha, motivo) "
            "VALUES (core.tenant_atual(), %s, %s, %s)",
            (extracao_id, Jsonb({"arquivo": arquivo, "linha": linha}), motivo),
        )


_COLUNAS = "tipo, credencial_cifrada, parametros, dias_fechamento"


def _configuracao(linha: tuple[Any, ...]) -> ConfiguracaoDeConector:
    credencial = None if linha[1] is None else bytes(linha[1])
    return ConfiguracaoDeConector(linha[0], credencial, linha[2], linha[3])


class RepositorioDeConectoresPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def salvar(self, configuracao: ConfiguracaoDeConector) -> None:
        c = configuracao
        self._conexao.execute(
            """INSERT INTO core.conector_config (tenant_id, tipo, credencial_cifrada, parametros,
                   dias_fechamento)
               VALUES (core.tenant_atual(), %s, %s, %s, %s)
               ON CONFLICT (tenant_id, tipo) DO UPDATE SET
                   credencial_cifrada = EXCLUDED.credencial_cifrada,
                   parametros = EXCLUDED.parametros,
                   dias_fechamento = EXCLUDED.dias_fechamento""",
            (c.tipo, c.credencial_cifrada, Jsonb(dict(c.parametros)), c.dias_fechamento),
        )

    def obter(self, tipo: str) -> ConfiguracaoDeConector | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS} FROM core.conector_config WHERE tipo = %s", (tipo,)
        ).fetchone()
        return None if linha is None else _configuracao(linha)

    def listar(self) -> Sequence[ConfiguracaoDeConector]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS} FROM core.conector_config ORDER BY tipo"
        ).fetchall()
        return [_configuracao(linha) for linha in linhas]
