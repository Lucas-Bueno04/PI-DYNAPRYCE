"""Núcleo de preço dos testes de aceite: política de referência da Tabela 7, publicada."""

from dynaprice.dominio.modelos import fabricar_politica
from dynaprice.dominio.precificacao import NucleoDePreco
from tests.dominio.modelos.documentos import documento_tabela_7


def nucleo() -> NucleoDePreco:
    return NucleoDePreco.da_politica(fabricar_politica(documento_tabela_7()).publicar())
