"""F0.12: k_gat — gatilho de revisão com zona morta simétrica em log (Eq. 74)."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import Dinheiro
from dynaprice.dominio.precificacao import DirecaoDoDesvio, GatilhoDeRevisao

GATILHO = GatilhoDeRevisao(Decimal("0.15"))
precos = st.decimals(min_value=Decimal(10), max_value=Decimal(10000), places=2).map(Dinheiro)


def test_tabela_7_dispara() -> None:
    avaliacao = GATILHO.avaliar(Dinheiro.de("437"), Dinheiro.de("614.27"))
    assert avaliacao.dispara
    assert round(abs(avaliacao.desvio), 2) == Decimal("0.34")
    assert avaliacao.direcao is DirecaoDoDesvio.ABAIXO


def test_zona_morta_nao_dispara() -> None:
    assert not GATILHO.avaliar(Dinheiro.de("114"), Dinheiro.de("100")).dispara  # +14%
    assert not GATILHO.avaliar(Dinheiro.de("87"), Dinheiro.de("100")).dispara  # -13%
    assert GATILHO.avaliar(Dinheiro.de("116"), Dinheiro.de("100")).dispara
    assert GATILHO.avaliar(Dinheiro.de("86"), Dinheiro.de("100")).dispara


def test_direcao_acima() -> None:
    assert GATILHO.avaliar(Dinheiro.de("200"), Dinheiro.de("100")).direcao is DirecaoDoDesvio.ACIMA


@given(precos, precos)
def test_simetria_multiplicativa(p: Dinheiro, alvo: Dinheiro) -> None:
    """|ln(P/P*)| = |ln(P*/P)|: subir ou descer pelo mesmo fator dispara igual."""
    assert GATILHO.avaliar(p, alvo).dispara == GATILHO.avaliar(alvo, p).dispara


@given(precos)
def test_preco_no_alvo_nunca_dispara(p: Dinheiro) -> None:
    assert not GATILHO.avaliar(p, p).dispara
