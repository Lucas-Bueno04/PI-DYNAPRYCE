"""Protocolo de ocultação (artigo 5.15 e 10.5): mede o erro da inferência sob informação incompleta.

Para cada contrato com 12 meses (preço-alvo conhecido) oculta-se parte da informação, infere-se o
preço por cada estimador e compara-se com o alvo. Validação cruzada em K dobras: o vizinho de um
contrato nunca vem da própria dobra. O erro é o EPAM do preço (Eq. 7 adaptada), com o denominador
limitado pelo menor piso da política. A vizinhança (Gower + kNN) é só offline: a cotação usa o
piso do regime (ADR-004).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean, median
from typing import Protocol

from dynaprice.dominio.modelos import Departamento, Horas, PoliticaVersao, Regime, ValorInvalido
from dynaprice.dominio.precificacao import PoliticaDePreco
from dynaprice.dominio.precificacao.inferencia import fator_de_credibilidade

MESES_COMPLETOS = 12
MINIMO_DE_CONTRATOS = 2


@dataclass(frozen=True, slots=True)
class ContratoConhecido:
    id: str
    regime: Regime
    departamentos: frozenset[Departamento]
    horas_mensais: tuple[Horas, ...]  # horas-padrão do contrato, 12 meses em ordem


@dataclass(frozen=True, slots=True)
class LinhaDeEpam:
    estimador: str
    meses: int
    epam: float
    vies_mediano: float  # mediana de (previsto − alvo)/alvo; negativo = subprecifica
    n: int


@dataclass(frozen=True, slots=True)
class ResultadoDaOcultacao:
    linhas: tuple[LinhaDeEpam, ...]
    dobras: int

    def melhor(self, meses: int) -> str:
        candidatas = [x for x in self.linhas if x.meses == meses]
        return min(candidatas, key=lambda x: (x.epam, x.estimador)).estimador


@dataclass(frozen=True, slots=True)
class _Alvo:
    contrato: ContratoConhecido
    alvo: float


class Estimador(Protocol):
    nome: str

    def prever(self, oculto: _Alvo, meses: int, treino: Sequence[_Alvo]) -> float: ...


class _Ferramentas:
    """Cálculos de preço compartilhados pelos estimadores (uma política, uma regra de preço)."""

    def __init__(self, politica: PoliticaVersao) -> None:
        self.politica = politica
        self.preco = PoliticaDePreco(politica)

    def piso(self, regime: Regime) -> float:
        return float(self.politica.piso(regime).valor)

    def proprio(self, contrato: ContratoConhecido, meses: int) -> float:
        """max(π_r, τ·H_pad,pr) com a média das horas dos meses vistos."""
        vistas = contrato.horas_mensais[:meses]
        media = Horas(sum((h.valor for h in vistas), Decimal(0)) / len(vistas))
        return float(self.preco.base(contrato.regime, media))

    def peso(self, meses: int) -> float:
        return float(fator_de_credibilidade(meses, self.politica.razao_s2_v2))


class _PisoDoRegime:
    nome = "piso_regime"

    def __init__(self, f: _Ferramentas) -> None:
        self._f = f

    def prever(self, oculto: _Alvo, meses: int, treino: Sequence[_Alvo]) -> float:
        return self._f.piso(oculto.contrato.regime)


class _Credibilidade:
    nome = "credibilidade"

    def __init__(self, f: _Ferramentas) -> None:
        self._f = f

    def prever(self, oculto: _Alvo, meses: int, treino: Sequence[_Alvo]) -> float:
        piso = self._f.piso(oculto.contrato.regime)
        if meses == 0:
            return piso
        z = self._f.peso(meses)
        return z * self._f.proprio(oculto.contrato, meses) + (1 - z) * piso


def distancia_de_gower(a: ContratoConhecido, b: ContratoConhecido) -> float:
    """Atributos categóricos do perfil: regime e cada departamento atendido; média de 0/1."""
    desencontros = [a.regime is not b.regime]
    desencontros += [(d in a.departamentos) != (d in b.departamentos) for d in Departamento]
    return sum(desencontros) / len(desencontros)


def _media_dos_vizinhos(oculto: _Alvo, treino: Sequence[_Alvo], k: int) -> float:
    ordem = sorted(
        treino, key=lambda t: (distancia_de_gower(oculto.contrato, t.contrato), t.contrato.id)
    )
    return fmean(t.alvo for t in ordem[:k])


class _Vizinhos:
    def __init__(self, k: int) -> None:
        self.nome = f"vizinhos_k{k}"
        self._k = k

    def prever(self, oculto: _Alvo, meses: int, treino: Sequence[_Alvo]) -> float:
        return _media_dos_vizinhos(oculto, treino, self._k)


class _CredibilidadeComVizinhos:
    """Eq. (55–56) do artigo: Z·média própria + (1 − Z)·inferência por vizinhança."""

    def __init__(self, f: _Ferramentas, k: int) -> None:
        self.nome = f"credibilidade_com_vizinhos_k{k}"
        self._f, self._k = f, k

    def prever(self, oculto: _Alvo, meses: int, treino: Sequence[_Alvo]) -> float:
        vizinhos = _media_dos_vizinhos(oculto, treino, self._k)
        if meses == 0:
            return vizinhos
        z = self._f.peso(meses)
        return z * self._f.proprio(oculto.contrato, meses) + (1 - z) * vizinhos


def _validar(
    contratos: Sequence[ContratoConhecido], meses_ocultos: Sequence[int], dobras: int
) -> None:
    if dobras < 2:
        raise ValorInvalido(f"dobras deve ser ao menos 2: {dobras}")
    if len(contratos) < dobras * MINIMO_DE_CONTRATOS:
        raise ValorInvalido(f"contratos insuficientes: {len(contratos)} para {dobras} dobras")
    if any(not 0 <= m < MESES_COMPLETOS for m in meses_ocultos):
        raise ValorInvalido("meses vistos devem estar entre 0 e 11")
    curtos = [c.id for c in contratos if len(c.horas_mensais) != MESES_COMPLETOS]
    if curtos:
        raise ValorInvalido(f"contratos sem 12 meses de horas: {curtos[:3]}")


def _estimadores(f: _Ferramentas, ks: Sequence[int]) -> list[Estimador]:
    return [
        _PisoDoRegime(f),
        _Credibilidade(f),
        *(_Vizinhos(k) for k in ks),
        *(_CredibilidadeComVizinhos(f, k) for k in ks),
    ]


def _linha(
    nome: str, meses: int, previstos: list[float], alvos: list[float], piso: float
) -> LinhaDeEpam:
    relativos = [(p - a) / max(a, piso) for p, a in zip(previstos, alvos, strict=True)]
    return LinhaDeEpam(
        nome, meses, median(abs(r) for r in relativos), median(relativos), len(relativos)
    )


def _previsoes(
    estimador: Estimador, conhecidos: Sequence[_Alvo], meses: int, dobras: int
) -> list[float]:
    """Cada contrato é previsto só com os contratos de outras dobras (sem vazamento)."""
    previstos: list[float] = []
    for i, oculto in enumerate(conhecidos):
        treino = [c for j, c in enumerate(conhecidos) if j % dobras != i % dobras]
        previstos.append(estimador.prever(oculto, meses, treino))
    return previstos


def executar_ocultacao(
    contratos: Sequence[ContratoConhecido],
    politica: PoliticaVersao,
    meses_ocultos: Sequence[int] = (0, 1, 3, 6, 9),
    ks: Sequence[int] = (3, 5, 10),
    dobras: int = 5,
) -> ResultadoDaOcultacao:
    _validar(contratos, meses_ocultos, dobras)
    f = _Ferramentas(politica)
    conhecidos = [_Alvo(c, f.proprio(c, MESES_COMPLETOS)) for c in sorted(contratos, key=_id)]
    alvos = [c.alvo for c in conhecidos]
    piso_minimo = min(float(politica.piso(r).valor) for r in Regime)
    linhas = [
        _linha(e.nome, m, _previsoes(e, conhecidos, m, dobras), alvos, piso_minimo)
        for e in _estimadores(f, ks)
        for m in meses_ocultos
    ]
    return ResultadoDaOcultacao(tuple(linhas), dobras)


def _id(contrato: ContratoConhecido) -> str:
    return contrato.id
