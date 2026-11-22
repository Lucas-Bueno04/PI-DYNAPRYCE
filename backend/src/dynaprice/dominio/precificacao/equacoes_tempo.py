"""k_teq: horas-padrão por departamento (Eq. 36) e média de doze meses (seção 6.3).

O cálculo acumula minutos e divide por 60 uma única vez no total, para que a Tabela 7
dê 5,935 h exatas (as parcelas 2,48333… e 0,66666… são dízimas).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from dynaprice.dominio.modelos import (
    Departamento,
    Direcionadores,
    Empresa,
    EquacaoDeTempo,
    Horas,
    PoliticaVersao,
    ValorInvalido,
)

_MINUTOS_POR_HORA = Decimal(60)


@dataclass(frozen=True, slots=True)
class HorasPadrao:
    """H_pad decomposto por departamento (auditável: A5)."""

    minutos: Mapping[Departamento, Decimal]

    def __post_init__(self) -> None:
        object.__setattr__(self, "minutos", MappingProxyType(dict(self.minutos)))

    @property
    def departamentos(self) -> frozenset[Departamento]:
        return frozenset(self.minutos)

    def horas(self, departamento: Departamento) -> Decimal:
        return self.minutos.get(departamento, Decimal(0)) / _MINUTOS_POR_HORA

    @property
    def total(self) -> Horas:
        return Horas(sum(self.minutos.values(), Decimal(0)) / _MINUTOS_POR_HORA)

    def __add__(self, outra: HorasPadrao) -> HorasPadrao:
        soma = dict(self.minutos)
        for departamento, minutos in outra.minutos.items():
            soma[departamento] = soma.get(departamento, Decimal(0)) + minutos
        return HorasPadrao(soma)


class EquacoesDeTempo:
    """Aplica as equações de tempo publicadas na versão de política (β congelados)."""

    def __init__(self, politica: PoliticaVersao) -> None:
        self._politica = politica

    def horas_padrao(self, empresa: Empresa, direcionadores: Mapping[str, Decimal]) -> HorasPadrao:
        return HorasPadrao(
            {
                departamento: _minutos(
                    self._politica.equacao(departamento, empresa.regime), direcionadores
                )
                for departamento in sorted(empresa.departamentos)
            }
        )


def _minutos(equacao: EquacaoDeTempo, direcionadores: Mapping[str, Decimal]) -> Decimal:
    variavel = sum(
        (
            b * direcionadores.get(nome, Decimal(0))
            for nome, b in equacao.inclinacoes_minutos.items()
        ),
        Decimal(0),
    )
    return equacao.beta0_horas * _MINUTOS_POR_HORA + variavel


def media_dos_direcionadores(meses: Sequence[Direcionadores]) -> dict[str, Decimal]:
    """x̄: média de cada direcionador nos meses dados (seção 6.3); ausente conta como zero."""
    if not meses:
        raise ValorInvalido("média de direcionadores sem nenhum mês")
    nomes = sorted({nome for mes in meses for nome in mes.valores})
    return {nome: sum((m.valor(nome) for m in meses), Decimal(0)) / len(meses) for nome in nomes}
