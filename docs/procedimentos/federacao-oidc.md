# Entrada por OIDC (F3.2)

O IdP prova quem é a pessoa; **conta, papéis e MFA continuam nossos** (ADR-002: o JWT segue próprio). O IdP nunca cria conta: o e-mail precisa estar verificado no IdP e casar com um usuário ativo já cadastrado. Depois disso o fluxo é o mesmo da senha: TOTP, cadastro de MFA (papéis `aprovar` e `administrar`) ou sessão.

## Ligar

Sem variáveis, as rotas respondem 404 e a SPA não mostra o botão. Para ligar, no serviço `api`:

| Variável | Conteúdo |
|---|---|
| `DYNAPRICE_OIDC_EMISSOR` | URL do emissor (`issuer`), com HTTPS |
| `DYNAPRICE_OIDC_CLIENTE_ID` | client id registrado no IdP |
| `DYNAPRICE_OIDC_SEGREDO_FILE` | caminho do arquivo (secret do compose) com o client secret |

No IdP, registrar a URI de retorno `https://<origem>/api/v1/auth/oidc/retorno`. A descoberta (`/.well-known/openid-configuration`) roda na partida; emissor diferente do configurado ou endpoint sem HTTPS impede a API de subir.

## O que foi defendido (testes em `tests/adaptadores/test_oidc.py`, `tests/aplicacao/test_federacao.py`, `tests/api/test_federacao.py`)

- Código de autorização com **PKCE S256**, `state` e `nonce` por tentativa; o estado viaja em JWT assinado num cookie HttpOnly/Secure/SameSite=Lax de 10 minutos, com audiência própria (não serve como token de acesso nem desafio).
- `id_token`: só RS256/ES256 (HS256 e `none` recusados), assinatura pelas chaves do IdP (JWKS com cache de 10 min), `iss`, `aud`, `exp`, `nonce`; `email_verified` precisa ser o booleano `true`.
- Falhas voltam a `/entrar?erro=federacao` sem detalhe. O desafio de MFA vai no **fragmento** da URL, nunca na consulta, e a SPA o remove da barra.
- Troca de inquilino do consultor: `POST /api/v1/auth/inquilino`; o token novo só enxerga o inquilino novo (`tests/api/test_consultor.py`).

## Pendente (depende do escritório)

Registro do cliente no IdP real e conferência de `email_verified` e dos escopos desse IdP. Rodar o fluxo ao vivo uma vez no piloto (F1.42) com um usuário de teste.
