# Calibração da carteira sintética (insumo da F0.6)

O gerador sintético reproduz as **estatísticas publicadas** no artigo (seção 9; os valores monetários são mascarados, mas razões, elasticidades, R² e Gini são reais, pela Prop. 1). Ele não reproduz dado nenhum do escritório: serve para testes, CI e demonstração. Cada alvo abaixo vira um teste de faixa em `tests/sintetico`, com semente fixa.

## Tamanho e estrutura

| Parâmetro | Alvo | Fonte |
|---|---|---|
| Contratos | ~500 (parametrizável) | 4.2 |
| Empresas sem honorário próprio (filiais, folhas, holdings vinculadas a outro contrato) | ~1/3 das empresas, ~11% das horas | 9.1 |
| Empresas com horas e sem vínculo de cobrança | ~10% (vão para "pendências de vínculo", ADR-003) | 9.1 |
| Contratos com empresas de regimes diferentes | parâmetro (padrão 5%), para testar D1 | ADR-003 |
| Regimes | MEI, SN, LP, LR; proporções parametrizáveis (padrão: maioria SN) | 3.3, 9.9 |
| Atividade econômica preenchida | ~22% | 9.1 |
| Meses | 12 fechados por empresa; parâmetro para gerar histórico parcial (ADR-004) | 4.2 |

## Esforço e direcionadores

| Parâmetro | Alvo | Fonte |
|---|---|---|
| Horas registradas do cliente mediano | ~2,5 h/mês | 9.1 |
| Horas por departamento | contábil 48%, fiscal 30%, folha 20% | 9.1 |
| Decil 1 × decil 10 de horas (medianas) | 0,4 h × 21,7 h (razão ~50) | Tabela 3 |
| Equações de tempo verdadeiras (geradoras) | fiscal β0 = 0,91 h, nota de entrada 3,75 min, nota de saída 0,08 min; contábil β0 = 0,79 h, lançamento manual 2,54 min, automático ≈ 0; folha β0 = 0,05 h, empregado-mês 18,5 min, admissão 116 min, rescisão 84 min | Tabela 4 |
| Razão horas-padrão / registradas (ϱ) | ~0,85 | 9.7 |
| Erro de medida multiplicativo (eq. 2) | ln H = ln H* + w, com w calibrado para R² ≈ 0,64 das horas-padrão (dentro da amostra) e ≈ 0,77 do Ridge em CV | 9.7, 9.8 |
| Atípicos (Huber) | 11% com horas > 2× o previsto; 9% < 0,5× | 9.8 |
| Elasticidades simples das horas | faturamento 0,25; notas 0,54; lançamentos ~0,6; folha/empregados 0,75 | Tabela 2 |
| R² (log) de um direcionador isolado | faturamento 0,23; notas 0,44; lançamentos 0,67 | Tabela 2 |
| Gini | notas 0,86; horas 0,65; honorário 0,51 | 9.5 |
| Sazonalidade | concentração de fechamentos no 1º semestre (índices mensais parametrizáveis) | 6.3 |
| Tendência no período | notas de saída/serviço +68%, entrada +39%, horas +19%, lançamentos −39% (1º × último trimestre) | 9.6 |

## Preço praticado (a regra regressiva que a política corrige)

| Parâmetro | Alvo | Fonte |
|---|---|---|
| Regra implícita | F = a + b·H, com a ≈ 213 u.m. e b ≈ 32 u.m./h, mais ruído | 9.4 |
| Honorário mediano | ~316 u.m. | 9.1 |
| Receita média por hora registrada (P̄) | ~88 u.m./h | 9.1 |
| Decis extremos de honorário | 226 × 867 u.m. (razão 3,8) | Tabela 3 |
| Elasticidade honorário × faturamento | 0,17–0,18 | Tabela 2 |
| Índice de alinhamento I_i | quartis 0,76 e 2,74 | 9.5 |
| Razões entre regimes | LR consome 2,4× as horas de LP e paga 1,28×; LP consome 2,1× as de SN e paga 1,39× | 9.4 |
| Reajuste anual | mediana 4,3% (IQR 4,0–4,6%), independente da variação do esforço | 9.6 |

## Valores esperados ao aplicar a política (verificação do gerador)

| Grandeza | Esperado | Fonte |
|---|---|---|
| τ̂ (preço revelado) | ≈ 88 / 0,85 ≈ 103,5 u.m./h-padrão | eq. 97 |
| τ* (receita constante) | ≈ 100 u.m./h-padrão, ~39% dos clientes no piso | 9.9 |
| τ̂ / τ* | ≈ 1,035 | Prop. 7, 9.9 |
| Pisos de referência (mascarados) | MEI 80, SN 185, LP 235, LR 340 | 9.9 |
| Elasticidade preço × esforço | 0,36 (praticado) → 0,46 (política, cenário de referência) | Tabela 6 |

As faixas de tolerância de cada teste ficam no próprio teste, porque uma amostra finita com semente não reproduz o valor exato. O gerador é validado pela **forma**: as mesmas ordens de grandeza e os mesmos sinais e razões do artigo.

## Calibração adotada (F0.6, 2026-11-09)

- **Unidade:** as estatísticas do "cliente" do artigo são conferidas **por contrato** (ADR-003). Empresas extras (filiais, folha separada) têm 5–30% do tamanho do contrato e atendem **um** departamento (`Empresa.departamentos`): sem isso, o β0 fiscal de 0,91 h de cada CNPJ extra contradiz os ~11% das horas do artigo.
- **Tensão entre alvos:** com F = a + b·H (a ≈ 213, b ≈ 32), P̄ ≈ 88 u.m./h exige média de ~3,8 h por cliente; com mediana 2,5 h e o piso de β0 (1,75 h por empresa, ≈ 2 h registradas), a razão de decis de ~50 é inalcançável sem quebrar P̄. Priorizados **τ̂ ≈ 103,5 e P̄ ≈ 88** (entram no preço e nas decisões D2/D3); a razão de decis fica ~8 (o teste exige ≥ 6, cauda pesada).
- **Parâmetros:** `mediana_tamanho = 0,12`, `sigma_tamanho = 1,2`; médias base por mês (escala 1): notas de entrada 1, de saída 15, lançamentos manuais 30, automáticos 30, empregados 4 (admissões 5%, rescisões 4%). Semente 42: mediana 2,5 h/contrato, τ̂ ≈ 103,0, P̄ ≈ 89,5; horas fiscal 38%, contábil 44%, folha 19% (artigo 30/48/20: o β0 fiscal de 0,91 h pesa nas empresas pequenas).
- **Não gerados:** atividade econômica (só usada pela vizinhança/Gower, fora do MVP pela ADR-004), tendência anual e reajuste de 4,3% (honorário constante na janela). Entram se F0.18/F2.5 precisarem.

## Limitações conhecidas do sintético (vistas no relatório da F0.19)

- **Gini** de horas (~0,37) e honorários (~0,19) abaixo do artigo (0,65 e 0,51): efeito da priorização de τ̂ e P̄ (G1-CAL).
- **Honorário sem efeito de regime**: o sintético usa F = a + b·H para todos; no artigo o LR paga 1,28x o LP e o LP 1,39x o SN. Por isso o piso proposto do MEI (P10) sai perto do SN. Não afeta a lógica, só os números do sintético.
- **R² do Huber fiscal baixo**: com notas de entrada médias de 1/mês, quase todo o tempo fiscal é β0, e o R² das horas registradas mede só ruído. O β estimado continua dentro da faixa do gerador.
- Os números que valem para as decisões D1–D4, D10 e D13 saem da F0.22, com dados reais.
