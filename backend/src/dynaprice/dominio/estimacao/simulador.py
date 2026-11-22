"""m_sim: simula uma política sobre a carteira antes de publicá-la (Eq. 70; seções 6.5–6.8).

Não existe segunda fórmula: o alvo vem de k_inf/k_pol, o caminho de k_tr e o arredondamento
de k_din. O simulador só agrega métricas: receitas R0, R*, R1, % no piso, no teto, congelados,
% com gatilho e ciclos até o alvo.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from dynaprice.dominio.modelos import Dinheiro, Horas, Kappa, Regime
from dynaprice.dominio.precificacao import MotivoDoPasso, NucleoDePreco, PrecoInferido

_MAXIMO_DE_CICLOS = 60


@dataclass(frozen=True, slots=True)
class ContratoSimulado:
    contrato_id: str
    regime: Regime
    horas_padrao: Horas
    meses: int
    preco_vigente: Dinheiro
    kappa: Kappa
    provisorio: bool = False


@dataclass(frozen=True, slots=True)
class _Trajetoria:
    inferido: PrecoInferido
    primeiro: MotivoDoPasso
    ciclo_1: Dinheiro
    ciclos: int | None  # None quando o contrato está acima do alvo
    gatilho: bool


@dataclass(frozen=True, slots=True)
class ResultadoDaSimulacao:
    contratos: int
    receita_vigente: Decimal  # R0
    receita_alvo: Decimal  # Σ P*
    receita_ciclo_1: Decimal  # R1, Eq. (70)
    fracao_no_piso: Decimal  # entre os contratos com informação completa
    fracao_no_teto: Decimal
    fracao_congelados: Decimal
    fracao_gatilho: Decimal
    ciclos_mediana: float
    ciclos_maximo: int


def _fracao(parte: int, todo: int) -> Decimal:
    return Decimal(parte) / Decimal(todo) if todo else Decimal(0)


def _soma(valores: Sequence[Decimal]) -> Decimal:
    return sum(valores, Decimal(0))


class SimuladorDePolitica:
    def __init__(self, nucleo: NucleoDePreco, inflacao: Decimal = Decimal(0)) -> None:
        self._inferencia = nucleo.inferencia
        self._transicao = nucleo.transicao
        self._gatilho = nucleo.gatilho
        self._inflacao = inflacao

    def simular(self, contratos: Sequence[ContratoSimulado]) -> ResultadoDaSimulacao:
        trajetorias = [self._trajetoria(c) for c in contratos]
        return ResultadoDaSimulacao(
            len(contratos),
            *_receitas(contratos, trajetorias),
            *_fracoes(trajetorias),
            *_ciclos(trajetorias),
        )

    def _trajetoria(self, contrato: ContratoSimulado) -> _Trajetoria:
        inferido = self._inferencia.preco(
            contrato.regime, contrato.horas_padrao, contrato.meses, contrato.kappa
        )
        alvo = inferido.valor
        integral = contrato.provisorio or inferido.provisorio  # seção 6.7 e ADR-004
        primeiro = self._transicao.proximo(contrato.preco_vigente, alvo, self._inflacao, integral)
        return _Trajetoria(
            inferido=inferido,
            primeiro=primeiro.motivo,
            ciclo_1=primeiro.novo,
            ciclos=self._ciclos(contrato.preco_vigente, alvo, integral),
            gatilho=self._gatilho.avaliar(contrato.preco_vigente, alvo).dispara,
        )

    def _ciclos(self, vigente: Dinheiro, alvo: Dinheiro, integral: bool) -> int | None:
        if vigente > alvo:
            return None
        preco, ciclos = vigente, 0
        while preco < alvo and ciclos < _MAXIMO_DE_CICLOS:
            preco = self._transicao.proximo(
                preco, alvo, self._inflacao, integral and ciclos == 0
            ).novo
            ciclos += 1
        return ciclos


def _receitas(
    contratos: Sequence[ContratoSimulado], trajetorias: Sequence[_Trajetoria]
) -> tuple[Decimal, Decimal, Decimal]:
    """R0, Σ P* e R1 (Eq. 70)."""
    return (
        _soma([c.preco_vigente.valor for c in contratos]),
        _soma([t.inferido.valor.valor for t in trajetorias]),
        _soma([t.ciclo_1.valor for t in trajetorias]),
    )


def _fracoes(trajetorias: Sequence[_Trajetoria]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """% no piso (entre os completos), no teto, congelados e com gatilho."""
    completos = [t for t in trajetorias if not t.inferido.provisorio]
    motivos = [t.primeiro for t in trajetorias]
    return (
        _fracao(sum(map(_no_piso, completos)), len(completos)),
        _fracao(motivos.count(MotivoDoPasso.TETO), len(motivos)),
        _fracao(motivos.count(MotivoDoPasso.CONGELADO), len(motivos)),
        _fracao(sum(t.gatilho for t in trajetorias), len(trajetorias)),
    )


def _ciclos(trajetorias: Sequence[_Trajetoria]) -> tuple[float, int]:
    ciclos = [t.ciclos for t in trajetorias if t.ciclos is not None]
    return (float(median(ciclos)) if ciclos else 0.0, max(ciclos, default=0))


def _no_piso(trajetoria: _Trajetoria) -> bool:
    alvo = trajetoria.inferido.alvo
    return alvo is not None and alvo.piso_vinculante
