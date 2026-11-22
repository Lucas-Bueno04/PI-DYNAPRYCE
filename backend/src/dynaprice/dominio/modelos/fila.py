"""Regras da fila de jobs: parâmetros e backoff exponencial (decisão F1-FILA)."""

from dataclasses import dataclass

from dynaprice.dominio.modelos.erros import ValorInvalido


@dataclass(frozen=True, slots=True)
class ParametrosDeFila:
    max_tentativas: int = 5
    backoff_base_s: float = 60
    backoff_teto_s: float = 3600
    variacao: float = 0.1
    lease_s: float = 300
    heartbeat_s: float = 60
    varredura_s: float = 60

    def __post_init__(self) -> None:
        if self.heartbeat_s >= self.lease_s:
            raise ValorInvalido("o heartbeat precisa ser mais curto que o lease")
        if self.max_tentativas < 1:
            raise ValorInvalido("max_tentativas precisa ser ao menos 1")


def atraso_de_backoff(tentativa: int, parametros: ParametrosDeFila, sorteio: float) -> float:
    """Espera antes da próxima tentativa; `sorteio` em [0, 1] espalha reexecuções simultâneas."""
    base = min(parametros.backoff_base_s * 2 ** (tentativa - 1), parametros.backoff_teto_s)
    return float(base * (1 + parametros.variacao * (2 * sorteio - 1)))
