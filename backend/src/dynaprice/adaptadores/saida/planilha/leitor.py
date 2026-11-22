"""Adapter p_src: planilha exportada pelo escritório (layout em docs/lab/layout_planilha.md).

Template do conector: ler → validar a minimização → normalizar. Só as colunas do layout são
lidas (lista de permissão); documento vira pseudônimo na leitura; arquivos ou colunas com
dados de empregado são recusados, porque o produto só precisa de contagens (RNF05).
"""

import csv
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dynaprice.adaptadores.saida.planilha.pseudonimo import Pseudonimizador
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

DIRECIONADORES = (
    "notas_entrada",
    "notas_saida",
    "lancamentos_manuais",
    "lancamentos_automaticos",
    "empregados",
    "admissoes",
    "rescisoes",
)
_PROIBIDAS = ("cpf", "salario", "nome_empregado", "empregado_nome")


def _numero(texto: str) -> Decimal:
    return Decimal(texto.strip().replace(",", "."))


def _sim(texto: str) -> bool:
    return texto.strip().upper() in {"S", "SIM", "1"}


@dataclass(frozen=True, slots=True)
class Rejeicao:
    """Linha recusada na leitura. Não guarda o conteúdo: ele pode ter dado pessoal."""

    arquivo: str
    linha: int
    motivo: str


_ERROS_DE_LINHA = (ValorInvalido, KeyError, ValueError, ArithmeticError, AttributeError)


class LeitorDePlanilhaDoEscritorio:
    def __init__(
        self, pasta: Path, pseudonimizador: Pseudonimizador, tolerante: bool = False
    ) -> None:
        self._pasta = pasta
        self._p = pseudonimizador
        self._tolerante = tolerante
        self.rejeicoes: list[Rejeicao] = []

    def _aplicar[T](self, funcao: Callable[[Linha], T], nome: str) -> Iterator[T]:
        for numero, linha in enumerate(self._linhas(nome), start=1):
            try:
                yield funcao(linha)
            except _ERROS_DE_LINHA as erro:
                if not self._tolerante:
                    raise
                self.rejeicoes.append(Rejeicao(nome, numero, type(erro).__name__))

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        if fim < inicio:
            raise ValorInvalido(f"janela invertida: {inicio} > {fim}")
        self._validar_pasta()

        def na_janela(competencia: Competencia) -> bool:
            return inicio <= competencia <= fim

        return Carteira(
            empresas=tuple(self._aplicar(self._empresa, "empresas.csv")),
            contratos=tuple(self._aplicar(_contrato, "contratos.csv")),
            vinculos=tuple(self._aplicar(self._vinculo, "vinculos.csv")),
            direcionadores=tuple(
                d
                for d in self._aplicar(self._movimento, "movimento.csv")
                if na_janela(d.competencia)
            ),
            horas=tuple(
                h for h in self._aplicar(self._horas, "horas.csv") if na_janela(h.competencia)
            ),
            honorarios=tuple(
                h for h in self._aplicar(_honorario, "honorarios.csv") if na_janela(h.competencia)
            ),
        )

    def _validar_pasta(self) -> None:
        if not self._pasta.is_dir():
            raise ValorInvalido(f"pasta da planilha não existe: {self._pasta}")
        if any("empregado" in arquivo.name for arquivo in self._pasta.iterdir()):
            raise ValorInvalido(
                "arquivo com linhas de empregado: o layout pede só contagens (RNF05)"
            )

    def _linhas(self, nome: str) -> Iterator[Linha]:
        with (self._pasta / nome).open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo, delimiter=";")
            proibidas = [
                c for c in leitor.fieldnames or [] if any(p in c.lower() for p in _PROIBIDAS)
            ]
            if proibidas:
                raise ValorInvalido(f"{nome}: colunas com dado de pessoa {proibidas} (cpf/salário)")
            yield from leitor

    def _empresa(self, linha: Linha) -> Empresa:
        departamentos = frozenset(Departamento(d) for d in linha["departamentos"].split("|"))
        return Empresa(
            self._p.pseudonimo(linha["documento"]), Regime(linha["regime"]), departamentos
        )

    def _vinculo(self, linha: Linha) -> Vinculo:
        ate = linha["ate"].strip()
        return Vinculo(
            self._p.pseudonimo(linha["documento"]),
            linha["contrato"],
            desde=Competencia.de_texto(linha["desde"]),
            ate=Competencia.de_texto(ate) if ate else None,
            principal=_sim(linha["principal"]),
        )

    def _movimento(self, linha: Linha) -> Direcionadores:
        valores = {n: _numero(linha[n]) for n in DIRECIONADORES if linha.get(n, "").strip()}
        competencia = Competencia.de_texto(linha["competencia"])
        return Direcionadores(self._p.pseudonimo(linha["documento"]), competencia, valores)

    def _horas(self, linha: Linha) -> HorasRegistradas:
        return HorasRegistradas(
            self._p.pseudonimo(linha["documento"]),
            Competencia.de_texto(linha["competencia"]),
            Departamento(linha["departamento"]),
            Horas(_numero(linha["horas"])),
        )


def _contrato(linha: Linha) -> Contrato:
    mes = linha["mes_reajuste"].strip()
    kappa = linha.get("kappa", "").strip()
    return Contrato(
        linha["contrato"],
        Dinheiro.de(_numero(linha["honorario_vigente"])),
        kappa=Kappa.de(_numero(kappa)) if kappa else Kappa.neutro(),
        mes_reajuste=int(mes) if mes else None,
        provisorio=_sim(linha["provisorio"]),
    )


def _honorario(linha: Linha) -> Honorario:
    competencia = Competencia.de_texto(linha["competencia"])
    return Honorario(linha["contrato"], competencia, Dinheiro.de(_numero(linha["valor"])))
