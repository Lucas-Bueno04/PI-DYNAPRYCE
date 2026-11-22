"""Fronteira de entrada numérica do domínio: só Decimal exato, nunca float (principios.md §3)."""

from decimal import Decimal, InvalidOperation

from dynaprice.dominio.modelos.erros import ValorInvalido

type Numero = Decimal | int | str


def para_decimal(valor: Numero, nome: str = "valor") -> Decimal:
    if isinstance(valor, bool) or not isinstance(valor, Decimal | int | str):
        raise ValorInvalido(f"{nome}: use Decimal, int ou str (recebido {type(valor).__name__})")
    try:
        convertido = Decimal(valor)
    except InvalidOperation as erro:
        raise ValorInvalido(f"{nome}: {valor!r} não é número") from erro
    if not convertido.is_finite():
        raise ValorInvalido(f"{nome}: {valor!r} não é finito")
    return convertido
