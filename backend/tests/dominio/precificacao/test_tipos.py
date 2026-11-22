"""F0.7 (A3): o núcleo de preço não expõe float; valores monetários são Decimal ou Dinheiro."""

import inspect
import pkgutil
import typing
from collections.abc import Iterator
from importlib import import_module

import dynaprice.dominio.precificacao as precificacao


def _publicos() -> Iterator[tuple[str, object]]:
    for info in pkgutil.iter_modules(precificacao.__path__, f"{precificacao.__name__}."):
        modulo = import_module(info.name)
        for nome, objeto in vars(modulo).items():
            if nome.startswith("_") or getattr(objeto, "__module__", None) != info.name:
                continue
            if inspect.isfunction(objeto):
                yield f"{info.name}.{nome}", objeto
            elif inspect.isclass(objeto):
                for metodo, funcao in vars(objeto).items():
                    if inspect.isfunction(funcao) and not metodo.startswith("_"):
                        yield f"{info.name}.{nome}.{metodo}", funcao


def test_nenhuma_assinatura_publica_usa_float() -> None:
    com_float = [
        nome
        for nome, funcao in _publicos()
        if "float" in str(typing.get_type_hints(funcao)).lower()
    ]
    assert com_float == []


def test_ha_funcoes_publicas_verificadas() -> None:
    assert len(list(_publicos())) >= 1
