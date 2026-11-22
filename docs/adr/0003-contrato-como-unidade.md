# ADR-003 — O contrato é a unidade de precificação

**Estado:** aceita quanto à cobrança — o escritório confirmou em 2026-11-09 que cobra **por contrato** (um piso por contrato, independentemente do número de CNPJs) · regra de segmento da empresa principal ainda a validar

## Contexto
O artigo modela "cliente" como uma linha com horas, direcionadores e honorário. Na prática, o honorário é cobrado por **contrato**, e um contrato pode cobrir várias empresas (matriz, filiais, folha separada, holding). No caso estudado, cerca de 1/3 das empresas ativas não tinha honorário próprio (seção 9.1), e o artigo as excluiu da modelagem. Num produto, excluir não é opção: essas empresas geram esforço que alguém paga.

## Decisão
- `Empresa`: unidade **operacional**. Tem direcionadores, horas e perfil, e pertence a exatamente um `Contrato` em cada competência.
- `Contrato`: unidade **comercial**. Tem segmento, preço vigente, mês de reajuste, κ e estado provisório.
- H_pad(contrato) = Σ H_pad(empresas), com as equações de tempo aplicadas **por empresa**, porque o tempo fixo β0 existe para cada CNPJ escriturado.
- **Piso aplicado uma vez por contrato** (confirmado pelo escritório).
- Segmento do contrato = segmento da empresa principal (marcada no vínculo). Ainda a validar com o escritório.
- O nível de informação é o do contrato: o menor nível entre as empresas, com o mínimo de meses entre elas.
- A estimação (Huber/Ridge) continua **por empresa**. A tarifa (τ̂ = ΣF/ΣH_pad) e a política são **por contrato**.

## Consequências
- (+) Nenhum esforço fica sem preço; a "pendência de vínculo" vira um fluxo visível.
- (+) A matemática do artigo não muda: só a agregação antes da política.
- (−) É preciso um mapa de vínculos mantido pelo escritório (RF03), com histórico por competência.
