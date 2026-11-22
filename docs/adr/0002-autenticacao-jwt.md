# ADR-002 — Autenticação por JWT emitido pelo backend

**Estado:** proposta · **Data:** 2026-11-09

## Decisão
| Item | Definição |
|---|---|
| Emissor | O próprio backend (caso de uso `Autenticar`, porta `EmissorDeTokens`) |
| Token de acesso | **JWT ES256**, 15 min. Claims: `iss`, `aud`, `sub`, `tid` (inquilino), `roles` (analisar, aprovar, administrar), `iat`, `exp`, `jti`. Cabeçalho `kid` para rotação de chave |
| Onde fica no cliente | **Só na memória** da SPA (nunca em `localStorage`/`sessionStorage`); enviado como `Authorization: Bearer` |
| Token de renovação | Opaco, aleatório de 256 bits, guardado no banco **só como hash** (SHA-256), com família, rotação a cada uso e **detecção de reuso** (reuso revoga a família inteira). Validade de 12 h por inatividade e 7 dias absolutos |
| Transporte do refresh | Cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`. A rota `/auth/renovar` também confere o cabeçalho `Origin` |
| Senha | Argon2id |
| MFA | TOTP (RF11), obrigatório para os papéis `aprovar` e `administrar` |
| Chaves | Par ES256 injetado por segredo da implantação. Chaves públicas em `/api/v1/auth/jwks.json`. Rotação: nova chave assina, a antiga só valida até expirar |
| Validação | Middleware no adaptador de entrada: assinatura, `iss`, `aud`, `exp` (tolerância de 30 s) → `Principal(usuario, tenant, papeis)` |
| Autorização | Nos casos de uso (anel 2) |
| Isolamento | O `tid` do token vira `set_config('app.tenant_id', …, true)` em cada transação, e a RLS do PostgreSQL faz o resto |
| Sair | Revoga a família de refresh; o token de acesso expira em até 15 min |
| Proteção contra força bruta | Limite por IP e por conta, com atraso progressivo, auditado |

## Alternativas
- **Provedor OIDC externo (Keycloak etc.):** adiado para F3, como **federação**: o backend aceita login federado e continua emitindo o próprio JWT. A porta `Identidade` já permite.
- **Sessão em cookie com estado no servidor:** mais simples, mas o pedido foi JWT, e o JWT permite clientes futuros (integrações, mobile) sem mudança.
- **HS256:** rejeitado. A chave simétrica teria de ser compartilhada com qualquer verificador.

## Consequências
- (+) Sem dependência de serviço externo para logar.
- (−) O backend passa a ser responsável por senha, MFA, bloqueio e rotação de chave, e esse código precisa de revisão de segurança dedicada.

## Complementos (revisão 2)
- **Vários inquilinos por usuário:** o login devolve os inquilinos disponíveis; `POST /auth/inquilino` emite um par de tokens para o `tid` escolhido.
- **Recuperação:** link de redefinição de uso único (hash, 30 min); 10 códigos de recuperação do MFA guardados em Argon2id; toda recuperação revoga as sessões e é auditada.
- **Banco:** as tabelas de `auth` ficam fora da RLS por inquilino e só os casos de uso de autenticação as acessam.
