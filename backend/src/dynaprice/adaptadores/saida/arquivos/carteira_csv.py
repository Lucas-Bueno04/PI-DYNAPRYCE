"""Adapter: escreve a Carteira em CSV determinístico (ordem fixa, LF, Decimal com ponto)."""

import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from dynaprice.dominio.modelos import Carteira

type Linha = Sequence[object]


@dataclass(frozen=True, slots=True)
class TabelaCsv:
    """Um arquivo da exportação: nome, cabeçalho e como tirar as linhas da carteira."""

    nome: str
    cabecalho: Linha
    linhas: Callable[[Carteira], Iterable[Linha]]


def _empresas(c: Carteira) -> Iterable[Linha]:
    return ((e.id, e.regime, "|".join(sorted(e.departamentos))) for e in c.empresas)


def _contratos(c: Carteira) -> Iterable[Linha]:
    return (
        (k.id, k.preco_vigente, k.mes_reajuste, int(k.provisorio), k.kappa.valor)
        for k in c.contratos
    )


def _vinculos(c: Carteira) -> Iterable[Linha]:
    return (
        (v.empresa_id, v.contrato_id, v.desde, v.ate or "", int(v.principal)) for v in c.vinculos
    )


def _direcionadores(c: Carteira) -> Iterable[Linha]:
    return (
        (d.empresa_id, d.competencia, nome, d.valores[nome])
        for d in c.direcionadores
        for nome in sorted(d.valores)
    )


def _horas(c: Carteira) -> Iterable[Linha]:
    return ((h.empresa_id, h.competencia, h.departamento, h.horas.valor) for h in c.horas)


def _honorarios(c: Carteira) -> Iterable[Linha]:
    return ((h.contrato_id, h.competencia, h.valor) for h in c.honorarios)


TABELAS: tuple[TabelaCsv, ...] = (
    TabelaCsv("empresas.csv", ("empresa_id", "regime", "departamentos"), _empresas),
    TabelaCsv(
        "contratos.csv",
        ("contrato_id", "preco_vigente", "mes_reajuste", "provisorio", "kappa"),
        _contratos,
    ),
    TabelaCsv(
        "vinculos.csv", ("empresa_id", "contrato_id", "desde", "ate", "principal"), _vinculos
    ),
    TabelaCsv(
        "direcionadores.csv",
        ("empresa_id", "competencia", "direcionador", "valor"),
        _direcionadores,
    ),
    TabelaCsv("horas.csv", ("empresa_id", "competencia", "departamento", "horas"), _horas),
    TabelaCsv("honorarios.csv", ("contrato_id", "competencia", "valor"), _honorarios),
)


class EscritorDeCarteiraCsv:
    def __init__(self, pasta: Path) -> None:
        self._pasta = pasta

    def escrever(self, carteira: Carteira) -> None:
        self._pasta.mkdir(parents=True, exist_ok=True)
        for tabela in TABELAS:
            self._gravar(tabela, carteira)

    def _gravar(self, tabela: TabelaCsv, carteira: Carteira) -> None:
        with (self._pasta / tabela.nome).open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo, lineterminator="\n")
            escritor.writerow(tabela.cabecalho)
            escritor.writerows(tabela.linhas(carteira))
