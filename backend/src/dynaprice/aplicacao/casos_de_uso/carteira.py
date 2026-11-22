"""Leituras da carteira para a interface: painel de indicadores e lista de clientes (contratos).

Só compõe o que os repositórios já expõem; nada é gravado. O "cliente" do sistema é o contrato:
a identificação da empresa é um pseudônimo (RNF05), nunca o nome nem o CNPJ.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.portas import FabricaDeUnidades, UnidadeDeTrabalho
from dynaprice.dominio.modelos import Competencia, Contrato, Empresa, Vinculo
from dynaprice.dominio.modelos.autenticacao import Principal

MESES_DA_SERIE = 12
MESES_DE_BUSCA = 36
MAIORES_DEFASAGENS = 10
_ZERO = Decimal(0)
_CEM = Decimal(100)
_FAIXAS: tuple[tuple[str, Decimal | None], ...] = (
    ("Muito abaixo do alvo (< -15%)", Decimal(-15)),
    ("Abaixo do alvo (-15% a -5%)", Decimal(-5)),
    ("Próximo do alvo (-5% a +5%)", Decimal(5)),
    ("Acima do alvo (+5% a +15%)", Decimal(15)),
    ("Muito acima do alvo (> +15%)", None),
)


@dataclass(frozen=True, slots=True)
class LinhaDeCliente:
    contrato_id: str
    regime: str | None
    empresas: int
    preco_vigente: Decimal
    preco_alvo: Decimal | None
    defasagem_pct: Decimal | None
    cobrado: Decimal | None
    mes_reajuste: int | None
    provisorio: bool
    kappa: Decimal
    recomendacao: str | None


@dataclass(frozen=True, slots=True)
class FatiaPorRegime:
    regime: str
    empresas: int
    contratos: int
    receita: Decimal


@dataclass(frozen=True, slots=True)
class PontoDaSerie:
    competencia: str
    valor: Decimal


@dataclass(frozen=True, slots=True)
class FaixaDeDefasagem:
    rotulo: str
    contratos: int


@dataclass(frozen=True, slots=True)
class Painel:
    competencia: str
    empresas: int
    contratos: int
    provisorios: int
    receita_mensal: Decimal
    receita_alvo: Decimal
    potencial_de_reajuste: Decimal
    alertas: int
    competencias_com_dados: tuple[str, ...]
    por_regime: tuple[FatiaPorRegime, ...]
    serie_receita: tuple[PontoDaSerie, ...]
    faixas: tuple[FaixaDeDefasagem, ...]
    recomendacoes: Mapping[str, int]
    divergencias: Mapping[str, int]
    maiores_defasagens: tuple[LinhaDeCliente, ...]


def _ativo(vinculo: Vinculo, competencia: Competencia) -> bool:
    return vinculo.desde <= competencia and (vinculo.ate is None or competencia <= vinculo.ate)


def _defasagem(vigente: Decimal, alvo: Decimal | None) -> Decimal | None:
    if alvo is None or alvo == _ZERO:
        return None
    return ((vigente - alvo) / alvo * _CEM).quantize(Decimal("0.1"))


def _regime_do_contrato(vinculos: Sequence[Vinculo], empresas: Mapping[str, Empresa]) -> str | None:
    ordenados = sorted(vinculos, key=lambda v: not v.principal)
    for vinculo in ordenados:
        empresa = empresas.get(vinculo.empresa_id)
        if empresa is not None:
            return empresa.regime.value
    return None


def _linhas(uow: UnidadeDeTrabalho, competencia: Competencia) -> tuple[LinhaDeCliente, ...]:
    empresas = {e.id: e for e in uow.empresas.listar()}
    ativos: dict[str, list[Vinculo]] = defaultdict(list)
    for vinculo in uow.vinculos.listar():
        if _ativo(vinculo, competencia):
            ativos[vinculo.contrato_id].append(vinculo)
    alvos = {a.contrato_id: a.preco_alvo for a in uow.precos_alvo.da_competencia(competencia)}
    cobrados = {
        h.contrato_id: h.valor.valor for h in uow.fatos.honorarios_da_competencia(competencia)
    }
    ultima: dict[str, tuple[Competencia, str]] = {}
    for r in uow.recomendacoes.listar():
        anterior = ultima.get(r.contrato_id)
        if anterior is None or anterior[0] <= r.competencia:
            ultima[r.contrato_id] = (r.competencia, r.estado.value)
    contratos: Sequence[Contrato] = uow.contratos.listar()
    return tuple(
        LinhaDeCliente(
            contrato_id=c.id,
            regime=_regime_do_contrato(ativos.get(c.id, []), empresas),
            empresas=len(ativos.get(c.id, [])),
            preco_vigente=c.preco_vigente.valor,
            preco_alvo=alvos.get(c.id),
            defasagem_pct=_defasagem(c.preco_vigente.valor, alvos.get(c.id)),
            cobrado=cobrados.get(c.id),
            mes_reajuste=c.mes_reajuste,
            provisorio=c.provisorio,
            kappa=c.kappa.valor,
            recomendacao=ultima[c.id][1] if c.id in ultima else None,
        )
        for c in sorted(contratos, key=lambda c: c.id)
    )


def _faixas(linhas: Sequence[LinhaDeCliente]) -> tuple[FaixaDeDefasagem, ...]:
    contagem = [0] * len(_FAIXAS)
    for linha in linhas:
        if linha.defasagem_pct is None:
            continue
        for posicao, (_, limite) in enumerate(_FAIXAS):
            if limite is None or linha.defasagem_pct < limite:
                contagem[posicao] += 1
                break
    return tuple(
        FaixaDeDefasagem(rotulo, n) for (rotulo, _), n in zip(_FAIXAS, contagem, strict=True)
    )


class ListarClientes:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, competencia: Competencia) -> Sequence[LinhaDeCliente]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            return _linhas(uow, competencia)


class ConsultarPainel:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, competencia: Competencia) -> Painel:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            linhas = _linhas(uow, competencia)
            totais = {
                mes: sum((h.valor.valor for h in uow.fatos.honorarios_da_competencia(mes)), _ZERO)
                for mes in (competencia.somar(-i) for i in range(MESES_DE_BUSCA))
            }
            serie = tuple(
                PontoDaSerie(str(competencia.somar(-i)), totais[competencia.somar(-i)])
                for i in range(MESES_DA_SERIE - 1, -1, -1)
            )
            com_dados = tuple(
                str(competencia.somar(-i))
                for i in range(MESES_DE_BUSCA)
                if totais[competencia.somar(-i)] > _ZERO
            )
            recomendacoes = Counter(r.estado.value for r in uow.recomendacoes.listar())
            divergencias = Counter(d.situacao.value for d in uow.divergencias.listar())
            alertas = len(uow.alertas.nao_reconhecidos())
            total_empresas = len(uow.empresas.listar())
        return Painel(
            competencia=str(competencia),
            empresas=total_empresas,
            contratos=len(linhas),
            provisorios=sum(1 for linha in linhas if linha.provisorio),
            receita_mensal=sum((linha.cobrado or _ZERO for linha in linhas), _ZERO),
            receita_alvo=sum((linha.preco_alvo or _ZERO for linha in linhas), _ZERO),
            potencial_de_reajuste=sum(
                (
                    max(linha.preco_alvo - linha.preco_vigente, _ZERO)
                    for linha in linhas
                    if linha.preco_alvo is not None
                ),
                _ZERO,
            ),
            alertas=alertas,
            competencias_com_dados=com_dados,
            por_regime=_por_regime(linhas),
            serie_receita=serie,
            faixas=_faixas(linhas),
            recomendacoes=dict(recomendacoes),
            divergencias=dict(divergencias),
            maiores_defasagens=tuple(
                sorted(
                    (
                        linha
                        for linha in linhas
                        if linha.defasagem_pct is not None and linha.defasagem_pct < _ZERO
                    ),
                    key=lambda linha: linha.defasagem_pct or _ZERO,
                )[:MAIORES_DEFASAGENS]
            ),
        )


def _por_regime(linhas: Sequence[LinhaDeCliente]) -> tuple[FatiaPorRegime, ...]:
    contratos: Counter[str] = Counter()
    empresas: Counter[str] = Counter()
    receita: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for linha in linhas:
        regime = linha.regime or "N/D"
        contratos[regime] += 1
        empresas[regime] += linha.empresas
        receita[regime] += linha.cobrado or _ZERO
    return tuple(
        FatiaPorRegime(regime, empresas[regime], contratos[regime], receita[regime])
        for regime in sorted(contratos)
    )
