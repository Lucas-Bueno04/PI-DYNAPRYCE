# Versões e licenças (F0.1 e F1.1)

Consulta feita em **2026-11-09**, a partir das fontes oficiais: API JSON do PyPI (`https://pypi.org/pypi/<pacote>/json`, versão mais recente, data do primeiro upload, `requires_python`, licença) e o ciclo de vida do Python (`https://endoflife.date/api/python.json`, que espelha o python.org). As versões abaixo são **mínimas**; as exatas ficam travadas no `uv.lock`.

## Python

| Ciclo | Última | Lançamento do ciclo | Fim de suporte |
|---|---|---|---|
| 3.15 | 3.15.2 | 2026-10 | 2031-10 |
| **3.14** | 3.14.10 | 2025-10 | **2030-10** |
| 3.13 | 3.13.18 | 2024-10 | 2029-10 |
| 3.12 (ADR-001) | 3.12.16 | 2023-10 | 2028-10 |

- A máquina local tem Python 3.12.3. O uv (0.13.7) instala outras versões, gerenciadas por ele.
- Wheels `manylinux` para cp313, cp314 e cp315 existem em numpy, scipy, pandas, scikit-learn e statsmodels.
- **Diferença com a ADR-001:** a estável atual é a 3.15, e a ADR-001 fixou a 3.12. **Decisão D-PY:** usar **Python 3.14**, a versão recomendada. O ciclo já tem um ano de correções, o suporte vai até 2030 e todas as dependências publicam wheels para ela. A 3.15 é recente demais para fixar no início (um mês). A 3.12 perde o suporte em 2028, cedo para um produto novo. A ADR-001 deve ser atualizada para 3.14.

## Backend e laboratório (F0)

| Pacote | Versão | Publicada em | Python | Licença | Observação |
|---|---|---|---|---|---|
| uv | 0.13.7 | 2026-11-03 | ≥3.8 | MIT OR Apache-2.0 | ativo |
| ruff | 0.17.4 | 2026-11-05 | ≥3.7 | MIT | ativo |
| mypy | 2.4.1 | 2026-10-28 | ≥3.10 | MIT | ativo |
| pytest | 9.2.0 | 2026-10-27 | ≥3.10 | MIT | ativo |
| hypothesis | 6.170.15 | 2026-11-06 | ≥3.11 | MPL-2.0 | ativo; MPL só afeta mudanças no próprio pacote |
| import-linter | 2.16 | 2026-11-06 | ≥3.11 | BSD-2-Clause | ativo |
| typer | 0.29.0 | 2026-11-09 | ≥3.10 | MIT | ativo |
| numpy | 2.5.4 | 2026-10-10 | ≥3.12 | BSD-3-Clause (+0BSD, MIT, Zlib, CC0 em partes) | ativo |
| scipy | 1.18.1 | 2026-08-21 | ≥3.12 | BSD-3-Clause | ativo |
| pandas | 3.1.1 | 2026-11-04 | ≥3.11 | BSD-3-Clause | ativo; a série 3.x muda o padrão de strings e o copy-on-write, por isso o código deve ser escrito já para a 3.x |
| scikit-learn | 1.9.1 | 2026-09-10 | ≥3.11 | BSD-3-Clause | ativo |
| statsmodels | 0.15.0 | 2026-08-27 | ≥3.10 | BSD-3-Clause | ativo; `RLM` + `HuberT` para a seção 5.9 |

## Backend (F1, reconferido em F1.1, 2026-11-10)

Fonte: API JSON do PyPI. Todas publicam wheel `cp314` ou `py3-none`, compatíveis com a D-PY.

| Pacote | Versão | Publicada em | Licença | Manutenção e observação |
|---|---|---|---|---|
| fastapi | 0.162.4 | 2026-11-10 | MIT | ativo |
| uvicorn | 0.54.0 | 2026-09-25 | BSD-3-Clause | ativo |
| pydantic | 2.14.3 | 2026-11-05 | MIT | ativo |
| pydantic-settings | 2.16.2 | 2026-10-28 | MIT | ativo |
| SQLAlchemy | 2.1.8 | 2026-11-04 | MIT | ativo |
| psycopg (com psycopg-binary) | 3.3.8 | 2026-11-04 | **LGPL-3.0-only** | ativo; uso como biblioteca sem alteração. **A confirmar** com o jurídico se o produto for distribuído a terceiros |
| alembic | 1.20.1 | 2026-10-22 | MIT | ativo |
| PyJWT | 2.15.1 | 2026-09-28 | MIT | ativo |
| argon2-cffi | 25.1.0 | 2025-06-03 | MIT | maduro, baixa cadência |
| pyotp | 2.10.0 | 2026-06-14 | MIT | ativo |
| cryptography | 50.0.2 | 2026-09-30 | Apache-2.0 OR BSD-3-Clause | ativo |
| httpx | 0.28.1 | 2024-12-06 | BSD-3-Clause | sem versão nova há 23 meses; mantido por ser usado só no conector Omie, atrás da porta `p_src`. O `pip-audit` da F1.38 é o sinal para trocar |
| pyodbc | 5.5.0 | 2026-11-08 | MIT-0 | ativo |
| openpyxl | 3.1.5 | 2024-06-28 | MIT | maduro, baixa cadência |
| structlog | 26.1.0 | 2026-06-06 | MIT OR Apache-2.0 | ativo |
| python-multipart | 0.0.33 | 2026-10-31 | Apache-2.0 | ativo; upload da planilha (F1.22) |
| testcontainers | 4.15.0 | 2026-07-24 | Apache-2.0 | ativo; testes de integração |

## Banco e runtime

Fonte: `https://endoflife.date/api/{postgresql,nodejs}.json`; imagens conferidas com `docker manifest inspect`.

| Componente | Ciclo | Última | Fim de suporte | Decisão |
|---|---|---|---|---|
| PostgreSQL | **18** | 18.6 (2026-08-11) | 2030-11-14 | **D-PG:** ciclo atual, com o suporte mais longo. Imagem `postgres:18.6` existe. Licença PostgreSQL |
| Node.js | **24 LTS** | 24.22.2 (2026-10-28) | 2028-04-30 | **D-NODE:** já instalado na máquina (24.22.1) e atende a todos os `engines` abaixo. O 26 só virou LTS em 2026-10-28; reavaliar na F4.1 |
| Imagem Python | 3.14 | `python:3.14-slim` | 2030-10 | existe; segue a D-PY |
| nginx (borda) | **1.30 estável** | 1.30.6 (2026-10-14) | até a 1.32 | **D-NGINX (F1.37):** linha estável (minor par), imagem sem root `nginxinc/nginx-unprivileged:1.30.6-alpine` conferida com `docker manifest inspect` em 2026-11-14. A 1.31 é mainline |

## Driver ODBC do Domínio

| Item | Situação | Evidência |
|---|---|---|
| SGBD | **a confirmar** na F0.21 (provavelmente SAP SQL Anywhere) | depende da TI do escritório |
| Driver para Linux | **a confirmar**: cliente SAP SQL Anywhere, instalado a partir do pacote da SAP, com aceite de licença na instalação | [guia Appeon para Ubuntu](https://docs.appeon.com/ps2025/Connecting_to_SQL_Anywhere_database_in_Linux.html) |
| Licença e redistribuição | **a confirmar** no SAP Software Center. Uma resposta de 2011 no fórum da SAP diz que há restrição de distribuição, o que é antigo demais para decidir | [fórum SAP](https://sqlanywhere-forum.sap.com/questions/6137/php-module-requires-an-extra-license-for-production) |
| Consequência no desenho | O driver **não entra na imagem OCI** até a licença ser lida; a F1.23 testa `a_dom` com um ODBC falso e a instalação fica para a F1.42 | decisão D-ODBC |

## Cadeia de suprimentos

Fonte: API do GitHub (`releases/latest` e licença do repositório) e PyPI.

| Ferramenta | Versão | Publicada em | Licença | Observação |
|---|---|---|---|---|
| syft | v1.57.1 | 2026-11-09 | Apache-2.0 | ativo |
| trivy | v0.76.2 | 2026-11-05 | Apache-2.0 | ativo, **com incidente grave em 2026** (abaixo). Imagem `aquasec/trivy:0.76.2` existe |
| pip-audit | 2.10.1 | 2026-06-10 | Apache-2.0 | ativo |
| npm audit | vem com o npm | — | Artistic-2.0 | ativo |
| Renovate | 44.227.4 | 2026-11-10 | **AGPL-3.0** | ativo; roda como ferramenta externa, não é ligado ao produto nem distribuído com ele |

**Incidente do Trivy (CVE-2026-33634, [GHSA-69fq-xp46-6x23](https://osv.dev/vulnerability/GHSA-69fq-xp46-6x23)).** Em março de 2026, tags de `aquasecurity/trivy-action` e `setup-trivy` foram reescritas e binários maliciosos foram publicados (0.69.4 a 0.69.6). Detalhes no [relato da Aqua](https://www.aquasec.com/blog/trivy-supply-chain-attack-what-you-need-to-know/). **Regra para a F1.38:** não usar `trivy-action`; rodar o binário por imagem fixada em digest e fixar **toda** action de terceiros por SHA completo, nunca por tag.

## Frontend

Fonte: registry do npm (`dist-tags.latest`, licença, `peerDependencies` e `engines`).

| Pacote | Versão | Publicada em | Licença | Observação |
|---|---|---|---|---|
| typescript | **5.9.3** | — | Apache-2.0 | **D-TS:** a última é a 7.0.2, mas `openapi-typescript` 7.13 exige `^5.x` e `typescript-eslint` 8.72 exige `<6.1.0`. A 5.9.3 é a maior que atende a ambos |
| react, react-dom | 19.3.1 | 2026-10-14 | MIT | ativo |
| @types/react, @types/react-dom | 19.3.0 | — | MIT | ativo |
| vite | 8.3.7 | 2026-11-09 | MIT | ativo; Node ≥22.12 |
| @vitejs/plugin-react | 6.3.0 | 2026-11-09 | MIT | ativo; pede Vite 8 |
| react-router | 8.5.1 | 2026-10-27 | MIT | ativo; Node ≥22.22 |
| @tanstack/react-query | 5.107.1 | 2026-11-06 | MIT | ativo |
| @tanstack/react-table | 9.3.1 | 2026-10-12 | MIT | ativo |
| @mantine/core, hooks, notifications | 9.8.0 | 2026-11-09 | MIT | ativo; pede React ≥19.2 |
| echarts | 6.1.0 | 2026-05-19 | Apache-2.0 | ativo |
| echarts-for-react | 3.0.6 | 2026-01-21 | MIT | aceita ECharts 6 |
| react-hook-form | 7.91.0 | 2026-10-23 | MIT | ativo |
| @hookform/resolvers | 7.0.5 | 2026-11-08 | MIT | aceita Zod 4 |
| zod | 4.6.7 | 2026-10-12 | MIT | ativo |
| openapi-typescript | 7.13.0 | 2026-02-11 | MIT | ativo; restringe o TypeScript |
| openapi-fetch | 0.17.0 | 2026-02-11 | MIT | ativo |
| eslint | 10.14.0 | 2026-10-30 | MIT | ativo |
| typescript-eslint | 8.72.2 | 2026-11-09 | MIT | ativo; restringe o TypeScript |

## Evidência para FE-TESTE e CI

**FE-TESTE (decidido: Vitest + Testing Library + Playwright).** As versões abaixo são compatíveis entre si e com Vite 8, React 19 e Node 24.

| Pacote | Versão | Publicada em | Licença | Compatibilidade |
|---|---|---|---|---|
| vitest | 5.1.0 | 2026-11-02 | MIT | aceita Vite `^8`; Node `^24` |
| @testing-library/react | 16.3.3 | 2026-08-27 | MIT | aceita React `^19` |
| @testing-library/dom | 10.4.2 | — | MIT | par exigido pelos dois pacotes da Testing Library |
| @testing-library/jest-dom | 7.0.1 | 2026-08-09 | MIT | Node ≥22 |
| @testing-library/user-event | 14.6.9 | 2026-11-10 | MIT | ativo |
| jsdom | 31.0.0 | 2026-11-05 | MIT | Node `^24.15`; a máquina tem 24.22.1 |
| @playwright/test | 1.65.0 | 2026-11-05 | Apache-2.0 | Node ≥20 |

**CI (decidido: GitHub Actions + GHCR).** Versões para a F1.38, a serem fixadas por SHA conforme a regra acima. O remoto no GitHub ainda precisa ser criado pelo responsável.

| Action | Versão | Publicada em | Licença |
|---|---|---|---|
| actions/checkout | v7.0.1 | 2026-07-20 | MIT |
| actions/setup-node | v7.1.0 | 2026-10-08 | MIT |
| astral-sh/setup-uv | v10.3.3 | 2026-10-28 | MIT |
| docker/build-push-action | v7.4.0 | 2026-09-15 | Apache-2.0 |
| docker/login-action | v4.8.0 | 2026-11-05 | Apache-2.0 |

## Teste de carga (F2.6)

**D-CARGA:** o gerador é próprio (`backend/tests/carga/gerador.py`), sobre `httpx` 0.28.1 que já está nas dependências: taxa fixa (open-loop), p50/p95/p99 e taxa de erro, com veredito contra o RNF02 (p95 < 300 ms e erro < 0,5%). k6 (AGPL-3.0) e Locust (MIT) foram dispensados: nenhuma ferramenta nova a licenciar nem a manter. Medido em 2026-11-14 contra o compose local (HTTPS pela borda, 1 contêiner de API): **20 req/s por 60 s: 1200 pedidos, 0 erros, p95 = 32 ms**; **100 req/s por 20 s: 2000 pedidos, 0 erros, p95 = 66 ms**. Para repetir: `python -m tests.carga.gerador --tenant <uuid> --chave deploy/compose/segredos/chave_es256 --publicar-politica --sem-verificar-tls`. Reexecutar no ambiente do piloto (F1.42) antes de aceitar RNF02 em produção.

