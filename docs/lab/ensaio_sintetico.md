# Ensaio do laboratório com a carteira sintética (contorno de F0.22)

Enquanto a planilha real (F0.20) e o acesso ao Domínio (F0.21) dependem do escritório, o laboratório roda de ponta a ponta sobre a carteira sintética (semente 42). Os números servem para provar o pipeline e o rascunho de política usado no desenvolvimento da F1. **Não valem para as decisões D1, D2, D3, D4, D10 e D13**: estas saem da F0.22 com dados reais.

Reproduzir: `cd backend && uv run dynaprice lab sintetico --semente 42 --saida build/sintetico-42 && uv run dynaprice lab relatorio --entrada build/sintetico-42 --saida build/relatorio-sintetico`.

| Grandeza | Sintético (semente 42) | Artigo |
|---|---|---|
| τ̂ (Eq. 65) | 115,15 | 103,5 |
| τ* (Eq. 67) | 114,48 | ≈ 100 |
| ϱ | 0,847 | 0,85 |
| R² CV do Ridge | 0,871 | 0,77 |
| Pisos P10 (MEI, SN, LP, LR) | 194,46; 200,75; 221,48; 251,66 | 80; 185; 235; 340 (mascarados) |
| s²/v² | 0,045 | — |

## Tempo (A3 da F0.22, medido na máquina de desenvolvimento)

| Contratos | Laboratório completo | Recalibração (agregação, alvo, transição) |
|---|---|---|
| 500 | 2,2 s | 0,18 s |
| 5.000 | 23,5 s | 1,78 s |

A recalibração mensal de um inquilino com 5.000 contratos fica em ~2 s no núcleo, muito abaixo da meta de 5 minutos (RNF, a confirmar); o custo real vai depender da extração (F1.23) e do banco (F1.9).
