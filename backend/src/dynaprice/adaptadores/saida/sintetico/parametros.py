"""Parâmetros do gerador sintético (G1), calibrados na seção 9 do artigo.

Fonte de cada alvo: docs/lab/calibracao_sintetica.md. Os números aleatórios são float dentro
do gerador (processo gerador de dados) e viram Decimal na fronteira, ao montar a Carteira.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType

from dynaprice.dominio.modelos import Departamento, EquacaoDeTempo, Regime

# Tabela 4 do artigo: equações de tempo verdadeiras (β0 em horas, inclinações em min/unidade).
EQUACOES_VERDADEIRAS: tuple[EquacaoDeTempo, ...] = (
    EquacaoDeTempo(
        Departamento.FISCAL,
        Decimal("0.91"),
        {"notas_entrada": Decimal("3.75"), "notas_saida": Decimal("0.08")},
    ),
    EquacaoDeTempo(
        Departamento.CONTABIL,
        Decimal("0.79"),
        {"lancamentos_manuais": Decimal("2.54"), "lancamentos_automaticos": Decimal("0")},
    ),
    EquacaoDeTempo(
        Departamento.FOLHA,
        Decimal("0.05"),
        {"empregados": Decimal("18.5"), "admissoes": Decimal("116"), "rescisoes": Decimal("84")},
    ),
)

# Médias mensais dos direcionadores para escala 1 (empresa típica do SN).
DIRECIONADORES_BASE: Mapping[str, float] = MappingProxyType(
    {
        "notas_entrada": 1.0,
        "notas_saida": 15.0,
        "lancamentos_manuais": 30.0,
        "lancamentos_automaticos": 30.0,
        "empregados": 4.0,
        "admissoes": 0.2,
        "rescisoes": 0.16,
    }
)

# Sazonalidade (seção 6.3): fechamentos concentrados no 1º semestre; média 1.
SAZONALIDADE: tuple[float, ...] = (
    1.15,
    1.15,
    1.2,
    1.15,
    1.1,
    1.05,
    0.95,
    0.9,
    0.85,
    0.85,
    0.8,
    0.85,
)


def _proporcoes_padrao() -> Mapping[Regime, float]:
    return MappingProxyType({Regime.MEI: 0.10, Regime.SN: 0.55, Regime.LP: 0.25, Regime.LR: 0.10})


def _escalas_padrao() -> Mapping[Regime, float]:
    # Seção 9.4: LR consome 2,4x as horas do LP; LP 2,1x as do SN.
    return MappingProxyType({Regime.MEI: 0.3, Regime.SN: 1.0, Regime.LP: 2.1, Regime.LR: 5.0})


@dataclass(frozen=True, slots=True)
class ParametrosSinteticos:
    semente: int
    contratos: int = 500
    proporcao_regimes: Mapping[Regime, float] = field(default_factory=_proporcoes_padrao)
    escala_por_regime: Mapping[Regime, float] = field(default_factory=_escalas_padrao)
    empresas_por_contrato: tuple[tuple[int, float], ...] = (
        (1, 0.70),
        (2, 0.15),
        (3, 0.10),
        (4, 0.05),
    )
    # Empresas extras (filiais, folha separada): fração do tamanho do contrato e um departamento.
    tamanho_extra: tuple[float, float] = (0.05, 0.3)
    departamento_extra: tuple[tuple[Departamento, float], ...] = (
        (Departamento.FOLHA, 0.4),
        (Departamento.FISCAL, 0.4),
        (Departamento.CONTABIL, 0.2),
    )
    fracao_mistos: float = 0.05
    fracao_sem_vinculo: float = 0.10
    fracao_historico_parcial: float = 0.05
    sigma_tamanho: float = 1.2
    sigma_mix: float = 0.5
    mediana_tamanho: float = 0.12
    rho: float = 0.85  # razão horas-padrão / registradas (9.7)
    sigma_medida: float = 0.35  # erro multiplicativo da eq. (2)
    fracao_atipicos_altos: float = 0.11  # horas > 2x o previsto (9.8)
    fracao_atipicos_baixos: float = 0.09  # horas < 0,5x o previsto (9.8)
    regra_implicita_a: float = 213.0  # F = a + b·H (9.4)
    regra_implicita_b: float = 32.0
    sigma_preco: float = 0.25
