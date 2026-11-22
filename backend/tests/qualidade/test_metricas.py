"""F0.4b: as métricas dos portões de qualidade (principios.md §6.2) medem o que dizem medir.

Escritos antes de `metricas.py` (TDD): cada métrica é verificada com código injetado.
"""

import textwrap

import grimp

from tests.qualidade.metricas import (
    Medida,
    acoplamento_eferente,
    ciclos_entre_modulos,
    e_fachada,
    medir_codigo,
)


def _medidas(codigo: str) -> dict[str, Medida]:
    return {m.nome: m for m in medir_codigo(textwrap.dedent(codigo), "mod.py")}


def test_funcao_linear_tem_complexidade_um() -> None:
    medidas = _medidas(
        """
        def f(x):
            return x + 1
        """
    )
    assert medidas["f"].complexidade == 1


def test_cada_decisao_soma_um_a_complexidade() -> None:
    medidas = _medidas(
        """
        def f(x, ys):
            if x > 0 and x < 10:      # if +1, and +1
                return 1
            elif x < 0:               # +1
                return 2
            for y in ys:              # +1
                while y:              # +1
                    y -= 1
            try:
                pass
            except ValueError:        # +1
                pass
            return 3 if x else 4      # +1
        """
    )
    assert medidas["f"].complexidade == 8


def test_compreensao_e_match_contam() -> None:
    medidas = _medidas(
        """
        def f(xs, v):
            ys = [x for x in xs if x]   # for +1, if +1
            match v:
                case 1:                 # +1
                    return ys
                case _:                 # +1
                    return []
        """
    )
    assert medidas["f"].complexidade == 5


def test_metodo_recebe_nome_qualificado_e_linhas() -> None:
    medidas = _medidas(
        """
        class C:
            def m(self):
                a = 1
                return a
        """
    )
    assert medidas["C.m"].linhas == 3
    assert medidas["C"].linhas == 4
    assert medidas["C"].tipo == "classe"
    assert medidas["C.m"].tipo == "funcao"


def test_funcao_aninhada_e_medida_separadamente() -> None:
    medidas = _medidas(
        """
        def externa():
            def interna(x):
                if x:
                    return 1
                return 0
            return interna
        """
    )
    assert medidas["externa"].complexidade == 1
    assert medidas["externa.interna"].complexidade == 2


def test_ciclo_entre_modulos_e_detectado() -> None:
    grafo = grimp.ImportGraph()
    for m in ("p", "p.a", "p.b", "p.c"):
        grafo.add_module(m)
    grafo.add_import(importer="p.a", imported="p.b")
    grafo.add_import(importer="p.b", imported="p.a")
    grafo.add_import(importer="p.c", imported="p.a")
    ciclos = ciclos_entre_modulos(grafo, "p")
    assert {frozenset(c) for c in ciclos} == {frozenset({"p.a", "p.b"})}


def test_acoplamento_eferente_conta_modulos_internos_distintos() -> None:
    grafo = grimp.ImportGraph()
    for m in ("p", "p.a", "p.b", "p.c", "fora"):
        grafo.add_module(m)
    grafo.add_import(importer="p.a", imported="p.b")
    grafo.add_import(importer="p.a", imported="p.c")
    grafo.add_import(importer="p.a", imported="fora")
    assert acoplamento_eferente(grafo, "p")["p.a"] == 2


def test_fachada_so_reexporta() -> None:
    assert e_fachada('"""doc"""\nfrom a import b\n__all__ = ["b"]\n')
    assert not e_fachada("from a import b\nX = 1\n")
    assert not e_fachada("def f():\n    pass\n")
