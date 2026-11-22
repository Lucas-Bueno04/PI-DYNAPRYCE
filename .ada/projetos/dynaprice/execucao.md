# Execução: DynaPrice

Origem: `plano.md` com as 11 seções aprovadas em 2026-11-09; desenho `mw9kw9fkffjn2` (Arquitetura e componentes, ADR-001 a ADR-004) e `mw9kw9i514upw` (Processos, dados e implantação). As fases saem dos marcos da seção 11. F0 e F1 estão detalhadas; F2 a F4 ficam grossas e serão replanejadas no portão anterior.

Convenções:
- Repositório novo em `/home/lucas/Documents/DynaPrice`, sem remoto. Não há perfil de ambiente até F0.4; o aceite usa os testes que o próprio passo cria (`cd backend && uv run pytest <caminho>`), critério verificável e simulação.
- Pacotes do backend: `backend/src/dynaprice/{dominio,aplicacao,adaptadores,frameworks}` (4 anéis). Núcleo de preço em `dominio/precificacao/` (só biblioteca padrão), estimação em `dominio/estimacao/` (única exceção que importa numpy, pandas, scikit-learn, statsmodels).
- Os critérios completos de cada passo estão no `estado.json` (aba Execução); a coluna Aceite abaixo resume.
- Nenhum passo executa nada fora da máquina sem aprovação explícita do humano. Passos que tocam o escritório (F0.21, F1.42) dizem risco e reversão.
- Toda versão de ferramenta só é fixada depois do passo de conferência (F0.1, F1.1, F4.1).

## Cobertura das simulações

| Simulação | Passo(s) que a testam |
|---|---|
| `mw9kw9i514upw:7` Preço-alvo e transição (Tabela 7) | F0.14 (passos 1 a 6, no núcleo) e F1.31 (7/7, ponta a ponta com aprovação, auditoria e arquivo) |
| Simulações de erro do núcleo (a desenhar em F0.15) | F0.15 |
| Simulações de erro de F1 (a desenhar em F1.4) | ver tabela "Simulações de F1" |
| Simulações de cotação e provisório (a desenhar em F2.1) | F2.2 e F2.4 |

As simulações novas ainda não existem no desenho; quando forem criadas, o passo que as desenha liga cada ref ao passo que a testa com `ada estado aceite add <passo> --simulacao <ref>`.

## Decisões (respondidas pelo humano em 2026-11-09; registro em decisoes.md)

| Item | Escolha | Efeito na execução |
|---|---|---|
| D1 | (a) regime da empresa principal | F0.10 implementa essa regra; F0.22 traz o relatório de contratos mistos para validação |
| D2 | (a) piso estatístico do artigo | o método está decidido; os valores saem de F0.22 e são aprovados no portão F0.23 antes de F1.21 |
| D3 | (a) τ̂ revelado, τ* como referência | idem: o valor sai de F0.22 |
| D4 | (a) θ = 15%, δ = 15% | parâmetros iniciais da política; a sensibilidade de F0.18/F0.22 é mostrada no portão |
| D5 | (b) com texto: os administradores do sistema de cada empresa/escritório aprovam | F1.18/F1.19: o papel aprovar é concedido aos administradores do inquilino, com TOTP obrigatório |
| D6 | (a) proposta de retenção do plano | F1.40 implementa os prazos |
| D7 | (a) mês de aniversário, 2 meses antes | F1.26 |
| D8 | (a) escritório controlador, DynaPrice operador | libera a carga de dados reais no banco a partir de F1.22, mantida a minimização |
| D9 | (a) toda a stack na rede do escritório | F1.7 e F1.42: o lugar "piloto" é a rede do escritório; F1.23 alcança o Domínio direto |
| D10 | (a) 5 dias | parâmetro inicial; F0.22 mede e mostra no portão se 5 dias bastam |
| D11 | (a) só centavos | o teste da Tabela 7 usa 437 → 502,55 → 577,93 → 614,27 |
| D12 | (b) ±20%, justificativa acima de ±5% | F1.27 e primeira política |
| D13 | (b) meses do regime novo, anterior como parcial | F1.26 / k_inf |
| CI | (a) GitHub Actions + GHCR | F1.7 e F1.38; o remoto no GitHub ainda precisa ser criado pelo humano |
| FE-TESTE | (a) Vitest + Testing Library + Playwright | F1.32 a F1.36; versões conferidas em F1.1 |

## F0 — Laboratório

Valor próprio: núcleo de preço provado contra o artigo, estimação reprodutível e relatório que dá os números de D1, D2, D3, D4, D10, D11 e D13. Tudo roda na máquina local, sem banco. F0.20 e F0.21 dependem do escritório e podem começar em paralelo com o núcleo.

| Passo | O quê | Para quê | Como | Nós | Aceite |
|---|---|---|---|---|---|
| F0.1 | Conferir versões e licenças do backend e do laboratório | Não fixar versão sem evidência | Fonte oficial de cada projeto: estável atual, data, manutenção, licença; Python 3.12 da ADR-001 comparado com a estável; diferença vira pergunta | fw_sci, fw_typer | `docs/versoes.md` completo, "a confirmar" onde não houver prova |
| F0.2 | Esqueleto do monorepo e do backend | Base para todos os passos | `git init` local (sem remoto, sem commit sem pedido); `backend/` com uv, ruff, mypy strict, pytest + hypothesis, Typer (`dynaprice`); `docs/adr/` exportado das abas ADR; `deploy/compose/` vazio | cli, in_cli, fw_typer | `uv sync --locked`, ruff, mypy; `pytest tests/test_cli.py`; ADRs iguais às abas |
| F0.3 | import-linter nos 4 anéis | Regra de arquitetura vira teste | Contratos de camadas + proibição de fw_sci fora de `dominio/estimacao`; teste que injeta violação | e_mod, k_pol, m_teq, fw_sci, legenda | `lint-imports`; `pytest tests/arquitetura` |
| F0.4 | Perfil mínimo do ambiente local | `ada testar` passa a funcionar | Ler `docs/perfil.md` da Ada; lugar `local`, alvos backend | cli | `ada testar backend` |
| F0.5 | Modelos do domínio mínimos | Tipos do núcleo | Dataclasses imutáveis; Decimal para dinheiro; Regime MEI/SN/LP/LR | e_mod | `pytest tests/dominio/modelos`; PoliticaVersao imutável e validada |
| F0.6 | Gerador de carteira sintética (G1) | Insumo de teste e do CI sem dado real | Calibrar faixas na seção 9 do artigo (`docs/lab/calibracao_sintetica.md`); semente fixa; inclui contratos mistos e ~10% sem vínculo; implementado como fonte (p_src) para reaproveitar em F1 | f_src, p_src, in_cli | `pytest tests/sintetico`; `dynaprice lab sintetico --semente 42`; reprodutível byte a byte |
| F0.7 | k_din | Ponto único de arredondamento | Decimal, ROUND_HALF_UP, 2 casas; arredondamento comercial opcional por parâmetro (D11) | k_din | `pytest .../test_dinheiro.py`; mypy garante Decimal |
| F0.8 | k_teq | Horas-padrão por departamento | β0 em horas + inclinações em minutos/unidade ÷ 60 | k_teq, f_hpad, s_teq | 2,785 + 2,483 + 0,667 = 5,935 |
| F0.9 | k_pol + Prop. 3 | Preço-alvo único | P* = κ·max(π_r, τ·H_pad); hypothesis para A1, A2, monotonia, continuidade, convexidade; κ fora de κ̄ rejeitado | k_pol, s_pol | 614,27 sem piso vinculante; propriedades verdes |
| F0.10 | k_agr | Contrato como unidade (ADR-003) | Σ H_pad das empresas com vínculo vigente; segmento numa função única (D1); pendências de vínculo | k_agr, f_agr, f_vinc | empresa sem vínculo fora da soma e listada |
| F0.11 | k_inf | Cascata da ADR-004 | Nível ℓ; sem histórico → π_r; parcial → Z = m/(m + s²/v²); ℓ = 2 → k_pol | k_inf, f_inf | propriedades de Z; regime ausente rejeitado |
| F0.12 | k_tr + k_gat + Prop. 8 | Transição limitada e gatilho | Algoritmo 3; congelamento acima do alvo; zona morta; revisão integral como opção | k_tr, k_gat, f_tr, f_gat, s_tr | Prop. 8 (a) a (e) com hypothesis |
| F0.13 | k_tar + Prop. 7 | Tarifa revelada e de receita constante | Algoritmo 1 (τ̂); solução exata (Prop. 5) para τ* | k_tar, f_tar | Prop. 7 e Prop. 5 contra busca numérica |
| F0.14 | Teste da Tabela 7 no núcleo | Aceite do núcleo | Teste com a ref `mw9kw9i514upw:7` no nome; passos 1 a 6; registrar com `ada resultado --simulacao mw9kw9i514upw:7 --resumo "6/7 passos; passo 7 em F1.31"` | k_teq, k_pol, k_tr, k_gat, k_din, s_teq, s_pol, s_tr, s_rec | **simulação `mw9kw9i514upw:7`**; trajetória exata 437 → 502,55 → 577,93 → 614,27 |
| F0.15 | Simulações de erro do núcleo | Caminhos de erro do fluxo 4.1 (lacuna 9.5) | Desenhar em `mw9kw9i514upw` (piso vinculante + alvo abaixo do vigente, zona morta, κ fora de κ̄), aprovar com o humano, testar | k_pol, k_tr, k_gat, k_inf | `pytest tests/aceite`; refs ligadas por `aceite add` |
| F0.16 | m_teq (Huber) | β das equações de tempo | Huber por departamento; `OMP_NUM_THREADS=1`, sementes fixas (G3) | m_teq, f_teq, fw_sci | β dentro do intervalo dos geradores; reprodutível |
| F0.17 | m_esf (Ridge) | Controle, fora da fórmula (E2) | Ridge log-log; contrato do import-linter impede uso no preço | m_esf, f_mod, fw_sci | `pytest .../test_ridge.py`; `lint-imports` |
| F0.18 | m_sim | Simular políticas e sensibilidade de θ/δ | Usa só k_pol/k_inf/k_tr/k_din; métricas de receita, % no piso e no teto, ciclos; estima s²/v² | m_sim, uc_simular, k_pol, k_tr, k_inf | sem segunda fórmula; 10³ contratos < 5 s |
| F0.19 | Diagnóstico e relatório pela cli | Entregável do laboratório | `dynaprice lab relatorio`; Markdown/HTML com fonte de cada número | m_diag, uc_simular, in_cli, fw_typer, f_anal | relatório sintético com todas as seções |
| F0.20 | Layout e leitor da planilha real | Trazer dado real com minimização | Layout pedido ao escritório; pseudonimizar documento na entrada; só contagens de folha; dados fora do repositório | a_csv, planilha, src_cad, f_limpo | teste de campos proibidos; `.gitignore` |
| F0.21 | Acesso somente leitura ao Domínio | Reduzir o risco 3 e informar D9 | Com a TI do escritório e aprovação do humano: usuário somente leitura, SGBD/versão, driver ODBC Linux e licença, TLS, uma consulta de contagem. **Risco:** carga no banco de produção do escritório; só consultas de contagem fora do expediente. **Reversão:** revogar o usuário | a_dom, fw_odbc, src_esc, dp_src | `docs/lab/acesso_dominio.md` (ou "inacessível" + plano B) |
| F0.22 | Relatório com dados reais | Números de D1, D2, D3, D4, D10, D13 | Rodar F0.19 sobre os dados de F0.20; comparar com a seção 9 do artigo | m_teq, m_esf, m_sim, m_diag, k_tar | relatório real completo; tempo de recalibração estimado |
| F0.23 | **Portão F0** | O humano qualifica | Gestor reconhece o diagnóstico e aprova o relatório; aprovar os valores de π_r, τ, θ/δ e dias de fechamento pelos métodos já decididos (D2, D3, D4, D10) e validar os contratos mistos (D1); replanejar F1 se preciso | — | (humano) |

## F1 — Núcleo, recalibração, recomendações, autenticação e interface mínima

Valor próprio: o ciclo mensal roda de ponta a ponta para o piloto, com decisão humana na tela e arquivo para o financeiro. Começa fechando as lacunas de desenho da seção 9 (F1.2 a F1.6) antes de qualquer código de banco ou fila.

| Passo | O quê | Para quê | Como | Nós | Aceite |
|---|---|---|---|---|---|
| F1.1 | Conferir versões e licenças de F1 | Fixar versões com evidência | Banco, API, segurança, conectores (driver do Domínio e licença), frontend, cadeia de suprimentos; evidência para CI e FE-TESTE | fw_fastapi, fw_db, fw_crypto, fw_odbc, fw_httpx, spa | `docs/versoes.md` atualizado |
| F1.2 | Estados e garantias do JOB | Lacuna "fila sem garantias" | Diagrama de estados; atributos no ER; lease + heartbeat, tentativas e backoff exponencial como parâmetros; chaves de idempotência (exportar por lote, reextração) | p_job, fw_runtime, in_worker, motores | desenho atualizado |
| F1.3 | Estados de Recomendação, Política, Contrato, Vínculo, Divergência | Lacuna "máquinas de estado" | Falha de exportação com nova tentativa; APROVADA não exportada; concorrência otimista; revogação de política como opção | d_rec, d_exp, d_pol, uc_vinc, uc_conc, e_mod | desenho atualizado |
| F1.4 | Simulações de erro de F1 | Viram testes de aceite | Desenhar em `mw9kw9i514upw` as 9 simulações da tabela abaixo; ligar cada ref ao passo | a_dom, a_omie, uc_vinc, uc_auth, m_recal, d_exp, uc_conc, uc_estimar, a_db, p_job | simulações criadas e ligadas |
| F1.5 | Regras e ER pendentes | Fechar o resto da seção 9 | ER de JOB/EXTRACAO_RAW/TENANT/USUARIO_PAPEL; RECOMENDACAO com contrato e versão; INDICE_INFLACAO global ou por tenant; frequência de revisão do provisório; portão de aceite das equações; hash por tenant; recarga da política; credencial do `dynaprice_app`; rotação da chave mestra; upload XLSX | e_mod, a_db, pg, p_cif, a_cif, in_http, api | decidido no desenho ou em aguardando |
| F1.6 | Revisão do desenho de F1 | Humano aprova antes do código | `ada plano`; mudanças viram atualização do plano | — | humano aprovou |
| F1.7 | Perfil do ambiente | Saber onde roda, como testa, como publica | compose local (pg, api, worker), lugares local/ci/piloto | dp_proxy, dp_web, dp_worker, dp_pg, dp_bkp | `docker compose config -q`; perfil completo |
| F1.8 | Imagem OCI única | Uma imagem, três entradas | `cmd=api\|worker\|cli`, sem root, sem segredo embutido | api, motores, cli, fw_fastapi, fw_runtime, fw_typer | `docker build` + `cli --help` |
| F1.9 | Banco, papéis e RLS | Isolamento (RNF03) | Migrações pela cli; `dynaprice_migrador` e `dynaprice_app` sem BYPASSRLS/DDL | pg, a_db, fw_db, in_cli, dp_pg | `pytest tests/integracao/db` |
| F1.10 | Repositórios e unidade de trabalho | Tenant por transação | `set_config('app.tenant_id', …, true)`; relógio injetável | p_rel, a_db, p_clock, a_clock | `pytest .../test_repositorios.py` |
| F1.11 | Teste de isolamento | Critério do marco F1 | Tabelas lidas do catálogo; tenant A contra B | a_db, pg, in_auth | `pytest .../test_isolamento.py` + simulação "isolamento" |
| F1.12 | Auditoria encadeada | RNF06 | Cadeia (seq, hash) serializada por tenant | a_db, p_rel, pg | adulteração detectada; sem bifurcação |
| F1.13 | Fila e worker | Jobs confiáveis | ON CONFLICT DO NOTHING, SKIP LOCKED + LISTEN, lease, backoff, órfãos | p_job, a_db, fw_runtime, in_worker, motores | `pytest .../test_fila.py` + simulação "worker que morre" |
| F1.14 | Cifrador de segredos | Credenciais e TOTP cifrados | AES-256-GCM, chave mestra do ambiente | p_cif, a_cif, fw_crypto | `pytest .../test_cifrador.py` |
| F1.15 | API base | Contrato HTTP | `/api/v1`, Problem Details, OpenAPI exportado, logs sem campos proibidos (S7) | in_http, fw_fastapi, api | `pytest tests/api/test_base.py` |
| F1.16 | Credenciais e tokens | ADR-002 | Argon2id, TOTP, ES256 com kid e JWKS | a_hash, a_jwt, p_tok, p_cred, fw_crypto | tokens inválidos recusados; rotação de kid |
| F1.17 | Sessões | ADR-002 | Login + TOTP, refresh com rotação, reuso, sair, bloqueio | uc_auth, p_sess, a_db | simulação "reuso de refresh": 2º uso revoga a família, renovar → 401 |
| F1.18 | Middleware e autorização | S5 | Principal; matriz papel × caso de uso no anel 2 | in_auth, in_http, uc_auth | toda rota declara papel; aprovar sem TOTP recusado |
| F1.19 | Usuários, inquilino, recuperação, primeiro admin | `uc_users`, `uc_recup` | MFA obrigatório; troca de inquilino; recuperação revoga sessões; `cli criar-admin` | uc_users, uc_recup, uc_auth, in_cli | testes de usuários e recuperação |
| F1.20 | Revisão de segurança da autenticação | Consequência da ADR-002 | Revisão dedicada (pessoa ou agente revisor), registrada | uc_auth, uc_recup, a_jwt, a_hash, in_auth | sem achado alto aberto |
| F1.21 | Política como dado | β congelados na versão | Importar rascunho do relatório F0 (D2, D3, D4, D11, D12); publicar com aprovar + TOTP; NOTIFY + recarga ao reconectar | d_pol, e_mod, a_db, api, f_pol | publicada imutável; versão conferida |
| F1.22 | Conectores e importação por planilha | Plano B e carga histórica | uc_conn; upload com limite e sem fórmulas/macros; raw versionado; quarentena | uc_conn, uc_import, a_csv, f_bruto, f_limpo, f_anal, p_src | reimportação idempotente |
| F1.23 | Conector Domínio | Extração automática | pyodbc; projeção mínima (só contagens de folha); timeout | a_dom, fw_odbc, p_src, src_esc | simulação "conector indisponível" |
| F1.24 | Conector Omie | Cobrado para conciliação | httpx; paginação; backoff; respostas gravadas | a_omie, fw_httpx, p_src, src_fin | teste de contrato |
| F1.25 | Vínculos e carga histórica | ADR-003 | Histórico desde/até; principal; pendências | uc_vinc, f_vinc, in_cli, uc_import | simulação "competência sem vínculo" |
| F1.26 | Recalibração mensal | Malha fechada | Competência fechada (D10); política vN fixa; janela (D7); regime (D13); expira PENDENTE | m_recal, in_worker, k_agr, k_inf, k_tr, k_gat, f_hpad | idempotente; simulação "fora da janela de reajuste" |
| F1.27 | Decidir recomendação | Decisão humana | Aprovar, ajustar κ (κ̄ de D12, justificativa), rejeitar; versão otimista; auditoria | d_rec, uc_auth, a_db | concorrência e limites testados |
| F1.28 | Exportação por arquivo | Chegar ao financeiro | Lote idempotente; estado de falha + nova tentativa; layout Omie a confirmar | d_exp, a_expf, p_exp, f_exp | simulação "falha na exportação" |
| F1.29 | Conciliação | Fechar a malha | Aprovado × cobrado; divergência aberta/justificada/resolvida | uc_conc, f_conc, f_hum | simulação "divergência na conciliação" |
| F1.30 | Estimação anual e diagnóstico | Rascunho de política e telas | Job `estimar_politica`; portão de aceite (F1.5) | uc_estimar, m_teq, m_esf, m_sim, k_tar, m_diag | simulação "portão de aceite reprovado" |
| F1.31 | Tabela 7 ponta a ponta + `cli recalcular` | Critério do marco F1 | Carteira sintética no banco; recalibrar; aprovar; exportar; recalcular | m_recal, d_rec, d_exp, k_pol, k_tr, s_rec, s_ges | **simulação `mw9kw9i514upw:7`** 7/7; reprodução ao centavo |
| F1.32 | Esqueleto do frontend | SPA mínima | Vite + React + TS; providers; cliente gerado do OpenAPI (G4); ferramentas de FE-TESTE | spa, fe_app, fe_api, fe_query, fe_ui, fe_forms, fe_be | `npm ci && typecheck && lint && test` |
| F1.33 | Login, MFA e guarda | Entrar com segurança | Token em memória; renovação silenciosa; fila no 401 | fe_login, fe_guard, fe_api | `npm test -- auth` |
| F1.34 | Recomendações e políticas | Decisão na tela | Decomposição; TOTP ao aprovar; diff de versões | fe_rec, fe_pol, fe_query | `npm test -- recomendacoes politicas` |
| F1.35 | Diagnóstico e laboratório | Ver e simular | Gráficos; rascunho → simulação | fe_diag, fe_lab, uc_simular | mesmos números do relatório da cli |
| F1.36 | Administração e vínculos | Operar o tenant | Usuários, papéis, MFA, conectores, pendências | fe_adm, uc_users, uc_conn, uc_vinc | `npm test -- admin` |
| F1.37 | Borda | Mesma origem (ADR-001) | Proxy no compose; TLS, CSP, HSTS, limite de taxa | borda, dp_proxy | cabeçalhos presentes |
| F1.38 | CI | Guardar tudo no CI | Plataforma de CI; alvos do perfil; syft, trivy, pip-audit, npm audit, Renovate | spa, api, motores, cli | isolamento quebrado deixa o CI vermelho |
| F1.39 | Backup e restauração | Critério do marco F1 | pg_dump + WAL em destino externo (local no desenvolvimento) | bkp, dp_bkp, pg | restauração reproduz a última recomendação |
| F1.40 | Retenção | D6 | Jobs de limpeza conforme a decisão | a_db, motores, pg | `pytest .../test_retencao.py` |
| F1.41 | Observabilidade mínima | Lacuna de engenharia | Logs estruturados, métricas, alerta de job falho | api, motores | alerta visível |
| F1.42 | Perfil do piloto e primeira implantação | Piloto em uso | Conforme D9, pelo procedimento do perfil, com aprovação do humano. **Risco:** ambiente do escritório. **Reversão:** procedimento de reversão do perfil (parar contêineres, restaurar backup) | dp_proxy, dp_web, dp_worker, dp_pg, dp_bkp, dp_src | saúde 200 no piloto |
| F1.43 | **Portão F1** | O humano qualifica | Critérios do marco F1; replanejar F2 | — | (humano) |

### Simulações de F1 (a desenhar em F1.4)

| Simulação (lacuna) | Ref | Passo que a testa |
|---|---|---|
| Conector indisponível (9.1) | `mw9kw9i514upw:11` | F1.23 |
| Competência sem vínculo (9.2) | `mw9kw9i514upw:12` | F1.25 |
| Reuso de refresh (9.3) | `mw9kw9i514upw:13` | F1.17 |
| Contrato fora da janela de reajuste (9.6) | `mw9kw9i514upw:14` | F1.26 |
| Falha na exportação (9.7) | `mw9kw9i514upw:15` | F1.28 |
| Divergência na conciliação (9.7) | `mw9kw9i514upw:16` | F1.29 |
| Portão de aceite reprovado (9.9) | `mw9kw9i514upw:17` | F1.30 |
| Isolamento entre tenants (9.10) | `mw9kw9i514upw:18` | F1.11 |
| Worker que morre no meio do job (fila) | `mw9kw9i514upw:19` | F1.13 |

## F2 — Cotação e validação

Grossa; replanejar no portão F1.

| Passo | O quê | Para quê | Como | Nós | Aceite |
|---|---|---|---|---|---|
| F2.1 | Simulações de cotação e do provisório | Lacunas 9.4 e 9.8 | Sem histórico, parcial, regime ausente, política não publicada, política desatualizada, provisório revisado; cotação → contrato provisório | d_cot, k_inf, e_mod | simulações criadas e ligadas |
| F2.2 | d_cot e rota | Cotação | `POST /api/v1/cotacoes` | d_cot, k_inf, k_pol, in_http, a_db | reprodutibilidade |
| F2.3 | fe_cot | Tela de cotação | Formulário com regime obrigatório | fe_cot, fe_forms | `npm test -- cotacao` |
| F2.4 | Revisão integral do provisório | ADR-004 item 4 | ℓ = 2 sem θ; relatório de provisórios abaixo do esforço | m_recal, k_inf, k_tr, m_diag | simulação "provisório revisado" |
| F2.5 | Protocolo de ocultação | Medir EPAM | Seção 10.5 do artigo; vizinhos só offline | m_sim, k_inf, m_viz | EPAM registrado |
| F2.6 | Carga da cotação | RNF02 | Ferramenta conferida antes | api, d_cot | p95 < 300 ms, erro < 0,5% |
| F2.7 | **Portão F2** | | | — | (humano) |

## F3 — Produto multi-inquilino

Grossa; replanejar no portão F2.

| Passo | O quê | Nós | Aceite |
|---|---|---|---|
| F3.1 | Replanejar F3 (desenho e versões) | idp, uc_auth, p_exp, p_src | desenho e plano de F3 aprovados |
| F3.2 | OIDC e consultor com troca de inquilino | idp, uc_auth, in_auth | isolamento verde com token da troca |
| F3.3 | Exportação por API para o Omie | p_exp, a_omie, d_exp | idempotente em homologação, com autorização |
| F3.4 | Segmentação aprendida e m_viz | m_viz, k_inf | só com EPAM melhor e aprovação |
| F3.5 | Âncora externa e BCB/IPCA | a_db, e_mod | alteração de evento detectada |
| F3.6 | Segundo inquilino e agente de extração (se D9) | p_src, a_dom, dp_src | sem mudança em `dominio/` |
| F3.7 | **Portão F3** | — | (humano) |

## F4 — Implantação

Grossa; replanejar no portão F3. Mexe em ambiente compartilhado: todo passo usa o procedimento do perfil, com reversão e aprovação do humano.

| Passo | O quê | Nós | Aceite |
|---|---|---|---|
| F4.1 | Conferir versões e desenhar o perfil Proxmox | dp_proxy, dp_web, dp_worker, dp_pg, dp_bkp | perfil desenhado; RPO/RTO aprovados (proposta 15 min / 4 h) |
| F4.2 | Implantar com a mesma imagem | dp_proxy, dp_web, dp_worker, dp_pg | diff vazio em `dominio/` e `aplicacao/` |
| F4.3 | Ensaio de restauração | dp_bkp, bkp, pg | dentro do RTO e do RPO |
| F4.4 | Medir disponibilidade por um mês | dp_web, dp_pg | meta declarada e medida |
| F4.5 | **Portão F4** | — | (humano) |
