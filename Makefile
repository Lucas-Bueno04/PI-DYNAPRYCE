# DynaPrice: setup, instalação e execução em modo dev e produção.
# `make` ou `make help` lista os alvos.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Configuração (sobrescreva na linha de comando: make prod-up DYNAPRICE_VERSAO=1.2.0) ----
DYNAPRICE_VERSAO  ?= dev
DYNAPRICE_ORIGEM  ?= https://localhost:8443
DYNAPRICE_PG_PORTA ?= 5432
API_PORTA         ?= 8000
WEB_PORTA         ?= 5173
# Rede do build das imagens: "host" contorna DNS quebrado nos contêineres (ver deploy/compose/README.md).
BUILD_NETWORK     ?= host
# Arquivos compose extras (ex.: override local sem no-new-privileges): make prod-up COMPOSE_EXTRA="-f meu.yaml"
COMPOSE_EXTRA     ?=

BACKEND  := backend
FRONTEND := frontend
COMPOSE_DIR := deploy/compose
SEGREDOS := $(COMPOSE_DIR)/segredos
SEGREDOS_DEV := $(SEGREDOS)/dev
COMPOSE := DYNAPRICE_VERSAO=$(DYNAPRICE_VERSAO) DYNAPRICE_ORIGEM=$(DYNAPRICE_ORIGEM) \
           DYNAPRICE_PG_PORTA=$(DYNAPRICE_PG_PORTA) docker compose -f $(COMPOSE_DIR)/compose.yaml
COMPOSE_DEV := $(COMPOSE) -f $(COMPOSE_DIR)/compose.dev.yaml $(COMPOSE_EXTRA)
COMPOSE_PROD := $(COMPOSE) $(COMPOSE_EXTRA)

# Ambiente da API e do worker rodando no host (modo dev): segredos em arquivo, banco em localhost.
ENV_DEV := DYNAPRICE_DB_URL_FILE=$(abspath $(SEGREDOS_DEV))/db_url_app \
  DYNAPRICE_CHAVES_MESTRAS_FILE=$(abspath $(SEGREDOS))/chaves_mestras \
  DYNAPRICE_CHAVE_ES256_FILE=$(abspath $(SEGREDOS))/chave_es256 \
  DYNAPRICE_CHAVE_PSEUDONIMO_FILE=$(abspath $(SEGREDOS))/chave_pseudonimo \
  DYNAPRICE_ORIGEM=http://localhost:$(WEB_PORTA)

.PHONY: help
help: ## Lista os alvos
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z0-9_.-]+:.*## /{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------- setup e instalação
.PHONY: setup check-tools install install-backend install-frontend secrets
setup: check-tools install secrets ## Primeira vez: confere ferramentas, instala dependências, gera segredos de DEV
	@echo "Pronto. Rode 'make dev' (desenvolvimento) ou veja 'make help'."

check-tools: ## Confere uv, node, npm, docker e openssl
	@for t in uv node npm docker openssl; do \
	  command -v $$t >/dev/null || { echo "falta: $$t"; exit 1; }; done
	@node -e 'process.exit(parseInt(process.versions.node)>=24?0:1)' || { echo "Node >= 24.15 é exigido (package.json)"; exit 1; }
	@docker compose version >/dev/null || { echo "falta o plugin docker compose"; exit 1; }

install: install-backend install-frontend ## Instala dependências do backend (uv, travadas) e do frontend (npm ci)

install-backend:
	cd $(BACKEND) && uv sync --locked

install-frontend:
	cd $(FRONTEND) && npm ci

secrets: ## Gera segredos DESCARTÁVEIS de dev e certificado autoassinado (nunca usar em produção)
	@./$(COMPOSE_DIR)/gerar-segredos-dev.sh
	@mkdir -p $(SEGREDOS_DEV)
	@sed 's/@pg:5432/@127.0.0.1:$(DYNAPRICE_PG_PORTA)/' $(SEGREDOS)/db_url_app > $(SEGREDOS_DEV)/db_url_app
	@sed 's/@pg:5432/@127.0.0.1:$(DYNAPRICE_PG_PORTA)/' $(SEGREDOS)/db_url_migrador > $(SEGREDOS_DEV)/db_url_migrador
	@echo "Segredos de dev em $(SEGREDOS)/ (ignorado pelo git)."

# ---------------------------------------------------------------- modo desenvolvimento
# Banco em contêiner; API, worker e Vite no host, com recarga automática.
.PHONY: dev dev-db dev-api dev-worker dev-web dev-down dev-reset-db
dev: dev-db ## Sobe banco + API + Vite (http://localhost:5173); Ctrl+C encerra API e Vite
	@$(MAKE) -j2 --no-print-directory dev-api dev-web

dev-db: $(SEGREDOS_DEV)/db_url_app ## Sobe o Postgres e aplica as migrações
	$(COMPOSE_DEV) up -d --wait pg
	$(COMPOSE_DEV) run --rm migrar

$(SEGREDOS_DEV)/db_url_app:
	@$(MAKE) --no-print-directory secrets

dev-api: ## API com recarga
	cd $(BACKEND) && $(ENV_DEV) uv run uvicorn --factory dynaprice.principal:criar_api \
	  --reload --host 127.0.0.1 --port $(API_PORTA)

dev-worker: ## Worker de jobs (rode em outro terminal se precisar de jobs)
	cd $(BACKEND) && $(ENV_DEV) uv run dynaprice worker

dev-web: ## Vite com proxy de /api para a API (porta 5173 por padrão)
	cd $(FRONTEND) && npm run dev -- --port $(WEB_PORTA)

dev-down: ## Para o banco de dev (mantém os dados)
	$(COMPOSE_DEV) down

dev-reset-db: ## Apaga o banco de dev (volume) e recria. DESTRUTIVO
	@read -p "Apagar TODOS os dados de dev? [s/N] " r && [ "$$r" = s ]
	$(COMPOSE_DEV) down -v

.PHONY: criar-admin
criar-admin: ## Primeiro admin (dev): make criar-admin INQUILINO="Escritório" EMAIL=a@b.c SENHA=...
	@test -n "$(INQUILINO)" -a -n "$(EMAIL)" -a -n "$(SENHA)" || { echo "informe INQUILINO, EMAIL e SENHA"; exit 1; }
	cd $(BACKEND) && $(ENV_DEV) DYNAPRICE_SENHA_ADMIN='$(SENHA)' \
	  uv run dynaprice criar-admin --inquilino "$(INQUILINO)" --email "$(EMAIL)"

# ---------------------------------------------------------------- qualidade
.PHONY: test lint typecheck check test-backend test-frontend
test: test-backend test-frontend ## Todos os testes
test-backend:
	cd $(BACKEND) && uv run pytest
test-frontend:
	cd $(FRONTEND) && npm test
lint: ## ruff + import-linter + eslint
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check . && uv run lint-imports
	cd $(FRONTEND) && npm run lint
typecheck: ## mypy strict + tsc
	cd $(BACKEND) && uv run mypy
	cd $(FRONTEND) && npm run typecheck
check: lint typecheck test ## Tudo que o CI cobra

# ---------------------------------------------------------------- modo produção (compose)
# Mesma imagem do desenvolvimento, com TLS, CSP e HSTS na borda. Os segredos REAIS ficam em $(SEGREDOS)/
# (procedimento: docs/procedimentos/publicar.md). Em produção a decisão de publicar é humana.
.PHONY: build prod-check prod-up prod-down prod-ps prod-logs prod-migrar prod-admin
build: ## Constrói as imagens dynaprice-backend e dynaprice-web com DYNAPRICE_VERSAO
	docker build --network=$(BUILD_NETWORK) -t dynaprice-backend:$(DYNAPRICE_VERSAO) $(BACKEND)
	docker build --network=$(BUILD_NETWORK) -t dynaprice-web:$(DYNAPRICE_VERSAO) $(FRONTEND)

prod-check: ## Confere segredos, TLS e a configuração do compose
	@for f in pg_superusuario pg_migrador pg_app db_url_migrador db_url_app chaves_mestras chave_es256 chave_pseudonimo tls/tls.crt tls/tls.key; do \
	  test -s $(SEGREDOS)/$$f || { echo "falta segredo: $(SEGREDOS)/$$f"; exit 1; }; done
	@test "$(DYNAPRICE_VERSAO)" != dev || echo "aviso: DYNAPRICE_VERSAO=dev; defina a versão (ex.: DYNAPRICE_VERSAO=1.0.0)"
	@case "$(DYNAPRICE_ORIGEM)" in https://*) ;; *) echo "DYNAPRICE_ORIGEM deve ser https://"; exit 1;; esac
	$(COMPOSE_PROD) config -q

prod-up: prod-check build ## Backup antes de migrar (deploy/backup/README.md); sobe pg, migra, api, worker e borda
	$(COMPOSE_PROD) up -d --wait
	@echo "Saúde: curl -k $(DYNAPRICE_ORIGEM)/api/v1/saude"

prod-down: ## Para a stack (mantém o volume do banco)
	$(COMPOSE_PROD) down

prod-ps: ## Estado dos contêineres
	$(COMPOSE_PROD) ps

prod-logs: ## Logs: make prod-logs S=api
	$(COMPOSE_PROD) logs -f --tail=200 $(S)

prod-migrar: ## Aplica as migrações pendentes
	$(COMPOSE_PROD) run --rm migrar

prod-admin: ## Primeiro admin: make prod-admin INQUILINO="..." EMAIL=... (a senha é pedida e não vai ao histórico)
	@test -n "$(INQUILINO)" -a -n "$(EMAIL)" || { echo "informe INQUILINO e EMAIL"; exit 1; }
	@read -s -p "Senha do admin: " s; echo; \
	  $(COMPOSE_PROD) run --rm -e DYNAPRICE_SENHA_ADMIN="$$s" api cli criar-admin --inquilino "$(INQUILINO)" --email "$(EMAIL)"

# ---------------------------------------------------------------- limpeza
.PHONY: clean
clean: ## Remove caches e builds locais (não toca em dados nem segredos)
	rm -rf $(BACKEND)/{.pytest_cache,.mypy_cache,.ruff_cache,.hypothesis,.import_linter_cache,build} $(FRONTEND)/dist
