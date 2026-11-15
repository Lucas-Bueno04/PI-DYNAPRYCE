"""Repositórios de contrato, empresa e vínculo (Repository: isola o SQL do domínio)."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import errors

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.aplicacao.erros import Conflito, NaoEncontrado
from dynaprice.dominio.modelos import (
    Competencia,
    Contrato,
    Departamento,
    DescontoNegociado,
    Dinheiro,
    Empresa,
    Kappa,
    Regime,
    Vinculo,
)


def data_da_competencia(competencia: Competencia) -> date:
    return date(competencia.ano, competencia.mes, 1)


def competencia_da_data(valor: date) -> Competencia:
    return Competencia(valor.year, valor.month)


_COLUNAS_CONTRATO = (
    "id, preco_vigente, kappa, desconto, desconto_justificativa, mes_reajuste, estado"
)


def _contrato(linha: tuple[Any, ...]) -> Contrato:
    identificador, preco, kappa, desconto, justificativa, mes, estado = linha
    return Contrato(
        identificador,
        Dinheiro(preco),
        Kappa(Decimal(kappa).normalize()),
        DescontoNegociado(Decimal(desconto).normalize(), justificativa),
        mes,
        provisorio=estado == "provisorio",
    )


class RepositorioDeContratosPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def obter(self, contrato_id: str) -> Contrato | None:
        linha = self._conexao.execute(
            f"SELECT {_COLUNAS_CONTRATO} FROM core.contrato WHERE id = %s", (contrato_id,)
        ).fetchone()
        return None if linha is None else _contrato(linha)

    def listar(self) -> Sequence[Contrato]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_CONTRATO} FROM core.contrato ORDER BY id"
        ).fetchall()
        return [_contrato(linha) for linha in linhas]

    def salvar(self, contrato: Contrato) -> None:
        self._conexao.execute(
            """INSERT INTO core.contrato (tenant_id, id, preco_vigente, kappa, desconto,
                   desconto_justificativa, mes_reajuste, estado)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (tenant_id, id) DO UPDATE SET
                   preco_vigente = EXCLUDED.preco_vigente, kappa = EXCLUDED.kappa,
                   desconto = EXCLUDED.desconto,
                   desconto_justificativa = EXCLUDED.desconto_justificativa,
                   mes_reajuste = EXCLUDED.mes_reajuste, estado = EXCLUDED.estado,
                   versao = core.contrato.versao + 1""",
            (
                contrato.id,
                contrato.preco_vigente.valor,
                contrato.kappa.valor,
                contrato.desconto.percentual,
                contrato.desconto.justificativa,
                contrato.mes_reajuste,
                "provisorio" if contrato.provisorio else "definitivo",
            ),
        )


def _empresa(linha: tuple[Any, ...]) -> Empresa:
    identificador, regime, departamentos = linha
    return Empresa(identificador, Regime(regime), frozenset(map(Departamento, departamentos)))


class RepositorioDeEmpresasPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def obter(self, empresa_id: str) -> Empresa | None:
        linha = self._conexao.execute(
            "SELECT id, regime, departamentos FROM core.empresa WHERE id = %s", (empresa_id,)
        ).fetchone()
        return None if linha is None else _empresa(linha)

    def listar(self) -> Sequence[Empresa]:
        linhas = self._conexao.execute(
            "SELECT id, regime, departamentos FROM core.empresa ORDER BY id"
        ).fetchall()
        return [_empresa(linha) for linha in linhas]

    def salvar(self, empresa: Empresa) -> None:
        self._conexao.execute(
            """INSERT INTO core.empresa (tenant_id, id, regime, departamentos)
               VALUES (core.tenant_atual(), %s, %s, %s)
               ON CONFLICT (tenant_id, id) DO UPDATE SET
                   regime = EXCLUDED.regime, departamentos = EXCLUDED.departamentos""",
            (empresa.id, empresa.regime.value, sorted(d.value for d in empresa.departamentos)),
        )


def _vinculo(linha: tuple[Any, ...]) -> Vinculo:
    empresa, contrato, desde, ate, principal = linha
    return Vinculo(
        empresa,
        contrato,
        competencia_da_data(desde),
        None if ate is None else competencia_da_data(ate),
        principal,
    )


class RepositorioDeVinculosPostgres:
    def __init__(self, conexao: Conexao) -> None:
        self._conexao = conexao

    def listar(self) -> Sequence[Vinculo]:
        linhas = self._conexao.execute(
            "SELECT empresa_id, contrato_id, desde, ate, principal FROM core.vinculo "
            "ORDER BY empresa_id, desde"
        ).fetchall()
        return [_vinculo(linha) for linha in linhas]

    def salvar(self, vinculo: Vinculo) -> None:
        try:
            self._gravar(vinculo)
        except errors.ExclusionViolation as erro:
            raise Conflito(f"vínculo sobreposto para a empresa {vinculo.empresa_id}") from erro
        except errors.ForeignKeyViolation as erro:
            raise NaoEncontrado("empresa ou contrato do vínculo") from erro

    def _gravar(self, vinculo: Vinculo) -> None:
        ate = None if vinculo.ate is None else data_da_competencia(vinculo.ate)
        self._conexao.execute(
            """INSERT INTO core.vinculo (tenant_id, contrato_id, empresa_id, principal, desde, ate)
               VALUES (core.tenant_atual(), %s, %s, %s, %s, %s)
               ON CONFLICT (tenant_id, empresa_id, desde) DO UPDATE SET
                   contrato_id = EXCLUDED.contrato_id, principal = EXCLUDED.principal,
                   ate = EXCLUDED.ate""",
            (
                vinculo.contrato_id,
                vinculo.empresa_id,
                vinculo.principal,
                data_da_competencia(vinculo.desde),
                ate,
            ),
        )
