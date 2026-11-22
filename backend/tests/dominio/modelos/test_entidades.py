"""F0.5: entidades mínimas do contrato como unidade (ADR-003)."""

from decimal import Decimal

import pytest

from dynaprice.dominio.modelos import (
    Competencia,
    Contrato,
    Departamento,
    DescontoNegociado,
    Dinheiro,
    Direcionadores,
    Empresa,
    Kappa,
    Regime,
    ValorInvalido,
    Vinculo,
)


def test_empresa_tem_regime_obrigatorio() -> None:
    assert Empresa("e1", Regime.LP).regime is Regime.LP
    with pytest.raises(ValorInvalido):
        Empresa("", Regime.LP)


def test_empresa_atende_todos_os_departamentos_por_padrao() -> None:
    assert Empresa("e1", Regime.LP).departamentos == frozenset(Departamento)


def test_empresa_so_de_folha_e_sem_departamento() -> None:
    folha = Empresa("e2", Regime.SN, frozenset({Departamento.FOLHA}))
    assert folha.atende(Departamento.FOLHA)
    assert not folha.atende(Departamento.FISCAL)
    with pytest.raises(ValorInvalido):
        Empresa("e3", Regime.SN, frozenset())


class TestVinculo:
    def test_vigencia_com_fim(self) -> None:
        v = Vinculo("e1", "c1", desde=Competencia(2026, 1), ate=Competencia(2026, 6))
        assert v.vigente_em(Competencia(2026, 1))
        assert v.vigente_em(Competencia(2026, 6))
        assert not v.vigente_em(Competencia(2026, 7))
        assert not v.vigente_em(Competencia(2025, 12))

    def test_vigencia_aberta(self) -> None:
        v = Vinculo("e1", "c1", desde=Competencia(2026, 1))
        assert v.vigente_em(Competencia(2030, 1))

    def test_fim_antes_do_inicio(self) -> None:
        with pytest.raises(ValorInvalido):
            Vinculo("e1", "c1", desde=Competencia(2026, 5), ate=Competencia(2026, 4))


class TestContrato:
    def test_padroes(self) -> None:
        c = Contrato("c1", preco_vigente=Dinheiro.de("437"))
        assert c.kappa == Kappa.neutro()
        assert c.desconto == DescontoNegociado.nenhum()
        assert not c.provisorio
        assert c.mes_reajuste is None

    def test_mes_reajuste_valido(self) -> None:
        with pytest.raises(ValorInvalido):
            Contrato("c1", preco_vigente=Dinheiro.de("1"), mes_reajuste=13)

    def test_identidade_por_id(self) -> None:
        a = Contrato("c1", preco_vigente=Dinheiro.de("1"))
        b = Contrato("c1", preco_vigente=Dinheiro.de("2"))
        assert a == b
        assert hash(a) == hash(b)

    def test_reajustar_devolve_novo_estado(self) -> None:
        c = Contrato("c1", preco_vigente=Dinheiro.de("437"), provisorio=True)
        novo = c.reajustar(Dinheiro.de("502.55"))
        assert novo.preco_vigente == Dinheiro.de("502.55")
        assert not novo.provisorio
        assert c.preco_vigente == Dinheiro.de("437")


class TestDirecionadores:
    def test_valores_imutaveis_e_nao_negativos(self) -> None:
        d = Direcionadores("e1", Competencia(2026, 1), {"notas_entrada": Decimal(30)})
        assert d.valor("notas_entrada") == Decimal(30)
        assert d.valor("ausente") == Decimal(0)
        with pytest.raises(TypeError):
            d.valores["x"] = Decimal(1)  # type: ignore[index]
        with pytest.raises(ValorInvalido):
            Direcionadores("e1", Competencia(2026, 1), {"notas_entrada": Decimal(-1)})
