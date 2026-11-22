"""Métricas dos portões de qualidade (principios.md §6.2), sem dependência externa além do grimp.

A complexidade ciclomática segue McCabe: 1 + número de pontos de decisão da função
(if/elif, laços, except, expressão condicional, cada operando extra de and/or,
cláusulas de compreensão, case de match, assert). Funções aninhadas são medidas à parte.
"""

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import grimp

_DECISOES: tuple[type[ast.AST], ...] = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.IfExp,
    ast.Assert,
    ast.match_case,
)
_ESCOPOS: tuple[type[ast.AST], ...] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)


@dataclass(frozen=True, slots=True)
class Medida:
    arquivo: str
    nome: str
    tipo: str  # "funcao" ou "classe"
    linhas: int
    complexidade: int


def _filhos_no_mesmo_escopo(no: ast.AST) -> Iterator[ast.AST]:
    for filho in ast.iter_child_nodes(no):
        yield filho
        if not isinstance(filho, _ESCOPOS):
            yield from _filhos_no_mesmo_escopo(filho)


def _pontos_de_decisao(no: ast.AST) -> int:
    if isinstance(no, _DECISOES):
        return 1
    if isinstance(no, ast.BoolOp):
        return len(no.values) - 1
    if isinstance(no, ast.comprehension):
        return 1 + len(no.ifs)
    return 0


def complexidade(funcao: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return 1 + sum(_pontos_de_decisao(n) for n in _filhos_no_mesmo_escopo(funcao))


def _linhas(no: ast.stmt) -> int:
    fim = no.end_lineno or no.lineno
    return fim - no.lineno + 1


def _medir(no: ast.AST, arquivo: str, prefixo: str) -> Iterator[Medida]:
    for filho in ast.iter_child_nodes(no):
        if isinstance(filho, ast.FunctionDef | ast.AsyncFunctionDef):
            nome = f"{prefixo}{filho.name}"
            yield Medida(arquivo, nome, "funcao", _linhas(filho), complexidade(filho))
            yield from _medir(filho, arquivo, f"{nome}.")
        elif isinstance(filho, ast.ClassDef):
            nome = f"{prefixo}{filho.name}"
            yield Medida(arquivo, nome, "classe", _linhas(filho), 0)
            yield from _medir(filho, arquivo, f"{nome}.")
        else:
            yield from _medir(filho, arquivo, prefixo)


def medir_codigo(codigo: str, arquivo: str) -> list[Medida]:
    return list(_medir(ast.parse(codigo), arquivo, ""))


def medir_pacote(raiz: Path) -> list[Medida]:
    medidas: list[Medida] = []
    for caminho in sorted(raiz.rglob("*.py")):
        medidas.extend(medir_codigo(caminho.read_text(encoding="utf-8"), str(caminho)))
    return medidas


def linhas_de_codigo(caminho: Path) -> int:
    return len(caminho.read_text(encoding="utf-8").splitlines())


def e_fachada(codigo: str) -> bool:
    """Módulo só com docstring, imports e __all__ (Facade de pacote): não carrega lógica."""
    for no in ast.parse(codigo).body:
        if isinstance(no, ast.Import | ast.ImportFrom):
            continue
        if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant):
            continue
        alvos = no.targets if isinstance(no, ast.Assign) else []
        if [getattr(a, "id", None) for a in alvos] == ["__all__"]:
            continue
        return False
    return True


def _internos(grafo: grimp.ImportGraph, pacote: str) -> set[str]:
    return {m for m in grafo.modules if m == pacote or m.startswith(f"{pacote}.")}


def acoplamento_eferente(grafo: grimp.ImportGraph, pacote: str) -> dict[str, int]:
    """Ce de cada módulo: quantos módulos internos distintos ele importa diretamente."""
    internos = _internos(grafo, pacote)
    return {m: len(grafo.find_modules_directly_imported_by(m) & internos) for m in sorted(internos)}


def ciclos_entre_modulos(grafo: grimp.ImportGraph, pacote: str) -> list[set[str]]:
    """Componentes fortemente conexos com mais de um módulo (por alcançabilidade mútua)."""
    internos = _internos(grafo, pacote)
    vizinhos = {m: grafo.find_modules_directly_imported_by(m) & internos for m in internos}
    alcancaveis = {m: _alcance(m, vizinhos) for m in internos}
    ciclos: list[set[str]] = []
    vistos: set[str] = set()
    for m in sorted(internos):
        if m in vistos:
            continue
        componente = {o for o in alcancaveis[m] if m in alcancaveis[o]} | {m}
        vistos |= componente
        if len(componente) > 1:
            ciclos.append(componente)
    return ciclos


def _alcance(origem: str, vizinhos: dict[str, set[str]]) -> set[str]:
    pilha, vistos = [origem], set[str]()
    while pilha:
        for proximo in vizinhos[pilha.pop()] - vistos:
            vistos.add(proximo)
            pilha.append(proximo)
    return vistos
