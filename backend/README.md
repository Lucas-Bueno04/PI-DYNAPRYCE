# DynaPrice: backend

Monólito modular em Python 3.14, organizado em Clean Architecture ([ADR-001](../docs/adr/0001-arquitetura.md)). Antes de mexer no código, leia os [princípios de engenharia](../docs/engenharia/principios.md) e as [ADRs](../docs/adr/).

## Como rodar

Requer o [uv](https://docs.astral.sh/uv/); ele instala o Python 3.14 se faltar.

```bash
uv sync                    # cria .venv com as dependências travadas em uv.lock
uv run dynaprice --help    # CLI (comandos: versao, lab)
uv run pytest              # testes
uv run ruff check .        # lint
uv run ruff format --check .
uv run mypy                # tipagem strict em src/ e tests/
```

## Os 4 anéis

A dependência aponta sempre para dentro: `principal` → `adaptadores` → `aplicacao` → `dominio`.

| Anel | Pacote | Conteúdo |
|---|---|---|
| 1 | `src/dynaprice/dominio/` | `modelos/`, `precificacao/` (a única implementação da regra de preço), `estimacao/` (único lugar com numpy, pandas, scikit-learn e statsmodels). Sem I/O. |
| 2 | `src/dynaprice/aplicacao/` | Casos de uso e `portas/` (`typing.Protocol`). |
| 3 | `src/dynaprice/adaptadores/` | `entrada/{cli,api,worker}/` e `saida/` (implementações das portas). |
| 4 | `src/dynaprice/principal.py` | Composition Root: liga as dependências e monta as entradas. |
