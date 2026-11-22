"""F0.3: a regra de dependência da Clean Architecture (ADR-001) é verificada como teste.

Cada caso de violação roda o import-linter sobre uma cópia do pacote em diretório
temporário, com um módulo intruso injetado, e exige que o contrato correspondente quebre.
"""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
PACOTE = RAIZ_BACKEND / "src" / "dynaprice"
LINT_IMPORTS = shutil.which("lint-imports") or "lint-imports"


def _rodar_lint(diretorio: Path) -> subprocess.CompletedProcess[str]:
    ambiente = {**os.environ, "PYTHONPATH": str(diretorio / "src")}
    return subprocess.run(
        [LINT_IMPORTS, "--no-cache"],
        cwd=diretorio,
        env=ambiente,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def copia_do_backend(tmp_path: Path) -> Path:
    """Cópia isolada de src/ e do pyproject.toml, onde os testes injetam violações."""
    shutil.copytree(PACOTE, tmp_path / "src" / "dynaprice")
    shutil.copy(RAIZ_BACKEND / "pyproject.toml", tmp_path / "pyproject.toml")
    return tmp_path


def _injetar(copia: Path, modulo_relativo: str, codigo: str) -> None:
    destino = copia / "src" / "dynaprice" / modulo_relativo
    destino.write_text(codigo, encoding="utf-8")


def test_repositorio_atual_respeita_todos_os_contratos() -> None:
    resultado = _rodar_lint(RAIZ_BACKEND)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_dominio_importando_adaptadores_quebra_a_camada(copia_do_backend: Path) -> None:
    _injetar(copia_do_backend, "dominio/intruso.py", "import dynaprice.adaptadores\n")
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode != 0
    assert "Anéis da Clean Architecture" in resultado.stdout
    assert "BROKEN" in resultado.stdout


def test_aplicacao_importando_principal_quebra_a_camada(copia_do_backend: Path) -> None:
    _injetar(copia_do_backend, "aplicacao/intruso.py", "import dynaprice.principal\n")
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode != 0
    assert "BROKEN" in resultado.stdout


@pytest.mark.parametrize("biblioteca", ["numpy", "pandas", "sklearn", "statsmodels", "scipy"])
def test_biblioteca_numerica_fora_de_estimacao_e_proibida(
    copia_do_backend: Path, biblioteca: str
) -> None:
    _injetar(copia_do_backend, "dominio/precificacao/intruso.py", f"import {biblioteca}\n")
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode != 0
    assert "Bibliotecas numéricas só em dominio.estimacao" in resultado.stdout


def test_biblioteca_numerica_em_estimacao_e_permitida(copia_do_backend: Path) -> None:
    _injetar(copia_do_backend, "dominio/estimacao/permitido.py", "import numpy\n")
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_framework_no_dominio_e_proibido(copia_do_backend: Path) -> None:
    _injetar(copia_do_backend, "dominio/modelos/intruso.py", "import typer\n")
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode != 0
    assert "não conhecem frameworks" in resultado.stdout


def _importacoes_de_primeiro_nivel(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes.add(no.module.split(".")[0])
    return nomes


@pytest.mark.parametrize("subpacote", ["dominio/precificacao", "dominio/modelos"])
def test_nucleo_puro_importa_so_biblioteca_padrao(subpacote: str) -> None:
    """dominio/precificacao e dominio/modelos: só biblioteca padrão e o próprio pacote."""
    permitidos = set(sys.stdlib_module_names) | {"dynaprice", "__future__"}
    for arquivo in (PACOTE / subpacote).rglob("*.py"):
        externos = _importacoes_de_primeiro_nivel(arquivo) - permitidos
        assert not externos, f"{arquivo.relative_to(PACOTE)} importa {sorted(externos)}"


def test_precificacao_importando_o_ridge_quebra_o_contrato(copia_do_backend: Path) -> None:
    """E2: o Ridge é controle e diagnóstico; a fórmula de preço não pode depender dele."""
    _injetar(
        copia_do_backend,
        "dominio/precificacao/intruso.py",
        "import dynaprice.dominio.estimacao.ridge\n",
    )
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode != 0
    assert "Estimação fora da fórmula de preço" in resultado.stdout


def test_aplicacao_importando_o_ridge_quebra_o_contrato(copia_do_backend: Path) -> None:
    _injetar(copia_do_backend, "aplicacao/intruso.py", "import dynaprice.dominio.estimacao.ridge\n")
    resultado = _rodar_lint(copia_do_backend)
    assert resultado.returncode != 0
    assert "Estimação fora da fórmula de preço" in resultado.stdout
