"""Leituras da carteira para a interface: lista de clientes e painel."""

from decimal import Decimal

import pytest

from dynaprice.aplicacao.casos_de_uso.carteira import ConsultarPainel, ListarClientes
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

ALVO = Decimal("614.27")  # preço-alvo da Tabela 7 com κ = 1


def _recalibrar(preco: CenarioDePreco) -> None:
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)


def test_cliente_traz_preco_vigente_alvo_e_defasagem(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7("A", meses=12, provisorio=False, vigente="437")
    _recalibrar(preco)
    (linha,) = ListarClientes(preco.fabrica).executar(preco.aprovador, REFERENCIA)
    assert linha.contrato_id == "A"
    assert linha.preco_vigente == Decimal("437.00")
    assert linha.preco_alvo == ALVO
    assert linha.defasagem_pct is not None and linha.defasagem_pct < 0
    assert linha.regime is not None


def test_sem_recalibracao_o_cliente_aparece_sem_preco_alvo(preco: CenarioDePreco) -> None:
    preco.contrato_tabela_7("A", meses=12, provisorio=False, vigente="437")
    (linha,) = ListarClientes(preco.fabrica).executar(preco.aprovador, REFERENCIA)
    assert linha.preco_alvo is None
    assert linha.defasagem_pct is None


def test_painel_resume_a_carteira(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7("A", meses=12, provisorio=False, vigente="437")
    preco.contrato_tabela_7("B", meses=6, provisorio=True, vigente="700")
    _recalibrar(preco)
    painel = ConsultarPainel(preco.fabrica).executar(preco.aprovador, REFERENCIA)
    assert painel.contratos == 2
    assert painel.provisorios == 1
    assert len(painel.serie_receita) == 12
    assert isinstance(painel.competencias_com_dados, tuple)
    assert sum(f.contratos for f in painel.faixas) == 2
    assert painel.receita_alvo == Decimal("1133.72")  # 614,27 (A) + 519,45 (B, provisório)
    assert painel.potencial_de_reajuste == ALVO - Decimal(437)
    assert [m.contrato_id for m in painel.maiores_defasagens] == ["A"]


def test_leitura_exige_papel(preco: CenarioDePreco) -> None:
    from dataclasses import replace

    from dynaprice.aplicacao.erros import AcessoNegado

    sem_papel = replace(preco.aprovador, papeis=frozenset())
    with pytest.raises(AcessoNegado):
        ConsultarPainel(preco.fabrica).executar(sem_papel, REFERENCIA)
