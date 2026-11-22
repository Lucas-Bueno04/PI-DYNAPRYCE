# ADR-004 — Sem dados operacionais, o preço provisório é o piso do regime tributário

**Estado:** aceita — regra definida pelo escritório em 2026-11-09

## Contexto
O artigo (seções 5.15 e 6.9, Algoritmo 2) precifica um contrato sem histórico pela média dos preços-alvo de vizinhos semelhantes (Gower + kNN). Quando não há informação nenhuma, usa a média dos preços praticados (π0). O escritório adota outra regra: pisos por regime tributário e, sem dados, o piso do regime.

## Decisão
1. **Segmentação principal declarada = regime tributário** (MEI, Simples Nacional, Lucro Presumido, Lucro Real). Os pisos π_r são definidos na análise de cada empresa/carteira e publicados na versão de política.
2. **Regime obrigatório** em todo contrato e cotação (é sempre conhecido pelo CNPJ). O "nível 0 sem nenhuma informação" deixa de existir.
3. **Cascata de preço:**

| Situação | Preço | Natureza |
|---|---|---|
| 12 meses de direcionadores (ℓ = 2) | κ·max(π_r, τ·H_pad) | definitivo, segue a transição |
| 1 a 11 meses (ℓ = 1 com histórico) | κ·[Z·max(π_r, τ·H_pad,pr) + (1 − Z)·π_r], Z = m/(m + s²/v²) | provisório |
| Sem histórico (cotação de cliente novo) | π_r do regime | provisório |

4. **Revisão integral** do provisório (sem o teto θ) quando o contrato chega a ℓ = 2, como na seção 6.7.
5. **Inferência por vizinhos (Gower/kNN)** fica fora do MVP como opção da política (`sem_historico: "piso_regime" | "vizinhos"`), avaliável em F2/F3 pelo protocolo de ocultação.

## Consequências
- (+) Regra simples de explicar ao cliente e sem dependência de vizinhança: sai um componente do caminho crítico da cotação.
- (−) **Risco de subprecificação** no período provisório: o piso é o menor preço admissível, e clientes novos de alto esforço pagam o piso até ter histórico. Mitigação: a credibilidade passa a pesar o esforço próprio já no 1º mês de dados; revisão integral em ℓ = 2; relatório mensal de "provisórios abaixo do esforço medido".
- (−) **Incentivo** (seção 6.10): o ganho máximo de um cliente que demora a fornecer dados é limitado pelo número de meses até os dados chegarem. Como os direcionadores vêm da própria execução do serviço, isso tende a ser 1 a 2 meses.
