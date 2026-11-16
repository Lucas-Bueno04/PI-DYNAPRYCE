"""Adaptador a_expf: arquivo para o financeiro. Layout do Omie a confirmar com o escritório."""

import csv
import io
from collections.abc import Sequence

from dynaprice.dominio.modelos.recomendacao import Recomendacao

_INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _texto_seguro(valor: str) -> str:
    """Impede que planilha interprete um campo como fórmula (injeção via CSV)."""
    return f"'{valor}" if valor.startswith(_INICIOS_DE_FORMULA) else valor


class ExportadorCsvDeRecomendacoes:
    def gerar(self, recomendacoes: Sequence[Recomendacao]) -> bytes:
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
        escritor.writerow(["contrato", "competencia_efeito", "valor"])
        for r in recomendacoes:
            valor = str(r.preco_proposto).replace(".", ",")
            escritor.writerow([_texto_seguro(r.contrato_id), str(r.efeito), valor])
        return saida.getvalue().encode("utf-8-sig")
