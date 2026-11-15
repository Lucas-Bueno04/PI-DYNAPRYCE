"""F3.5: carga do índice de inflação (global; só o papel migrador grava) sem sobrescrever."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres import abrir_pool
from dynaprice.adaptadores.saida.postgres.indices import IndicesDeInflacaoPostgres
from dynaprice.aplicacao.casos_de_uso.indices import AtualizarIndiceDeInflacao
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.indice import VariacaoDeIndice
from tests.conftest import Banco


class FonteFalsa:
    def __init__(self, *variacoes: VariacaoDeIndice) -> None:
        self.variacoes_ = variacoes
        self.pedidos: list[tuple[Competencia, Competencia]] = []

    def variacoes(self, inicio: Competencia, fim: Competencia) -> tuple[VariacaoDeIndice, ...]:
        self.pedidos.append((inicio, fim))
        return self.variacoes_


def _v(mes: int, valor: str) -> VariacaoDeIndice:
    return VariacaoDeIndice(Competencia(2026, mes), Decimal(valor))


@pytest.fixture
def migrador(banco: Banco) -> Iterator[ConnectionPool[Any]]:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute("DELETE FROM core.indice_inflacao WHERE competencia >= '2026-01-01'")
    with abrir_pool(banco.migrador, tamanho_maximo=2) as pool:
        yield pool


def _linhas(banco: Banco) -> list[tuple[object, ...]]:
    with psycopg.connect(banco.superusuario) as s:
        return s.execute(
            "SELECT competencia, indice, variacao, registrado_por FROM core.indice_inflacao "
            "WHERE competencia >= '2026-01-01' ORDER BY competencia"
        ).fetchall()


def test_grava_os_meses_novos_com_a_origem(migrador: ConnectionPool[Any], banco: Banco) -> None:
    fonte = FonteFalsa(_v(1, "0.0042"), _v(2, "0.0030"))
    resumo = AtualizarIndiceDeInflacao(
        fonte, IndicesDeInflacaoPostgres(migrador), "bcb:sgs433"
    ).executar(Competencia(2026, 1), Competencia(2026, 2))
    assert (resumo.inseridos, resumo.iguais, resumo.divergentes) == (2, 0, ())
    assert fonte.pedidos == [(Competencia(2026, 1), Competencia(2026, 2))]
    assert [(r[2], r[3]) for r in _linhas(banco)] == [
        (Decimal("0.004200"), "bcb:sgs433"),
        (Decimal("0.003000"), "bcb:sgs433"),
    ]


def test_repetir_a_carga_nao_duplica_nem_altera(
    migrador: ConnectionPool[Any], banco: Banco
) -> None:
    caso = AtualizarIndiceDeInflacao(
        FonteFalsa(_v(1, "0.0042")), IndicesDeInflacaoPostgres(migrador), "bcb:sgs433"
    )
    caso.executar(Competencia(2026, 1), Competencia(2026, 1))
    resumo = caso.executar(Competencia(2026, 1), Competencia(2026, 1))
    assert (resumo.inseridos, resumo.iguais) == (0, 1)
    assert len(_linhas(banco)) == 1


def test_valor_revisado_pela_fonte_nao_sobrescreve_e_e_relatado(
    migrador: ConnectionPool[Any],
    banco: Banco,
) -> None:
    indices = IndicesDeInflacaoPostgres(migrador)
    AtualizarIndiceDeInflacao(FonteFalsa(_v(1, "0.0042")), indices, "manual:ana").executar(
        Competencia(2026, 1), Competencia(2026, 1)
    )
    resumo = AtualizarIndiceDeInflacao(FonteFalsa(_v(1, "0.0050")), indices, "bcb:sgs433").executar(
        Competencia(2026, 1), Competencia(2026, 1)
    )
    assert resumo.inseridos == 0 and len(resumo.divergentes) == 1
    divergente = resumo.divergentes[0]
    assert (divergente.competencia, divergente.gravado, divergente.da_fonte) == (
        Competencia(2026, 1),
        Decimal("0.004200"),
        Decimal("0.0050"),
    )
    assert [(r[2], r[3]) for r in _linhas(banco)] == [(Decimal("0.004200"), "manual:ana")]


def test_o_papel_da_aplicacao_nao_consegue_gravar_o_indice(banco: Banco) -> None:
    with psycopg.connect(banco.app) as s, pytest.raises(psycopg.errors.InsufficientPrivilege):
        s.execute("INSERT INTO core.indice_inflacao VALUES ('2026-03-01', 'IPCA', 0.01, 'x')")
