# Validação por ocultação (F2.5)

Protocolo do artigo (5.15 e 10.5): para cada contrato com 12 meses, oculta-se parte da informação, infere-se o preço e mede-se o erro contra o preço-alvo conhecido, em 5 dobras (o vizinho nunca vem da dobra do contrato oculto). O erro é o EPAM do preço, `mediana(|P̂ − P*| / max(P*, menor piso))`. Código: `dominio/estimacao/ocultacao.py`; sai como a seção "Validação por ocultação (EPAM)" de `dynaprice lab relatorio`.

Estimadores: `piso_regime` (ADR-004), `credibilidade` (Z = m/(m + s²/v²) com o piso), `vizinhos_k` (Gower sobre regime e departamentos atendidos, média do alvo dos k vizinhos) e `credibilidade_com_vizinhos_k` (Eq. 55–56 do artigo). A vizinhança é só offline; a cotação usa o piso do regime.

## Carteira sintética (semente 42, 475 contratos com 12 meses)

| Estimador | 0 meses | 1 | 3 | 6 | 9 |
|---|---|---|---|---|---|
| credibilidade (com piso) | 18,5% | 1,8% | 1,6% | 1,7% | 0,6% |
| credibilidade com vizinhos (k = 10) | 22,3% | 2,3% | 2,3% | 2,1% | 0,8% |
| piso do regime | 18,5% | 18,5% | 18,5% | 18,5% | 18,5% |
| vizinhos (k = 10) | 22,3% | 22,3% | 22,3% | 22,3% | 22,3% |

**Leitura:** na carteira sintética o piso do regime erra menos que a vizinhança sem histórico, o que sustenta a ADR-004, e a credibilidade derruba o erro já no 1º mês. Atenção ao alcance: o perfil da carteira sintética tem só regime e departamentos, então a vizinhança tem pouca informação para usar. Com dados reais (F0.21), repetir o protocolo; se um perfil mais rico (porte, setor) fizer `vizinhos` vencer `piso_regime`, reabrir a opção `sem_historico: "vizinhos"` da política.
