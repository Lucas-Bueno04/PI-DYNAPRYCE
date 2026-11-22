"""Adapter p_src: lê a carteira dos CSV do EscritorDeCarteiraCsv (inverso exato da escrita)."""

import csv
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Contrato,
    Departamento,
    Dinheiro,
    Direcionadores,
    Empresa,
    Honorario,
    Horas,
    HorasRegistradas,
    Kappa,
    Regime,
    ValorInvalido,
    Vinculo,
)

type Linha = dict[str, str]


def validar_janela(inicio: Competencia, fim: Competencia) -> None:
    if fim < inicio:
        raise ValorInvalido(f"janela invertida: {inicio} > {fim}")


class LeitorDeCarteiraCsv:
    def __init__(self, pasta: Path) -> None:
        self._pasta = pasta

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        validar_janela(inicio, fim)
        if not self._pasta.is_dir():
            raise ValorInvalido(f"pasta da carteira não existe: {self._pasta}")

        def na_janela(competencia: Competencia) -> bool:
            return inicio <= competencia <= fim

        return Carteira(
            empresas=tuple(map(_empresa, self._linhas("empresas.csv"))),
            contratos=tuple(map(_contrato, self._linhas("contratos.csv"))),
            vinculos=tuple(map(_vinculo, self._linhas("vinculos.csv"))),
            direcionadores=tuple(d for d in self._direcionadores() if na_janela(d.competencia)),
            horas=tuple(
                h for h in map(_horas, self._linhas("horas.csv")) if na_janela(h.competencia)
            ),
            honorarios=tuple(
                h
                for h in map(_honorario, self._linhas("honorarios.csv"))
                if na_janela(h.competencia)
            ),
        )

    def _linhas(self, nome: str) -> Iterator[Linha]:
        with (self._pasta / nome).open(encoding="utf-8", newline="") as arquivo:
            yield from csv.DictReader(arquivo)

    def _direcionadores(self) -> Iterator[Direcionadores]:
        """Agrupa as linhas longas (empresa, competência, direcionador, valor) em ordem."""
        chave: tuple[str, str] | None = None
        valores: dict[str, Decimal] = {}
        for linha in self._linhas("direcionadores.csv"):
            atual = (linha["empresa_id"], linha["competencia"])
            if chave is not None and atual != chave:
                yield _registro(chave, valores)
                valores = {}
            chave = atual
            valores[linha["direcionador"]] = Decimal(linha["valor"])
        if chave is not None:
            yield _registro(chave, valores)


def _registro(chave: tuple[str, str], valores: dict[str, Decimal]) -> Direcionadores:
    return Direcionadores(chave[0], Competencia.de_texto(chave[1]), valores)


def _empresa(linha: Linha) -> Empresa:
    departamentos = frozenset(Departamento(d) for d in linha["departamentos"].split("|"))
    return Empresa(linha["empresa_id"], Regime(linha["regime"]), departamentos)


def _contrato(linha: Linha) -> Contrato:
    mes = linha["mes_reajuste"]
    return Contrato(
        linha["contrato_id"],
        Dinheiro.de(linha["preco_vigente"]),
        kappa=Kappa.de(linha["kappa"]),
        mes_reajuste=int(mes) if mes else None,
        provisorio=linha["provisorio"] == "1",
    )


def _vinculo(linha: Linha) -> Vinculo:
    ate = linha["ate"]
    return Vinculo(
        linha["empresa_id"],
        linha["contrato_id"],
        desde=Competencia.de_texto(linha["desde"]),
        ate=Competencia.de_texto(ate) if ate else None,
        principal=linha["principal"] == "1",
    )


def _horas(linha: Linha) -> HorasRegistradas:
    return HorasRegistradas(
        linha["empresa_id"],
        Competencia.de_texto(linha["competencia"]),
        Departamento(linha["departamento"]),
        Horas.de(linha["horas"]),
    )


def _honorario(linha: Linha) -> Honorario:
    return Honorario(
        linha["contrato_id"],
        Competencia.de_texto(linha["competencia"]),
        Dinheiro.de(linha["valor"]),
    )
