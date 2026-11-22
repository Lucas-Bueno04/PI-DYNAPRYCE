"""Factory: monta PoliticaVersao a partir do documento declarativo (Quadro 7).

Centraliza a leitura do documento; a validação das invariantes fica no próprio tipo.
Números vêm como str/int/Decimal; float é recusado (o adaptador lê JSON com parse_float=Decimal).
"""

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Any

from dynaprice.dominio.modelos.conversao import para_decimal
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.equacao_de_tempo import EquacaoDeTempo
from dynaprice.dominio.modelos.erros import ValorInvalido
from dynaprice.dominio.modelos.grandezas import Tarifa
from dynaprice.dominio.modelos.politica import OrigemTarifa, PoliticaVersao, RegraSemHistorico
from dynaprice.dominio.modelos.regime import Departamento, Regime

type Documento = Mapping[str, Any]


def fabricar_politica(documento: Documento) -> PoliticaVersao:
    tarifa = _secao(documento, "tarifa_hora_padrao")
    reajuste = _secao(documento, "reajuste")
    incompleta = _secao(documento, "informacao_incompleta")
    return PoliticaVersao(
        versao=_inteiro(documento, "versao"),
        pisos=_pisos(_secao(documento, "piso_por_segmento")),
        tarifa=Tarifa.de(_campo(tarifa, "valor")),
        origem_tarifa=_enum(OrigemTarifa, _campo(tarifa, "origem")),
        teto_real_theta=para_decimal(_campo(reajuste, "teto_real_por_ciclo"), "θ"),
        gatilho_delta=para_decimal(_campo(documento, "gatilho_revisao"), "δ"),
        kappa_maximo=para_decimal(_campo(documento, "kappa_maximo"), "κ̄"),
        razao_s2_v2=para_decimal(_campo(incompleta, "razao_s2_v2"), "s²/v²"),
        sem_historico=_enum(RegraSemHistorico, _campo(incompleta, "sem_historico")),
        equacoes=tuple(_equacao(e) for e in _campo(documento, "equacoes_de_tempo")),
        fechamento_dias=_inteiro(documento, "fechamento_dias"),
        antecedencia_reajuste_meses=_inteiro(reajuste, "antecedencia_meses"),
        arredondamento_multiplo=_multiplo(documento.get("arredondamento")),
    )


def _multiplo(secao: Documento | None) -> Decimal | None:
    if secao is None:
        return None
    return para_decimal(_campo(secao, "multiplo"), "arredondamento.multiplo")


def _campo(secao: Documento, nome: str) -> Any:
    if nome not in secao:
        raise ValorInvalido(f"documento de política sem o campo '{nome}'")
    return secao[nome]


def _secao(documento: Documento, nome: str) -> Documento:
    valor = _campo(documento, nome)
    if not isinstance(valor, Mapping):
        raise ValorInvalido(f"'{nome}' deve ser um objeto")
    return valor


def _inteiro(secao: Documento, nome: str) -> int:
    valor = _campo(secao, nome)
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValorInvalido(f"'{nome}' deve ser inteiro: {valor!r}")
    return valor


def _enum[E: StrEnum](tipo: type[E], valor: Any) -> E:
    try:
        return tipo(valor)
    except ValueError as erro:
        raise ValorInvalido(f"{tipo.__name__} inválido: {valor!r}") from erro


def _pisos(secao: Documento) -> dict[Regime, Dinheiro]:
    return {_enum(Regime, regime): Dinheiro.de(valor) for regime, valor in secao.items()}


def _equacao(item: Documento) -> EquacaoDeTempo:
    regime = item.get("regime")
    inclinacoes = _secao(item, "inclinacoes_minutos")
    return EquacaoDeTempo(
        departamento=_enum(Departamento, _campo(item, "departamento")),
        beta0_horas=para_decimal(_campo(item, "beta0_horas"), "β0"),
        inclinacoes_minutos={k: para_decimal(v, k) for k, v in inclinacoes.items()},
        regime=None if regime is None else _enum(Regime, regime),
    )
