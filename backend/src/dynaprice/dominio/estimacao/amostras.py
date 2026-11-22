"""Amostras de estimação por departamento: (direcionadores, horas registradas) por empresa-mês.

Fronteira Decimal → float: dentro de dominio/estimacao os números são float (principios.md §3).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from dynaprice.dominio.modelos import Carteira, Departamento, HorasRegistradas

type Especificacao = Mapping[Departamento, tuple[str, ...]]

# Direcionadores de cada equação de tempo (Tabela 4 do artigo).
ESPECIFICACAO_PADRAO: Especificacao = MappingProxyType(
    {
        Departamento.FISCAL: ("notas_entrada", "notas_saida"),
        Departamento.CONTABIL: ("lancamentos_manuais", "lancamentos_automaticos"),
        Departamento.FOLHA: ("empregados", "admissoes", "rescisoes"),
    }
)


@dataclass(frozen=True, slots=True)
class AmostraDeDepartamento:
    departamento: Departamento
    direcionadores: tuple[str, ...]
    matriz: tuple[tuple[float, ...], ...]  # uma linha por empresa-mês
    horas: tuple[float, ...]


type Linha = tuple[tuple[float, ...], float]


class _Montador:
    """Junta horas registradas e direcionadores da mesma empresa-mês, por departamento."""

    def __init__(self, carteira: Carteira, especificacao: Especificacao) -> None:
        self._especificacao = especificacao
        self._atende = {e.id: e.departamentos for e in carteira.empresas}
        self._valores = {(d.empresa_id, d.competencia): d for d in carteira.direcionadores}
        self._linhas: dict[Departamento, list[Linha]] = {d: [] for d in especificacao}

    def adicionar(self, registro: HorasRegistradas) -> None:
        mes = self._valores.get((registro.empresa_id, registro.competencia))
        if mes is None or not self._valido(registro):
            return
        nomes = self._especificacao[registro.departamento]
        x = tuple(float(mes.valor(nome)) for nome in nomes)
        self._linhas[registro.departamento].append((x, float(registro.horas.valor)))

    def _valido(self, registro: HorasRegistradas) -> bool:
        departamento = registro.departamento
        atendidos = self._atende.get(registro.empresa_id, frozenset())
        return departamento in self._linhas and departamento in atendidos

    def amostras(self) -> list[AmostraDeDepartamento]:
        return [
            AmostraDeDepartamento(
                d,
                self._especificacao[d],
                tuple(x for x, _ in linhas),
                tuple(h for _, h in linhas),
            )
            for d, linhas in self._linhas.items()
        ]


def amostras_da_carteira(
    carteira: Carteira, especificacao: Especificacao = ESPECIFICACAO_PADRAO
) -> list[AmostraDeDepartamento]:
    montador = _Montador(carteira, especificacao)
    for registro in carteira.horas:
        montador.adicionar(registro)
    return montador.amostras()
