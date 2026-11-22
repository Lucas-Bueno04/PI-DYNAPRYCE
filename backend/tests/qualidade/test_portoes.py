"""F0.4b: portões de qualidade aplicados a src/dynaprice (principios.md §6.2).

Limites: complexidade ≤ 8; função ≤ 40 linhas; classe ≤ 200; módulo ≤ 300;
sem ciclos entre módulos; acoplamento eferente ≤ 8. Exceções só nas listas abaixo, com motivo.
"""

import textwrap
from pathlib import Path

import grimp
import pytest

from tests.qualidade.metricas import (
    Medida,
    acoplamento_eferente,
    ciclos_entre_modulos,
    e_fachada,
    linhas_de_codigo,
    medir_codigo,
    medir_pacote,
)

PACOTE = Path(__file__).resolve().parents[2] / "src" / "dynaprice"

COMPLEXIDADE_MAXIMA = 8
LINHAS_FUNCAO = 40
LINHAS_CLASSE = 200
LINHAS_MODULO = 300
ACOPLAMENTO_MAXIMO = 8

# nome qualificado -> motivo. Vazias de propósito: exceção é refatoração adiada e precisa de motivo.
EXCECOES_COMPLEXIDADE: dict[str, str] = {}
EXCECOES_TAMANHO: dict[str, str] = {}
# Composition Root conhece todos os componentes por definição (principios.md §2).
EXCECOES_ACOPLAMENTO: dict[str, str] = {
    "dynaprice.principal": "Composition Root",
    "dynaprice.principal.api": "Composition Root",
    "dynaprice.principal.fontes": "Composition Root",
    "dynaprice.principal.cli": "Composition Root",
    "dynaprice.principal.worker": "Composition Root",
}


def violacoes_de_complexidade(medidas: list[Medida]) -> list[str]:
    return [
        f"{m.arquivo}:{m.nome} complexidade {m.complexidade}"
        for m in medidas
        if m.tipo == "funcao"
        and m.complexidade > COMPLEXIDADE_MAXIMA
        and m.nome not in EXCECOES_COMPLEXIDADE
    ]


def violacoes_de_tamanho(medidas: list[Medida]) -> list[str]:
    limite = {"funcao": LINHAS_FUNCAO, "classe": LINHAS_CLASSE}
    return [
        f"{m.arquivo}:{m.nome} {m.linhas} linhas"
        for m in medidas
        if m.linhas > limite[m.tipo] and m.nome not in EXCECOES_TAMANHO
    ]


@pytest.fixture(scope="module")
def medidas() -> list[Medida]:
    return medir_pacote(PACOTE)


@pytest.fixture(scope="module")
def grafo() -> grimp.ImportGraph:
    return grimp.build_graph("dynaprice", cache_dir=None)


def test_complexidade_ciclomatica_no_limite(medidas: list[Medida]) -> None:
    assert violacoes_de_complexidade(medidas) == []


def test_funcoes_e_classes_no_limite_de_linhas(medidas: list[Medida]) -> None:
    assert violacoes_de_tamanho(medidas) == []


def test_modulos_no_limite_de_linhas() -> None:
    grandes = [
        f"{p}: {n}" for p in PACOTE.rglob("*.py") if (n := linhas_de_codigo(p)) > LINHAS_MODULO
    ]
    assert grandes == []


def test_sem_ciclos_entre_modulos(grafo: grimp.ImportGraph) -> None:
    assert ciclos_entre_modulos(grafo, "dynaprice") == []


def _fachadas() -> set[str]:
    """__init__ que só reexporta (Facade do pacote): o Ce mede o tamanho do pacote, não lógica."""
    raiz = PACOTE.parent
    return {
        ".".join(p.parent.relative_to(raiz).parts)
        for p in PACOTE.rglob("__init__.py")
        if e_fachada(p.read_text(encoding="utf-8"))
    }


def test_acoplamento_eferente_no_limite(grafo: grimp.ImportGraph) -> None:
    ignorar = EXCECOES_ACOPLAMENTO.keys() | _fachadas()
    excesso = {
        m: ce
        for m, ce in acoplamento_eferente(grafo, "dynaprice").items()
        if ce > ACOPLAMENTO_MAXIMO and m not in ignorar
    }
    assert excesso == {}


# --- os portões reprovam violações injetadas ---


def test_portao_reprova_funcao_complexa() -> None:
    ramos = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(COMPLEXIDADE_MAXIMA))
    codigo = f"def f(x):\n{ramos}\n    return -1\n"
    assert violacoes_de_complexidade(medir_codigo(codigo, "x.py")) == [
        f"x.py:f complexidade {COMPLEXIDADE_MAXIMA + 1}"
    ]


def test_portao_reprova_funcao_longa() -> None:
    corpo = "\n".join(f"    a{i} = {i}" for i in range(LINHAS_FUNCAO))
    codigo = textwrap.dedent(f"def f():\n{corpo}\n")
    assert violacoes_de_tamanho(medir_codigo(codigo, "x.py")) == [
        f"x.py:f {LINHAS_FUNCAO + 1} linhas"
    ]
