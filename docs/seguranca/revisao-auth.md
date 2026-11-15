# Revisão de segurança da autenticação (F1.20)

**Quem revisou:** agente revisor de segurança da Ada (`ada:seguranca`), independente do agente que escreveu o código, em duas rodadas, 2026-11-11. **Não houve revisão humana.** Uma revisão por pessoa continua recomendada antes do piloto com dados reais.

**Escopo:** ADR-002 inteira: casos de uso de autenticação, usuários e recuperação; autorização; cifrador, senhas e JWT; repositórios de `auth`; funções `SECURITY DEFINER` da migração; API de autenticação; composição e implantação.

**Método:** leitura do código. Parte das corridas foi concluída pela leitura; as correções têm teste que reproduz o achado (`tests/aplicacao/test_autenticar.py`, `test_recuperar_acesso.py`, `test_usuarios.py`).

## Achados altos: todos corrigidos

| # | Achado | Correção |
|---|---|---|
| A1 | `/auth/inquilino` aceitava refresh revogado, usado ou expirado, e a sessão sobrevivia à revogação | Validador único de refresh em todas as rotas; a família nova herda a validade e o MFA |
| A2 | Senha correta zerava o contador e permitia força bruta de TOTP | Com MFA ativo, só o TOTP correto zera |
| A3 | `/auth/recuperar-mfa` sem limite e com oráculo de tempo | Bloqueio por conta e IP; sempre duas verificações Argon2 |
| A4 | Login concorrente regravava a linha e desfazia desativação ou nova senha | Só escritas pontuais; não existe mais regravação da linha |
| N1 | Estouro no cálculo do bloqueio desligava todos os limites depois de 47 falhas | Expoente limitado; teste com 10.000 falhas |

## Achados médios

| # | Achado | Situação |
|---|---|---|
| M1 | Administrador agia sobre a conta global de usuário de vários inquilinos | Corrigido; reavaliar a checagem ao consumir o link quando existir vínculo a um segundo inquilino |
| M2 | Limite por IP zerava com login válido | Corrigido: decaimento por janela |
| M3 | Atrás de proxy, todos os clientes contam como um IP | **Aberto até a F1.37**: falta definir `DYNAPRICE_PROXY_CONFIAVEL` com o IP exato do proxy, nunca `*` |
| M4 | Corrida no contador de falhas e no replay de TOTP | Corrigido: contador atômico e passo condicional |
| N2 | Login em andamento abria sessão depois da redefinição | Corrigido: releitura com trava antes de abrir a sessão |

## Achados baixos

Corrigidos: B1, B5, B6, B7, N3, N4, N5, N6 e parte de B8 (`no-store` e segredos do worker).

Abertos, aceitos no MVP:
- **B2:** resposta 429 revela que a conta existe.
- **B3:** o contador de falhas da conta não decai com o tempo.
- **B4:** o desafio de MFA não é de uso único nem ligado à credencial.
- **B8 (resto):** `dynaprice_app` tem acesso total a `auth.*` e é compartilhado com o worker; `core.tenant.estado = 'suspenso'` não é checado na autenticação.
