"""F0.10: k_agr — H_pad e segmento por contrato (ADR-003; D1)."""

from collections.abc import Sequence
from decimal import Decimal

import pytest

from dynaprice.dominio.modelos import (
    Competencia,
    Departamento,
    Direcionadores,
    Empresa,
    Regime,
    Vinculo,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import (
    AgregadorDeContratos,
    EquacoesDeTempo,
    MotivoPendencia,
    regime_da_principal,
)
from tests.dominio.modelos.documentos import documento_tabela_7

REF = Competencia(2025, 12)
TABELA_7 = {
    "notas_entrada": Decimal(30),
    "lancamentos_manuais": Decimal(40),
    "empregados": Decimal(2),
}


def _meses(empresa_id: str, quantos: int = 12) -> list[Direcionadores]:
    return [Direcionadores(empresa_id, REF.somar(-i), TABELA_7) for i in range(quantos)]


@pytest.fixture
def agregador() -> AgregadorDeContratos:
    return AgregadorDeContratos(EquacoesDeTempo(fabricar_politica(documento_tabela_7())))


def test_soma_as_empresas_do_contrato(agregador: AgregadorDeContratos) -> None:
    matriz = Empresa("m", Regime.LP)
    folha = Empresa("f", Regime.LP, frozenset({Departamento.FOLHA}))
    vinculos = [
        Vinculo("m", "c1", desde=Competencia(2020, 1), principal=True),
        Vinculo("f", "c1", desde=Competencia(2020, 1)),
    ]
    resultado = agregador.agregar(REF, [matriz, folha], vinculos, _meses("m") + _meses("f"))
    (contrato,) = resultado.contratos
    assert contrato.contrato_id == "c1"
    assert contrato.empresas == ("f", "m")
    assert contrato.horas_padrao.total.valor == Decimal("5.935") + Decimal(40) / 60
    assert contrato.regime is Regime.LP
    assert contrato.meses == 12
    assert resultado.pendencias == ()


def test_empresa_sem_vinculo_vigente_vira_pendencia(agregador: AgregadorDeContratos) -> None:
    empresas = [Empresa("m", Regime.SN), Empresa("solta", Regime.SN), Empresa("antiga", Regime.SN)]
    vinculos = [
        Vinculo("m", "c1", desde=Competencia(2020, 1), principal=True),
        Vinculo("antiga", "c1", desde=Competencia(2020, 1), ate=Competencia(2025, 11)),
    ]
    direcionadores = _meses("m") + _meses("solta") + _meses("antiga")
    resultado = agregador.agregar(REF, empresas, vinculos, direcionadores)
    assert resultado.contratos[0].empresas == ("m",)
    assert resultado.contratos[0].horas_padrao.total.valor == Decimal("5.935")
    assert {(p.referencia, p.motivo) for p in resultado.pendencias} == {
        ("solta", MotivoPendencia.SEM_VINCULO),
        ("antiga", MotivoPendencia.SEM_VINCULO),
    }


def test_empresa_em_dois_contratos_fica_fora_dos_dois(agregador: AgregadorDeContratos) -> None:
    empresas = [Empresa("a", Regime.SN), Empresa("b", Regime.SN), Empresa("x", Regime.SN)]
    vinculos = [
        Vinculo("a", "c1", desde=REF, principal=True),
        Vinculo("b", "c2", desde=REF, principal=True),
        Vinculo("x", "c1", desde=REF),
        Vinculo("x", "c2", desde=REF),
    ]
    direcionadores = _meses("a") + _meses("b") + _meses("x")
    resultado = agregador.agregar(REF, empresas, vinculos, direcionadores)
    assert all("x" not in c.empresas for c in resultado.contratos)
    assert ("x", MotivoPendencia.VINCULO_DUPLICADO) in {
        (p.referencia, p.motivo) for p in resultado.pendencias
    }


def test_contrato_sem_principal_fica_pendente(agregador: AgregadorDeContratos) -> None:
    resultado = agregador.agregar(
        REF, [Empresa("a", Regime.SN)], [Vinculo("a", "c1", desde=REF)], _meses("a")
    )
    assert resultado.contratos == ()
    assert resultado.pendencias[0].referencia == "c1"
    assert resultado.pendencias[0].motivo is MotivoPendencia.SEM_PRINCIPAL


def test_meses_e_o_minimo_entre_as_empresas(agregador: AgregadorDeContratos) -> None:
    empresas = [Empresa("m", Regime.SN), Empresa("nova", Regime.SN)]
    vinculos = [
        Vinculo("m", "c1", desde=Competencia(2020, 1), principal=True),
        Vinculo("nova", "c1", desde=Competencia(2025, 10)),
    ]
    resultado = agregador.agregar(REF, empresas, vinculos, _meses("m") + _meses("nova", 3))
    assert resultado.contratos[0].meses == 3


def test_segmento_misto_d1_regime_da_principal_com_alerta(agregador: AgregadorDeContratos) -> None:
    empresas = [Empresa("m", Regime.SN), Empresa("lr", Regime.LR)]
    vinculos = [Vinculo("m", "c1", desde=REF, principal=True), Vinculo("lr", "c1", desde=REF)]
    contrato = agregador.agregar(REF, empresas, vinculos, _meses("m") + _meses("lr")).contratos[0]
    assert contrato.regime is Regime.SN
    assert contrato.misto
    assert contrato.alerta_segmento  # principal MEI/SN com LP/LR no contrato (D1)


def test_regra_de_segmento_injetavel_muda_so_o_segmento() -> None:
    def maior_regime(empresas: Sequence[Empresa], principal: Empresa) -> Regime:
        return max((e.regime for e in empresas), key=list(Regime).index)

    politica = fabricar_politica(documento_tabela_7())
    padrao = AgregadorDeContratos(EquacoesDeTempo(politica), regime_da_principal)
    outro = AgregadorDeContratos(EquacoesDeTempo(politica), maior_regime)
    empresas = [Empresa("m", Regime.SN), Empresa("lr", Regime.LR)]
    vinculos = [Vinculo("m", "c1", desde=REF, principal=True), Vinculo("lr", "c1", desde=REF)]
    direcionadores = _meses("m") + _meses("lr")
    a = padrao.agregar(REF, empresas, vinculos, direcionadores).contratos[0]
    b = outro.agregar(REF, empresas, vinculos, direcionadores).contratos[0]
    assert (a.regime, b.regime) == (Regime.SN, Regime.LR)
    assert a.horas_padrao == b.horas_padrao
