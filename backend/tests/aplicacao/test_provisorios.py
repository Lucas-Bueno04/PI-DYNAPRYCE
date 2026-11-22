"""F2.4: relatório mensal "provisórios abaixo do esforço medido" (ADR-004, mitigação do risco)."""

from decimal import Decimal

import pytest

from dynaprice.aplicacao.casos_de_uso.provisorios import ProvisoriosAbaixoDoEsforco
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.dominio.modelos import Dinheiro
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

ESFORCO = Decimal("614.27")  # κ·max(π_LP, τ·H_pad) da Tabela 7 com κ = 1


@pytest.fixture
def relatorio(preco: CenarioDePreco) -> ProvisoriosAbaixoDoEsforco:
    return ProvisoriosAbaixoDoEsforco(preco.fabrica)


def _recalibrar(preco: CenarioDePreco) -> None:
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)


def test_lista_provisorio_com_preco_abaixo_do_esforco(
    preco: CenarioDePreco, relatorio: ProvisoriosAbaixoDoEsforco
) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7("P1", meses=6, provisorio=True, vigente="437")
    _recalibrar(preco)
    (item,) = relatorio.executar(preco.aprovador, REFERENCIA)
    assert item.contrato_id == "P1"
    assert item.preco_vigente == Dinheiro.de("437.00")
    assert item.esforco == Dinheiro.de("614.27")
    assert item.diferenca == ESFORCO - Decimal(437)
    assert item.meses == 6


def test_ignora_definitivos_e_provisorios_que_ja_cobrem_o_esforco(
    preco: CenarioDePreco, relatorio: ProvisoriosAbaixoDoEsforco
) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7("DEF", meses=12, provisorio=False, vigente="437")
    preco.contrato_tabela_7("ALTO", meses=6, provisorio=True, vigente="700")
    _recalibrar(preco)
    assert relatorio.executar(preco.aprovador, REFERENCIA) == ()


def test_ordena_pela_maior_diferenca(
    preco: CenarioDePreco, relatorio: ProvisoriosAbaixoDoEsforco
) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7("A", meses=6, provisorio=True, vigente="500")
    preco.contrato_tabela_7("B", meses=6, provisorio=True, vigente="300")
    _recalibrar(preco)
    assert [i.contrato_id for i in relatorio.executar(preco.aprovador, REFERENCIA)] == ["B", "A"]


def test_sem_recalibracao_do_mes_nao_ha_o_que_listar(
    preco: CenarioDePreco, relatorio: ProvisoriosAbaixoDoEsforco
) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7("P1", meses=6, provisorio=True, vigente="437")
    assert relatorio.executar(preco.aprovador, REFERENCIA) == ()
