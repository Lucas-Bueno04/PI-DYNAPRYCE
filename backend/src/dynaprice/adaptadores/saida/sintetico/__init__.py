"""Adaptador de saída: fonte de carteira sintética (G1)."""

from dynaprice.adaptadores.saida.sintetico.gerador import GeradorDeCarteiraSintetica
from dynaprice.adaptadores.saida.sintetico.parametros import (
    EQUACOES_VERDADEIRAS,
    ParametrosSinteticos,
)

__all__ = ["EQUACOES_VERDADEIRAS", "GeradorDeCarteiraSintetica", "ParametrosSinteticos"]
