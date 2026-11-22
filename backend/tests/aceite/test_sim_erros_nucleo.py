"""Aceite F0.15: simulações de erro do núcleo (lacuna 9.5 do plano; fluxo 4.1)."""

from decimal import Decimal

import pytest

from dynaprice.dominio.modelos import Dinheiro, Empresa, Horas, Kappa, Regime, ValorInvalido
from dynaprice.dominio.precificacao import DirecaoDoDesvio, MotivoDoPasso
from tests.aceite.nucleo import nucleo


def test_sim_mw9kw9i514upw_8_piso_vinculante_e_alvo_abaixo_do_vigente() -> None:
    n = nucleo()
    # 1. Só os tempos fixos: H_pad = Σβ0 = 1,75 h
    hpad = n.equacoes.horas_padrao(Empresa("sn-pequeno", Regime.SN), {}).total
    assert hpad == Horas.de("1.75")
    # 2. Piso vinculante: 103,5 x 1,75 = 181,13 < 185
    alvo = n.preco.preco_alvo(Regime.SN, hpad)
    assert alvo.piso_vinculante
    assert alvo.valor == Dinheiro.de("185")
    # 3. Gatilho acima do alvo
    vigente = Dinheiro.de("250")
    avaliacao = n.gatilho.avaliar(vigente, alvo.valor)
    assert avaliacao.dispara and avaliacao.direcao is DirecaoDoDesvio.ACIMA
    assert round(avaliacao.desvio, 2) == Decimal("0.30")
    # 4. Congelamento nominal com inflação de 4%
    passo = n.transicao.proximo(vigente, alvo.valor, inflacao=Decimal("0.04"))
    assert passo.corrigido == Decimal("260.00")
    assert passo.novo == Dinheiro.de("250")
    assert passo.motivo is MotivoDoPasso.CONGELADO


def test_sim_mw9kw9i514upw_9_desvio_dentro_da_zona_morta() -> None:
    n = nucleo()
    # 1. Preço vigente perto do alvo (cliente da Tabela 7)
    alvo = n.preco.preco_alvo(Regime.LP, Horas.de("5.935")).valor
    assert alvo == Dinheiro.de("614.27")
    # 2. Dentro da zona morta: nenhuma recomendação
    avaliacao = n.gatilho.avaliar(Dinheiro.de("580"), alvo)
    assert round(abs(avaliacao.desvio), 3) == Decimal("0.057")
    assert round(avaliacao.limiar, 3) == Decimal("0.140")
    assert not avaliacao.dispara


def test_sim_mw9kw9i514upw_10_kappa_fora_de_kappa_barra() -> None:
    n = nucleo()
    hpad = Horas.de("5.935")
    # 1. κ = 1,3 > κ̄ = 1,2: rejeitado, nenhum preço criado
    with pytest.raises(ValorInvalido):
        n.preco.preco_alvo(Regime.LP, hpad, Kappa.de("1.3"))
    # 2. κ = 0,9 < 1: rejeitado (A1/A2)
    with pytest.raises(ValorInvalido):
        n.preco.preco_alvo(Regime.LP, hpad, Kappa.de("0.9"))
    # 3. κ = 1,2 no teto: 1,2 x 614,2725 = 737,13
    assert n.preco.preco_alvo(Regime.LP, hpad, Kappa.de("1.2")).valor == Dinheiro.de("737.13")
