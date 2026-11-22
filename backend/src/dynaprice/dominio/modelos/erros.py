"""Exceções de domínio (principios.md §5): nunca exceção genérica para regra violada."""


class ErroDeDominio(Exception):
    """Raiz das violações de regra do domínio."""


class ValorInvalido(ErroDeDominio, ValueError):
    """Um objeto de valor recebeu um valor que viola sua invariante."""


class TransicaoInvalida(ErroDeDominio):
    """Uma entidade recebeu uma transição de estado não permitida."""
