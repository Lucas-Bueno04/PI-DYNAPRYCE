"""Fatos mensais e o retrato da carteira que uma fonte de dados entrega (p_src)."""

from dataclasses import dataclass

from dynaprice.dominio.modelos.competencia import Competencia
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.entidades import Contrato, Direcionadores, Empresa, Vinculo
from dynaprice.dominio.modelos.grandezas import Horas
from dynaprice.dominio.modelos.regime import Departamento


@dataclass(frozen=True, slots=True)
class HorasRegistradas:
    """Horas registradas H (com erro de medida, eq. 2) de uma empresa num departamento e mês."""

    empresa_id: str
    competencia: Competencia
    departamento: Departamento
    horas: Horas


@dataclass(frozen=True, slots=True)
class Honorario:
    """Honorário F cobrado de um contrato numa competência (HONORARIO_MES)."""

    contrato_id: str
    competencia: Competencia
    valor: Dinheiro


@dataclass(frozen=True, slots=True)
class Carteira:
    empresas: tuple[Empresa, ...]
    contratos: tuple[Contrato, ...]
    vinculos: tuple[Vinculo, ...]
    direcionadores: tuple[Direcionadores, ...]
    horas: tuple[HorasRegistradas, ...]
    honorarios: tuple[Honorario, ...]
