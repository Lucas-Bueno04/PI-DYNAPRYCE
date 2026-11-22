"""Versão de política de preço (Quadro 7; plano §5): imutável, validada, com os β congelados."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from dynaprice.dominio.modelos.ajustes import KAPPA_TETO_ABSOLUTO
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.equacao_de_tempo import EquacaoDeTempo
from dynaprice.dominio.modelos.erros import TransicaoInvalida, ValorInvalido
from dynaprice.dominio.modelos.grandezas import Tarifa
from dynaprice.dominio.modelos.regime import Departamento, Regime


class OrigemTarifa(StrEnum):
    """Fontes de τ (seções 6.4 e 6.5)."""

    PRECO_REVELADO = "preco_revelado"
    CUSTO = "custo"
    RECEITA_ALVO = "receita_alvo"


class RegraSemHistorico(StrEnum):
    """ADR-004 item 5: só o piso do regime no MVP; vizinhos fica para F2/F3."""

    PISO_REGIME = "piso_regime"
    VIZINHOS = "vizinhos"


class EstadoPolitica(StrEnum):
    RASCUNHO = "rascunho"
    PUBLICADA = "publicada"
    SUBSTITUIDA = "substituida"


@dataclass(frozen=True, slots=True)
class PoliticaVersao:
    versao: int
    pisos: Mapping[Regime, Dinheiro]
    tarifa: Tarifa
    origem_tarifa: OrigemTarifa
    teto_real_theta: Decimal
    gatilho_delta: Decimal
    kappa_maximo: Decimal
    razao_s2_v2: Decimal
    sem_historico: RegraSemHistorico
    equacoes: tuple[EquacaoDeTempo, ...]
    fechamento_dias: int
    antecedencia_reajuste_meses: int
    arredondamento_multiplo: Decimal | None = None  # D11: comercial desligado por padrão
    estado: EstadoPolitica = EstadoPolitica.RASCUNHO

    def __post_init__(self) -> None:
        self._validar_escalares()
        self._validar_pisos()
        self._validar_equacoes()
        object.__setattr__(self, "pisos", MappingProxyType(dict(self.pisos)))

    def _validar_escalares(self) -> None:
        _exigir(self.versao >= 1, f"versão deve ser ≥ 1: {self.versao}")
        _exigir(self.teto_real_theta >= 0, f"θ deve ser ≥ 0: {self.teto_real_theta}")
        _exigir(self.gatilho_delta >= 0, f"δ deve ser ≥ 0: {self.gatilho_delta}")
        _exigir(
            1 <= self.kappa_maximo <= KAPPA_TETO_ABSOLUTO,
            f"κ̄ fora de [1; {KAPPA_TETO_ABSOLUTO}]: {self.kappa_maximo}",
        )
        _exigir(self.razao_s2_v2 > 0, f"s²/v² deve ser > 0: {self.razao_s2_v2}")
        _exigir(
            self.sem_historico is RegraSemHistorico.PISO_REGIME,
            f"sem_historico '{self.sem_historico}' não disponível no MVP (ADR-004)",
        )
        _exigir(self.fechamento_dias >= 0, f"dias de fechamento < 0: {self.fechamento_dias}")
        _exigir(self.antecedencia_reajuste_meses >= 0, "antecedência de reajuste < 0")
        multiplo = self.arredondamento_multiplo
        _exigir(multiplo is None or multiplo > 0, f"múltiplo de arredondamento ≤ 0: {multiplo}")

    def _validar_pisos(self) -> None:
        faltando = [r.value for r in Regime if r not in self.pisos]
        _exigir(not faltando, f"piso ausente para {faltando}")
        nulos = [r.value for r, p in self.pisos.items() if p.valor <= 0]
        _exigir(not nulos, f"piso deve ser > 0 em {nulos}")

    def _validar_equacoes(self) -> None:
        chaves = [e.chave for e in self.equacoes]
        _exigir(len(chaves) == len(set(chaves)), "equação de tempo duplicada")

    def piso(self, regime: Regime) -> Dinheiro:
        return self.pisos[regime]

    def equacao(self, departamento: Departamento, regime: Regime) -> EquacaoDeTempo:
        """Variante do regime (β0,m,r) se existir; senão a geral do departamento."""
        por_chave = {e.chave: e for e in self.equacoes}
        equacao = por_chave.get((departamento, regime)) or por_chave.get((departamento, None))
        if equacao is None:
            raise ValorInvalido(f"política v{self.versao} sem equação para {departamento}")
        return equacao

    @property
    def departamentos(self) -> frozenset[Departamento]:
        return frozenset(e.departamento for e in self.equacoes)

    def publicar(self) -> PoliticaVersao:
        return self._transitar(EstadoPolitica.RASCUNHO, EstadoPolitica.PUBLICADA)

    def substituir(self) -> PoliticaVersao:
        return self._transitar(EstadoPolitica.PUBLICADA, EstadoPolitica.SUBSTITUIDA)

    def _transitar(self, de: EstadoPolitica, para: EstadoPolitica) -> PoliticaVersao:
        if self.estado is not de:
            raise TransicaoInvalida(f"política v{self.versao}: {self.estado} → {para} proibido")
        return replace(self, estado=para)


def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ValorInvalido(mensagem)
