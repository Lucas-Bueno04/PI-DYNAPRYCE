"""k_agr: o contrato como unidade de preço (ADR-003).

H_pad(contrato) = Σ H_pad(empresas com vínculo vigente), com as equações aplicadas por empresa;
empresa sem vínculo (ou com dois) vira pendência e nunca entra na soma.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from dynaprice.dominio.modelos import Competencia, Direcionadores, Empresa, Regime, Vinculo
from dynaprice.dominio.precificacao.equacoes_tempo import (
    EquacoesDeTempo,
    HorasPadrao,
    media_dos_direcionadores,
)

# Strategy da decisão D1: muda só esta função se o escritório decidir outra regra.
type RegraDeSegmento = Callable[[Sequence[Empresa], Empresa], Regime]

_REGIMES_SIMPLES = frozenset({Regime.MEI, Regime.SN})


def regime_da_principal(empresas: Sequence[Empresa], principal: Empresa) -> Regime:
    """D1 (a): o segmento do contrato é o regime da empresa principal."""
    return principal.regime


class MotivoPendencia(StrEnum):
    SEM_VINCULO = "sem_vinculo"
    VINCULO_DUPLICADO = "vinculo_duplicado"
    SEM_PRINCIPAL = "sem_principal"


@dataclass(frozen=True, slots=True)
class Pendencia:
    referencia: str  # id da empresa ou do contrato
    motivo: MotivoPendencia


@dataclass(frozen=True, slots=True)
class AgregadoDoContrato:
    contrato_id: str
    regime: Regime
    empresas: tuple[str, ...]
    horas_padrao: HorasPadrao
    meses: int  # menor número de meses com dados entre as empresas (ADR-003)
    regimes: frozenset[Regime]

    @property
    def misto(self) -> bool:
        return len(self.regimes) > 1

    @property
    def alerta_segmento(self) -> bool:
        """D1: principal MEI/SN num contrato que também tem LP/LR."""
        return self.regime in _REGIMES_SIMPLES and bool(self.regimes - _REGIMES_SIMPLES)


@dataclass(frozen=True, slots=True)
class ResultadoDaAgregacao:
    contratos: tuple[AgregadoDoContrato, ...]
    pendencias: tuple[Pendencia, ...]


@dataclass(frozen=True, slots=True)
class _Composicao:
    empresas: tuple[Empresa, ...]
    principal: Empresa | None


class AgregadorDeContratos:
    def __init__(
        self, equacoes: EquacoesDeTempo, regra_de_segmento: RegraDeSegmento = regime_da_principal
    ) -> None:
        self._equacoes = equacoes
        self._regra = regra_de_segmento

    def agregar(
        self,
        competencia: Competencia,
        empresas: Sequence[Empresa],
        vinculos: Sequence[Vinculo],
        direcionadores: Sequence[Direcionadores],
    ) -> ResultadoDaAgregacao:
        composicoes, pendencias = _compor(competencia, empresas, vinculos)
        por_empresa: dict[str, list[Direcionadores]] = defaultdict(list)
        for registro in direcionadores:
            por_empresa[registro.empresa_id].append(registro)
        contratos: list[AgregadoDoContrato] = []
        for contrato_id, composicao in sorted(composicoes.items()):
            if composicao.principal is None:
                pendencias.append(Pendencia(contrato_id, MotivoPendencia.SEM_PRINCIPAL))
                continue
            contratos.append(
                self._agregado(contrato_id, composicao, composicao.principal, por_empresa)
            )
        return ResultadoDaAgregacao(tuple(contratos), tuple(pendencias))

    def _agregado(
        self,
        contrato_id: str,
        composicao: _Composicao,
        principal: Empresa,
        por_empresa: dict[str, list[Direcionadores]],
    ) -> AgregadoDoContrato:
        horas = HorasPadrao({})
        for empresa in composicao.empresas:
            meses = por_empresa.get(empresa.id, [])
            if meses:
                horas += self._equacoes.horas_padrao(empresa, media_dos_direcionadores(meses))
        return AgregadoDoContrato(
            contrato_id=contrato_id,
            regime=self._regra(composicao.empresas, principal),
            empresas=tuple(sorted(e.id for e in composicao.empresas)),
            horas_padrao=horas,
            meses=min(
                len({m.competencia for m in por_empresa.get(e.id, [])}) for e in composicao.empresas
            ),
            regimes=frozenset(e.regime for e in composicao.empresas),
        )


def _compor(
    competencia: Competencia, empresas: Sequence[Empresa], vinculos: Sequence[Vinculo]
) -> tuple[dict[str, _Composicao], list[Pendencia]]:
    vigentes: dict[str, list[Vinculo]] = defaultdict(list)
    for vinculo in vinculos:
        if vinculo.vigente_em(competencia):
            vigentes[vinculo.empresa_id].append(vinculo)
    membros: dict[str, list[Empresa]] = defaultdict(list)
    principais: dict[str, Empresa] = {}
    pendencias: list[Pendencia] = []
    for empresa in sorted(empresas, key=lambda e: e.id):
        dela = vigentes.get(empresa.id, [])
        if len(dela) != 1:
            motivo = MotivoPendencia.SEM_VINCULO if not dela else MotivoPendencia.VINCULO_DUPLICADO
            pendencias.append(Pendencia(empresa.id, motivo))
            continue
        membros[dela[0].contrato_id].append(empresa)
        if dela[0].principal:
            principais[dela[0].contrato_id] = empresa
    composicoes = {c: _Composicao(tuple(m), principais.get(c)) for c, m in membros.items()}
    return composicoes, pendencias


def empresas_sem_vinculo(
    competencia: Competencia,
    vinculos: Sequence[Vinculo],
    direcionadores: Sequence[Direcionadores],
) -> list[str]:
    """Empresas com movimento na competência e sem vínculo vigente (fila de uc_vinc)."""
    vinculadas = {v.empresa_id for v in vinculos if v.vigente_em(competencia)}
    com_movimento = {d.empresa_id for d in direcionadores if d.competencia == competencia}
    return sorted(com_movimento - vinculadas)
