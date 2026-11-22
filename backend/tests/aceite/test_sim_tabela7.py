"""Aceite do núcleo: simulação mw9kw9i514upw:7 "Preço-alvo e transição (Tabela 7)", passos 1 a 6.

O passo 7 (decisão humana, auditoria e arquivo) é verificado ponta a ponta em F1.31.
O passo 5 verifica o efeito observável no núcleo: o gatilho dispara (a Recomendacao PENDENTE
é criada pela recalibração, F1.26).
"""

from decimal import Decimal

from dynaprice.dominio.modelos import (
    Competencia,
    Departamento,
    Dinheiro,
    Direcionadores,
    Empresa,
    Regime,
    Vinculo,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import (
    AgregadorDeContratos,
    EquacoesDeTempo,
    GatilhoDeRevisao,
    InferenciaDePreco,
    NivelDeInformacao,
    PisoDoRegime,
    PoliticaDePreco,
    RegraDeTransicao,
    arredondamento_da_politica,
    ciclos_ate_o_alvo,
)
from tests.dominio.modelos.documentos import documento_tabela_7

REF = Competencia(2025, 12)
MES = {"notas_entrada": Decimal(30), "lancamentos_manuais": Decimal(40), "empregados": Decimal(2)}


def test_sim_mw9kw9i514upw_7_preco_alvo_e_transicao_tabela_7() -> None:
    politica = fabricar_politica(documento_tabela_7()).publicar()
    equacoes = EquacoesDeTempo(politica)
    preco = PoliticaDePreco(politica)

    # 1. Direcionadores médios de 12 meses: nível 2, segmento LP
    empresa = Empresa("cliente-lp", Regime.LP)
    meses = [Direcionadores(empresa.id, REF.somar(-i), MES) for i in range(12)]
    vinculo = Vinculo(empresa.id, "contrato-lp", desde=Competencia(2020, 1), principal=True)
    (contrato,) = AgregadorDeContratos(equacoes).agregar(REF, [empresa], [vinculo], meses).contratos
    inferido = InferenciaDePreco(preco, PisoDoRegime(politica)).preco(
        contrato.regime, contrato.horas_padrao.total, contrato.meses
    )
    assert inferido.nivel is NivelDeInformacao.COMPLETO and inferido.nivel.ell == 2
    assert contrato.regime is Regime.LP

    # 2. Horas-padrão por departamento
    hpad = contrato.horas_padrao
    assert round(hpad.horas(Departamento.FISCAL), 3) == Decimal("2.785")
    assert round(hpad.horas(Departamento.CONTABIL), 3) == Decimal("2.483")
    assert round(hpad.horas(Departamento.FOLHA), 3) == Decimal("0.667")
    assert hpad.total.valor == Decimal("5.935")

    # 3. Aplicação da política: 103,5 x 5,935 = 614,27 > 235; κ = 1
    alvo = preco.preco_alvo(contrato.regime, hpad.total)
    assert alvo.valor == inferido.valor == Dinheiro.de("614.27")
    assert not alvo.piso_vinculante
    assert round(preco.ponto_de_quebra(Regime.LP).valor, 2) == Decimal("2.27")

    # 4. Distância ao alvo: P0 = 437, G = 1,41, t* = 3
    vigente = Dinheiro.de("437")
    distancia = alvo.valor.valor / vigente.valor
    assert round(distancia, 2) == Decimal("1.41")
    assert ciclos_ate_o_alvo(distancia, politica.teto_real_theta) == 3

    # 5. Gatilho: |ln(437/614,27)| = 0,34 > ln 1,15 = 0,14 → recomendação gerada
    avaliacao = GatilhoDeRevisao(politica.gatilho_delta).avaliar(vigente, alvo.valor)
    assert round(abs(avaliacao.desvio), 2) == Decimal("0.34")
    assert round(avaliacao.limiar, 2) == Decimal("0.14")
    assert avaliacao.dispara

    # 6. Trajetória sem inflação, Decimal ROUND_HALF_UP (D11), sem ultrapassar o alvo
    transicao = RegraDeTransicao(politica.teto_real_theta, arredondamento_da_politica(politica))
    trajetoria = [vigente]
    while trajetoria[-1] < alvo.valor:
        trajetoria.append(transicao.proximo(trajetoria[-1], alvo.valor).novo)
    assert trajetoria == [Dinheiro.de(v) for v in ("437", "502.55", "577.93", "614.27")]
    assert all(p <= alvo.valor for p in trajetoria)
