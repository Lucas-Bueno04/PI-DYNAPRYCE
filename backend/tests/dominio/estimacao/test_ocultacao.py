"""F2.5: protocolo de ocultação (artigo 5.15/10.5): oculta-se a informação de clientes conhecidos,
infere-se o preço e mede-se o EPAM contra o preço-alvo conhecido.

Política da Tabela 7: π_LP = 235, π_SN = 185, τ = 103,5, s²/v² = 2.
"""

from decimal import Decimal

import pytest

from dynaprice.dominio.estimacao.ocultacao import (
    ContratoConhecido,
    LinhaDeEpam,
    ResultadoDaOcultacao,
    executar_ocultacao,
)
from dynaprice.dominio.modelos import Departamento, Horas, Regime, ValorInvalido, fabricar_politica
from tests.dominio.modelos.documentos import documento_tabela_7

POLITICA = fabricar_politica(documento_tabela_7())
TODOS = frozenset(Departamento)


def _contrato(
    i: int, regime: Regime, horas: Decimal | int | str, deptos: frozenset[Departamento] = TODOS
) -> ContratoConhecido:
    return ContratoConhecido(f"C{i:02d}", regime, deptos, tuple(Horas.de(horas) for _ in range(12)))


def _lp(n: int = 10) -> list[ContratoConhecido]:
    return [_contrato(i, Regime.LP, 3) for i in range(n)]  # alvo = max(235; 310,5) = 310,5


def _linha(resultado: ResultadoDaOcultacao, estimador: str, meses: int) -> LinhaDeEpam:
    (linha,) = [x for x in resultado.linhas if x.estimador == estimador and x.meses == meses]
    return linha


def test_piso_do_regime_erra_pela_distancia_entre_piso_e_alvo() -> None:
    r = executar_ocultacao(_lp(), POLITICA, meses_ocultos=(0, 6), ks=(3,), dobras=5)
    piso = _linha(r, "piso_regime", 0)
    assert piso.epam == pytest.approx((310.5 - 235) / 310.5)
    assert piso.vies_mediano < 0  # subestima: é o risco de subprecificação da ADR-004
    assert piso.n == 10


def test_credibilidade_reduz_o_erro_com_mais_meses_vistos() -> None:
    r = executar_ocultacao(_lp(), POLITICA, meses_ocultos=(0, 3, 6, 9), ks=(3,), dobras=5)
    erros = [_linha(r, "credibilidade", m).epam for m in (0, 3, 6, 9)]
    assert erros == sorted(erros, reverse=True) and erros[0] > erros[-1]
    # m = 6: Z = 6/(6+2) = 0,75; P = 0,75·310,5 + 0,25·235 = 291,625
    assert erros[2] == pytest.approx((310.5 - 291.625) / 310.5)


def test_sem_meses_credibilidade_e_igual_ao_piso() -> None:
    r = executar_ocultacao(_lp(), POLITICA, meses_ocultos=(0,), ks=(3,), dobras=5)
    assert _linha(r, "credibilidade", 0).epam == pytest.approx(_linha(r, "piso_regime", 0).epam)


def test_vizinhos_acertam_quando_o_perfil_explica_o_preco() -> None:
    carteira = _lp(10) + [_contrato(i, Regime.SN, 1) for i in range(10, 20)]  # SN: alvo = 185
    r = executar_ocultacao(carteira, POLITICA, meses_ocultos=(0,), ks=(3,), dobras=5)
    assert _linha(r, "vizinhos_k3", 0).epam == pytest.approx(0)
    assert _linha(r, "piso_regime", 0).epam == pytest.approx((310.5 - 235) / 310.5 / 2)


def test_o_vizinho_nunca_vem_da_dobra_do_oculto() -> None:
    """Perfis iguais, alvos distintos e k = 1: a previsão é o 1º contrato (por id) fora da dobra."""
    carteira = [_contrato(i, Regime.LP, Decimal(3) + Decimal(i) / 10) for i in range(10)]
    alvo = [103.5 * (3 + 0.1 * i) for i in range(10)]
    r = executar_ocultacao(carteira, POLITICA, meses_ocultos=(0,), ks=(1,), dobras=2)
    # dobra 0 = índices pares → vizinho C01; dobra 1 = ímpares → vizinho C00
    erros = [abs((alvo[1] if i % 2 == 0 else alvo[0]) - alvo[i]) / alvo[i] for i in range(10)]
    mediana = (sorted(erros)[4] + sorted(erros)[5]) / 2
    assert _linha(r, "vizinhos_k1", 0).epam == pytest.approx(mediana)


def test_combinacao_com_vizinhos_aparece_para_cada_k() -> None:
    r = executar_ocultacao(_lp(), POLITICA, meses_ocultos=(0, 6), ks=(3, 5), dobras=5)
    nomes = {x.estimador for x in r.linhas}
    assert {"piso_regime", "credibilidade", "vizinhos_k3", "vizinhos_k5"} <= nomes
    assert {"credibilidade_com_vizinhos_k3", "credibilidade_com_vizinhos_k5"} <= nomes


def test_resultado_e_determinista() -> None:
    a = executar_ocultacao(_lp(12), POLITICA, meses_ocultos=(0, 6), ks=(3,), dobras=4)
    b = executar_ocultacao(
        list(reversed(_lp(12))), POLITICA, meses_ocultos=(0, 6), ks=(3,), dobras=4
    )
    assert a.linhas == b.linhas


def test_recusa_poucos_contratos_e_dobras_invalidas() -> None:
    with pytest.raises(ValorInvalido, match="contratos"):
        executar_ocultacao(_lp(3), POLITICA, dobras=5)
    with pytest.raises(ValorInvalido, match="dobras"):
        executar_ocultacao(_lp(10), POLITICA, dobras=1)
    with pytest.raises(ValorInvalido, match="meses"):
        executar_ocultacao(_lp(10), POLITICA, meses_ocultos=(12,), dobras=5)


def test_recusa_contrato_sem_12_meses() -> None:
    curto = ContratoConhecido("X", Regime.LP, TODOS, (Horas.de(3),) * 11)
    with pytest.raises(ValorInvalido, match="12 meses"):
        executar_ocultacao([*_lp(9), curto], POLITICA, dobras=5)


def test_melhor_estimador_por_meses() -> None:
    r = executar_ocultacao(_lp(), POLITICA, meses_ocultos=(6,), ks=(3,), dobras=5)
    assert r.melhor(6) in {x.estimador for x in r.linhas}
    assert _linha(r, r.melhor(6), 6).epam == min(x.epam for x in r.linhas if x.meses == 6)
