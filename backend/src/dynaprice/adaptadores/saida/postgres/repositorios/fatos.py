"""Fatos mensais (empresa_mes, honorários), índice de inflação e alertas."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.adaptadores.saida.postgres.repositorios.cadastro import (
    RepositorioDeContratosPostgres,
    RepositorioDeEmpresasPostgres,
    RepositorioDeVinculosPostgres,
    competencia_da_data,
    data_da_competencia,
)
from dynaprice.aplicacao.portas import Alerta
from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Departamento,
    Dinheiro,
    Direcionadores,
    Honorario,
    Horas,
    HorasRegistradas,
    Regime,
)

INDICE_PADRAO = "IPCA"

_ULTIMA_VERSAO = """
    SELECT DISTINCT ON (m.empresa_id, m.competencia)
           m.empresa_id, m.competencia, m.direcionadores, m.horas_registradas
    FROM core.empresa_mes m
    JOIN core.empresa e ON e.tenant_id = m.tenant_id AND e.id = m.empresa_id
    WHERE m.competencia BETWEEN %s AND %s {filtro}
    ORDER BY m.empresa_id, m.competencia, m.versao_extracao DESC
"""


def _direcionadores(linha: tuple[Any, ...]) -> Direcionadores:
    valores = {nome: Decimal(valor) for nome, valor in linha[2].items()}
    return Direcionadores(linha[0], competencia_da_data(linha[1]), valores)


class RepositorioDeFatosPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def gravar_empresa_mes(
        self,
        direcionadores: Direcionadores,
        horas: Mapping[str, Decimal],
        versao: int,
        regime: Regime | None,
    ) -> None:
        self._conexao.execute(
            """INSERT INTO core.empresa_mes (tenant_id, empresa_id, competencia, versao_extracao,
                   regime, direcionadores, horas_registradas)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s)
               ON CONFLICT (tenant_id, empresa_id, competencia, versao_extracao) DO UPDATE SET
                   regime = EXCLUDED.regime, direcionadores = EXCLUDED.direcionadores,
                   horas_registradas = EXCLUDED.horas_registradas""",
            (
                direcionadores.empresa_id,
                data_da_competencia(direcionadores.competencia),
                versao,
                None if regime is None else regime.value,
                Jsonb({k: str(v) for k, v in direcionadores.valores.items()}),
                Jsonb({k: str(v) for k, v in horas.items()}),
            ),
        )

    def gravar_honorario(self, honorario: Honorario) -> None:
        self._conexao.execute(
            """INSERT INTO core.honorario_mes (tenant_id, contrato_id, competencia, valor_cobrado)
               VALUES (core.tenant_atual(), %s, %s, %s)
               ON CONFLICT (tenant_id, contrato_id, competencia) DO UPDATE SET
                   valor_cobrado = EXCLUDED.valor_cobrado""",
            (
                honorario.contrato_id,
                data_da_competencia(honorario.competencia),
                honorario.valor.valor,
            ),
        )

    def honorarios_da_competencia(self, competencia: Competencia) -> Sequence[Honorario]:
        linhas = self._conexao.execute(
            "SELECT contrato_id, competencia, valor_cobrado FROM core.honorario_mes "
            "WHERE competencia = %s ORDER BY contrato_id",
            (data_da_competencia(competencia),),
        ).fetchall()
        return [Honorario(c, competencia_da_data(d), Dinheiro(v)) for c, d, v in linhas]

    def direcionadores_do_regime_atual(
        self, inicio: Competencia, fim: Competencia
    ) -> Sequence[Direcionadores]:
        # D13: meses de outro regime não contam; regime nulo vem de cargas sem histórico dele.
        consulta = _ULTIMA_VERSAO.format(filtro="AND (m.regime IS NULL OR m.regime = e.regime)")
        linhas = self._conexao.execute(
            consulta.encode(), (data_da_competencia(inicio), data_da_competencia(fim))
        ).fetchall()
        return [_direcionadores(linha) for linha in linhas]

    def inflacao_acumulada(self, inicio: Competencia, fim: Competencia) -> Decimal | None:
        linhas = self._conexao.execute(
            "SELECT variacao FROM core.indice_inflacao "
            "WHERE indice = %s AND competencia BETWEEN %s AND %s",
            (INDICE_PADRAO, data_da_competencia(inicio), data_da_competencia(fim)),
        ).fetchall()
        if len(linhas) != inicio.meses_ate(fim) + 1:
            return None
        acumulado = Decimal(1)
        for linha in linhas:
            acumulado *= 1 + linha[0]
        return acumulado - 1

    def carteira(self, inicio: Competencia, fim: Competencia) -> Carteira:
        linhas = self._conexao.execute(
            _ULTIMA_VERSAO.format(filtro="").encode(),
            (data_da_competencia(inicio), data_da_competencia(fim)),
        ).fetchall()
        honorarios = self._conexao.execute(
            "SELECT contrato_id, competencia, valor_cobrado FROM core.honorario_mes "
            "WHERE competencia BETWEEN %s AND %s",
            (data_da_competencia(inicio), data_da_competencia(fim)),
        ).fetchall()
        return Carteira(
            empresas=tuple(RepositorioDeEmpresasPostgres(self._conexao).listar()),
            contratos=tuple(RepositorioDeContratosPostgres(self._conexao).listar()),
            vinculos=tuple(RepositorioDeVinculosPostgres(self._conexao).listar()),
            direcionadores=tuple(_direcionadores(linha) for linha in linhas),
            horas=tuple(_horas(linhas)),
            honorarios=tuple(
                Honorario(c, competencia_da_data(d), Dinheiro(v)) for c, d, v in honorarios
            ),
        )


def _horas(linhas: Sequence[tuple[Any, ...]]) -> list[HorasRegistradas]:
    return [
        HorasRegistradas(
            linha[0], competencia_da_data(linha[1]), Departamento(nome), Horas(Decimal(valor))
        )
        for linha in linhas
        for nome, valor in linha[3].items()
    ]


class AlertasPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def registrar(
        self, tipo: str, referencia: str, detalhe: Mapping[str, Any] | None = None
    ) -> None:
        self._conexao.execute(
            "INSERT INTO core.alerta (tenant_id, tipo, referencia, detalhe) "
            "VALUES (core.tenant_atual(), %s, %s, %s)",
            (tipo, referencia, Jsonb(dict(detalhe or {}))),
        )

    def nao_reconhecidos(self) -> Sequence[Alerta]:
        linhas = self._conexao.execute(
            "SELECT id, tipo, referencia, criado_em FROM core.alerta "
            "WHERE reconhecido_em IS NULL ORDER BY criado_em DESC"
        ).fetchall()
        return [Alerta(*linha) for linha in linhas]
