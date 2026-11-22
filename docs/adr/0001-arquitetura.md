# ADR-001 — Cliente-servidor, backend em Clean Architecture, PostgreSQL

**Estado:** proposta (aguarda aprovação) · **Data:** 2026-11-09

## Contexto
O artigo exige independência de infraestrutura (RNF09), isolamento multi-inquilino imposto pelo banco (RNF03), preço decomponível e auditável (RNF07, RNF06). A carteira tem cerca de 10³ clientes por inquilino, a recalibração é mensal e são poucos usuários.

## Decisão
1. **Cliente-servidor:**
   - **Cliente:** SPA em React + TypeScript, que só apresenta dados e não contém regra de preço.
   - **Servidor:** API JSON versionada (`/api/v1`), cujo contrato é o **OpenAPI** gerado pelo backend. Os tipos TypeScript do cliente são gerados desse contrato.
2. **Backend em Clean Architecture** com 4 anéis (Entidades → Casos de uso → Adaptadores → Frameworks e drivers); a dependência aponta sempre para dentro. As portas do artigo são as interfaces do anel 2.
3. **Monólito modular:** um pacote e uma imagem, com três entradas (`api`, `worker`, `cli`).
4. **PostgreSQL** como único estado: RLS forçada, DDL transacional, índices parciais, `LISTEN/NOTIFY`, fila `core.job` com `SKIP LOCKED`, `JSONB` e `pgcrypto`.
5. **Mesma origem:** o proxy serve a SPA em `/` e encaminha `/api` ao backend. Assim não há CORS, e o cookie de renovação pode ser `SameSite=Strict`.
6. **Cerimônia mínima:** sem presenter nem interfaces de entrada/saída por caso de uso. Os casos de uso usam dataclasses do domínio; Pydantic só aparece na borda HTTP.
7. **Exceção declarada:** `dominio/estimacao` pode importar numpy, pandas, scikit-learn e statsmodels. A regra é verificada no CI por import-linter.
8. **Autorização é regra de negócio:** quem pode publicar política ou decidir recomendação é verificado nos casos de uso (anel 2), a partir do `Principal` extraído do token.

## Estrutura
```
backend/dynaprice/
  dominio/{modelos,precificacao,estimacao}/          # anel 1
  aplicacao/portas/  aplicacao/*.py                  # anel 2 (inclui autenticar.py, renovar_sessao.py)
  adaptadores/entrada/{api,worker,cli}/              # anel 3
  adaptadores/saida/{postgres,conectores/{dominio,omie,planilha},exportadores,seguranca}/
  principal.py                                       # anel 4: composição e partida
frontend/src/
  app/ (providers, rotas, guarda por papel)
  features/{auth,diagnostico,laboratorio,cotacao,recomendacoes,politicas,admin}/
  shared/{api (gerado do OpenAPI),ui,graficos,lib}/
```

## Alternativas consideradas
- **MySQL:** rejeitado. Sem RLS, sem DDL transacional e sem índice parcial.
- **Interface server-rendered (HTMX):** substituída pela SPA React, por decisão de produto (cliente-servidor explícito).
- **Microsserviços:** rejeitados neste porte.

## Consequências
- (+) A regra de preço tem uma implementação só, no backend, testável sem banco.
- (+) O contrato OpenAPI tipa o frontend: mudança incompatível na API quebra o build do cliente, e não a produção.
- (−) Dois projetos para construir e publicar (`backend/` e `frontend/`) e uma esteira de CI com dois estágios.

## Atualização 2026-11-09 (F0.1, decisão D-PY)
Python **3.14** no lugar da 3.12 (ver `docs/versoes.md`): ciclo com um ano de correções, suporte até 2030-10 e wheels de todas as dependências.
