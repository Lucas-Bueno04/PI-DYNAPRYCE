"""Adaptador de saída: planilha exportada pelo escritório (a_csv, plano B do Domínio)."""

from dynaprice.adaptadores.saida.planilha.leitor import LeitorDePlanilhaDoEscritorio
from dynaprice.adaptadores.saida.planilha.pseudonimo import Pseudonimizador

__all__ = ["LeitorDePlanilhaDoEscritorio", "Pseudonimizador"]
