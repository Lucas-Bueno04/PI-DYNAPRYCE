"""Repositórios de política, preço-alvo, recomendação e divergência."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.adaptadores.saida.postgres.repositorios.cadastro import (
    competencia_da_data,
    data_da_competencia,
)
from dynaprice.aplicacao.erros import Conflito
from dynaprice.aplicacao.portas import PrecoAlvoRegistrado, RegistroDePolitica
from dynaprice.dominio.modelos import (
    Competencia,
    Dinheiro,
    Kappa,
    PoliticaVersao,
    fabricar_politica,
)
from dynaprice.dominio.modelos.recomendacao import EstadoRecomendacao, Recomendacao


class RepositorioDePoliticasPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def salvar_rascunho(
        self,
        documento: Mapping[str, Any],
        portao_aceite: bool | None = None,
        relatorio: Mapping[str, Any] | None = None,
    ) -> int:
        linha = self._conexao.execute(
            "SELECT COALESCE(MAX(versao), 0) + 1 FROM core.politica_versao"
        ).fetchone()
        assert linha is not None
        versao = int(linha[0])
        self._conexao.execute(
            """INSERT INTO core.politica_versao (tenant_id, versao, documento, portao_aceite,
                   relatorio)
               VALUES (core.tenant_atual(), %s, %s, %s, %s)""",
            (
                versao,
                Jsonb({**documento, "versao": versao}),
                portao_aceite,
                None if relatorio is None else Jsonb(dict(relatorio)),
            ),
        )
        return versao

    def obter(self, versao: int) -> RegistroDePolitica | None:
        linha = self._conexao.execute(
            "SELECT versao, estado, documento, portao_aceite, relatorio "
            "FROM core.politica_versao WHERE versao = %s",
            (versao,),
        ).fetchone()
        return None if linha is None else RegistroDePolitica(*linha)

    def listar(self) -> Sequence[RegistroDePolitica]:
        linhas = self._conexao.execute(
            "SELECT versao, estado, documento, portao_aceite, relatorio "
            "FROM core.politica_versao ORDER BY versao DESC"
        ).fetchall()
        return [RegistroDePolitica(*linha) for linha in linhas]

    def versao_publicada(self) -> int | None:
        linha = self._conexao.execute(
            "SELECT versao FROM core.politica_versao WHERE estado = 'publicada'"
        ).fetchone()
        return None if linha is None else int(linha[0])

    def publicada(self) -> PoliticaVersao | None:
        linha = self._conexao.execute(
            "SELECT documento FROM core.politica_versao WHERE estado = 'publicada'"
        ).fetchone()
        return None if linha is None else fabricar_politica(linha[0]).publicar()

    def publicar(self, versao: int, por: UUID | None, agora: datetime) -> None:
        self._conexao.execute(
            "UPDATE core.politica_versao SET estado = 'substituida' WHERE estado = 'publicada'"
        )
        self._conexao.execute(
            """UPDATE core.politica_versao SET estado = 'publicada', aprovado_por = %s,
                   publicada_em = %s WHERE versao = %s""",
            (por, agora, versao),
        )
        self._conexao.execute("SELECT pg_notify('politica_publicada', core.tenant_atual()::text)")


class RepositorioDePrecosAlvoPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def gravar(
        self,
        contrato_id: str,
        competencia: Competencia,
        politica_versao: int,
        nivel: int,
        horas_padrao: Decimal | None,
        entradas: Mapping[str, Any],
        preco_alvo: Decimal,
    ) -> UUID | None:
        linha = self._conexao.execute(
            """INSERT INTO core.preco_alvo (tenant_id, contrato_id, competencia, politica_versao,
                   nivel_informacao, h_pad, entradas, preco_alvo)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (tenant_id, contrato_id, competencia, politica_versao) DO NOTHING
               RETURNING id""",
            (
                contrato_id,
                data_da_competencia(competencia),
                politica_versao,
                nivel,
                horas_padrao,
                Jsonb(dict(entradas)),
                preco_alvo,
            ),
        ).fetchone()
        return None if linha is None else linha[0]

    def obter(self, preco_alvo_id: UUID) -> PrecoAlvoRegistrado | None:
        linha = self._conexao.execute(
            """SELECT id, contrato_id, competencia, politica_versao, nivel_informacao, h_pad,
                      entradas, preco_alvo
               FROM core.preco_alvo WHERE id = %s""",
            (preco_alvo_id,),
        ).fetchone()
        if linha is None:
            return None
        return PrecoAlvoRegistrado(linha[0], linha[1], competencia_da_data(linha[2]), *linha[3:])

    def da_competencia(self, competencia: Competencia) -> Sequence[PrecoAlvoRegistrado]:
        linhas = self._conexao.execute(
            """SELECT id, contrato_id, competencia, politica_versao, nivel_informacao, h_pad,
                      entradas, preco_alvo
               FROM core.preco_alvo WHERE competencia = %s ORDER BY contrato_id""",
            (data_da_competencia(competencia),),
        ).fetchall()
        return [
            PrecoAlvoRegistrado(i, c, competencia_da_data(d), *resto) for i, c, d, *resto in linhas
        ]


_COLUNAS_RECOMENDACAO = (
    "id, contrato_id, preco_alvo_id, politica_versao, competencia, data_efeito, preco_vigente, "
    "preco_proposto, trajetoria, kappa, estado, versao, lote_id, motivo, decidido_por"
)


def _recomendacao(linha: tuple[Any, ...]) -> Recomendacao:
    return Recomendacao(
        id=linha[0],
        contrato_id=linha[1],
        preco_alvo_id=linha[2],
        politica_versao=linha[3],
        competencia=competencia_da_data(linha[4]),
        efeito=competencia_da_data(linha[5]),
        preco_vigente=Dinheiro(linha[6]),
        preco_proposto=Dinheiro(linha[7]),
        trajetoria=tuple(Dinheiro.de(Decimal(p)) for p in linha[8]),
        kappa=Kappa(Decimal(linha[9]).normalize()),
        estado=EstadoRecomendacao(linha[10]),
        versao=linha[11],
        lote_id=linha[12],
        motivo=linha[13],
        decidido_por=linha[14],
    )


class RepositorioDeRecomendacoesPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def inserir(self, recomendacao: Recomendacao) -> None:
        r = recomendacao
        self._conexao.execute(
            """INSERT INTO core.recomendacao (tenant_id, id, contrato_id, preco_alvo_id,
                   politica_versao, competencia, data_efeito, preco_vigente, preco_proposto,
                   trajetoria, kappa)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                r.id,
                r.contrato_id,
                r.preco_alvo_id,
                r.politica_versao,
                data_da_competencia(r.competencia),
                data_da_competencia(r.efeito),
                r.preco_vigente.valor,
                r.preco_proposto.valor,
                Jsonb([str(p) for p in r.trajetoria]),
                r.kappa.valor,
            ),
        )

    def obter(self, recomendacao_id: UUID) -> Recomendacao | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS_RECOMENDACAO} FROM core.recomendacao WHERE id = %s",
            (recomendacao_id,),
        ).fetchone()
        return None if linha is None else _recomendacao(linha)

    def listar(self, estado: EstadoRecomendacao | None = None) -> Sequence[Recomendacao]:
        filtro, valores = ("WHERE estado = %s", (estado.value,)) if estado else ("", ())
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_RECOMENDACAO} FROM core.recomendacao {filtro} "
            "ORDER BY competencia DESC, contrato_id",
            valores,
        ).fetchall()
        return [_recomendacao(linha) for linha in linhas]

    def salvar(self, recomendacao: Recomendacao, versao_esperada: int) -> None:
        r = recomendacao
        cursor = self._conexao.execute(
            """UPDATE core.recomendacao SET estado = %s, versao = %s, preco_proposto = %s,
                   trajetoria = %s, kappa = %s, lote_id = %s, motivo = %s, decidido_por = %s,
                   decidido_em = CASE WHEN %s::uuid IS NULL THEN decidido_em ELSE now() END
               WHERE id = %s AND versao = %s""",
            (
                r.estado.value,
                r.versao,
                r.preco_proposto.valor,
                Jsonb([str(p) for p in r.trajetoria]),
                r.kappa.valor,
                r.lote_id,
                r.motivo,
                r.decidido_por,
                r.decidido_por,
                r.id,
                versao_esperada,
            ),
        )
        if cursor.rowcount != 1:
            raise Conflito("a recomendação mudou desde a leitura")

    def pendentes_anteriores(self, competencia: Competencia) -> Sequence[Recomendacao]:
        linhas = self._conexao.execute(
            f"""SELECT {_COLUNAS_RECOMENDACAO} FROM core.recomendacao
                WHERE estado = 'pendente' AND competencia < %s""",
            (data_da_competencia(competencia),),
        ).fetchall()
        return [_recomendacao(linha) for linha in linhas]

    def contratos_aguardando_exportacao(self) -> frozenset[str]:
        linhas = self._conexao.execute(
            "SELECT DISTINCT contrato_id FROM core.recomendacao "
            "WHERE estado IN ('aprovada', 'falha_exportacao')"
        ).fetchall()
        return frozenset(linha[0] for linha in linhas)

    def do_lote(self, lote_id: UUID) -> Sequence[Recomendacao]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_RECOMENDACAO} FROM core.recomendacao WHERE lote_id = %s "
            "ORDER BY contrato_id",
            (lote_id,),
        ).fetchall()
        return [_recomendacao(linha) for linha in linhas]

    def ultima_exportada(self, contrato_id: str, competencia: Competencia) -> Recomendacao | None:
        linha = self._conexao.execute(
            f"""SELECT {_COLUNAS_RECOMENDACAO} FROM core.recomendacao
                WHERE contrato_id = %s AND estado = 'exportada' AND data_efeito <= %s
                ORDER BY data_efeito DESC LIMIT 1""",
            (contrato_id, data_da_competencia(competencia)),
        ).fetchone()
        return None if linha is None else _recomendacao(linha)
