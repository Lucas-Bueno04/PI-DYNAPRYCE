"""F1.10: unidade de trabalho por inquilino, repositórios e relógio."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from dynaprice.adaptadores.saida.relogio import RelogioDoSistema
from dynaprice.dominio.modelos import (
    Competencia,
    Contrato,
    Departamento,
    Dinheiro,
    Empresa,
    Kappa,
    Regime,
    Vinculo,
)
from tests.conftest import Banco


def _contrato(identificador: str = "C1") -> Contrato:
    return Contrato(identificador, Dinheiro.de("437.00"), Kappa.de("1.1"), mes_reajuste=3)


def test_transacao_fixa_o_inquilino_so_durante_ela(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.tenant_configurado() == str(novo_tenant)
    with fabrica.sem_tenant() as uow:
        assert uow.tenant_configurado() == ""


def test_contrato_ida_e_volta_preserva_decimal(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    with fabrica.para_tenant(novo_tenant) as uow:
        uow.contratos.salvar(_contrato())
    with fabrica.para_tenant(novo_tenant) as uow:
        lido = uow.contratos.obter("C1")
    assert lido is not None
    assert lido.preco_vigente == Dinheiro(Decimal("437.00"))
    assert lido.kappa == Kappa(Decimal("1.1"))
    assert lido.mes_reajuste == 3
    assert lido.provisorio is False


def test_contrato_salvar_de_novo_atualiza(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    with fabrica.para_tenant(novo_tenant) as uow:
        uow.contratos.salvar(_contrato())
        uow.contratos.salvar(_contrato().reajustar(Dinheiro.de("502.55")))
        assert [c.preco_vigente for c in uow.contratos.listar()] == [Dinheiro.de("502.55")]


def test_erro_desfaz_a_transacao(fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID) -> None:
    with pytest.raises(RuntimeError), fabrica.para_tenant(novo_tenant) as uow:
        uow.contratos.salvar(_contrato())
        raise RuntimeError("falha no meio")
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.contratos.obter("C1") is None


def test_empresa_e_vinculo_ida_e_volta(
    fabrica: FabricaDeUnidadesPostgres, novo_tenant: UUID
) -> None:
    empresa = Empresa("E1", Regime.LP, frozenset({Departamento.FOLHA}))
    vinculo = Vinculo("E1", "C1", Competencia(2026, 1), Competencia(2026, 12), principal=True)
    with fabrica.para_tenant(novo_tenant) as uow:
        uow.contratos.salvar(_contrato())
        uow.empresas.salvar(empresa)
        uow.vinculos.salvar(vinculo)
    with fabrica.para_tenant(novo_tenant) as uow:
        assert uow.empresas.obter("E1") == empresa
        assert uow.vinculos.listar() == [vinculo]


def test_competencia_em_sao_paulo_e_instante_em_utc(banco: Banco, novo_tenant: UUID) -> None:
    """01/02 às 02:00 UTC ainda é 31/01 em São Paulo: competência de janeiro."""
    instante = datetime(2027, 2, 1, 2, 0, tzinfo=UTC)
    relogio = RelogioDoSistema(lambda: instante)
    assert relogio.competencia_atual() == Competencia(2027, 1)
    assert relogio.agora().utcoffset() is not None
    assert relogio.agora().utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    with psycopg.connect(banco.superusuario) as c:
        c.execute("SET TIME ZONE 'UTC'")
        c.execute(
            "INSERT INTO audit.evento VALUES (%s, 1, NULL, NULL, 't', '{}', %s, '', '')",
            (novo_tenant, relogio.agora()),
        )
        linha = c.execute(
            "SELECT criado_em FROM audit.evento WHERE tenant_id = %s", (novo_tenant,)
        ).fetchone()
        c.rollback()
    assert linha is not None
    assert linha[0] == instante
