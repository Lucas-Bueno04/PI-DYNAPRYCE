# Acesso somente leitura ao Domínio (F0.21)

**Situação em 2026-11-09: não acessível a partir do ambiente de desenvolvimento.** Depende da TI do escritório e da aprovação do responsável, e o servidor MCP `dominio` desta máquina não conectou (tempo esgotado). **Plano B pronto:** planilha no layout de `docs/lab/layout_planilha.md` (F0.20), lida por `LeitorDePlanilhaDoEscritorio` com pseudonimização na entrada.

## Roteiro com a TI do escritório (quando for executado)

| Item | O que registrar | Situação |
|---|---|---|
| SGBD e versão | produto (o Domínio usa SQL Anywhere/Sybase na maioria das instalações; confirmar) e versão | a confirmar |
| Driver ODBC para Linux | nome, versão e licença (SAP SQL Anywhere ODBC; checar se a licença do escritório cobre o uso) | a confirmar |
| Caminho de rede | host/porta do servidor do Domínio na rede do escritório (D9: a stack roda na mesma rede) | a confirmar |
| TLS | se o servidor aceita conexão cifrada; senão, restringir por rede e registrar o risco | a confirmar |
| Usuário | somente leitura, só as tabelas de contagem (notas, lançamentos, folha agregada) | a criar pela TI |
| Consulta de contagem | uma `SELECT COUNT(*)` por tabela, fora do expediente | a executar |

**Risco:** carga no banco de produção do escritório; só consultas de contagem fora do expediente. **Reversão:** revogar o usuário.
