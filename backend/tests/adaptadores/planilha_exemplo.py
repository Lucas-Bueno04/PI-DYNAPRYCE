"""Gera uma planilha no layout do escritório (docs/lab/layout_planilha.md) a partir de uma
carteira, com documentos e nomes falsos e colunas proibidas, para testar o leitor."""

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from dynaprice.dominio.modelos import Carteira

DIRECIONADORES = (
    "notas_entrada",
    "notas_saida",
    "lancamentos_manuais",
    "lancamentos_automaticos",
    "empregados",
    "admissoes",
    "rescisoes",
)


def documento_falso(empresa_id: str) -> str:
    numero = int(empresa_id[1:])
    return f"{numero:02d}.{numero % 1000:03d}.{numero % 997:03d}/0001-{numero % 97:02d}"


def _br(valor: object) -> str:
    return str(valor).replace(".", ",")


def _gravar(caminho: Path, cabecalho: Sequence[str], linhas: Iterable[Sequence[object]]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";", lineterminator="\n")
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)


def escrever_planilha(carteira: Carteira, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    doc = documento_falso
    _gravar(
        pasta / "empresas.csv",
        ("documento", "razao_social", "regime", "departamentos"),
        (
            (doc(e.id), f"Fulano da Silva {e.id} ME", e.regime, "|".join(sorted(e.departamentos)))
            for e in carteira.empresas
        ),
    )
    _gravar(
        pasta / "contratos.csv",
        ("contrato", "honorario_vigente", "mes_reajuste", "provisorio", "kappa"),
        (
            (
                c.id,
                _br(c.preco_vigente),
                c.mes_reajuste or "",
                "S" if c.provisorio else "N",
                _br(c.kappa.valor),
            )
            for c in carteira.contratos
        ),
    )
    _gravar(
        pasta / "vinculos.csv",
        ("documento", "contrato", "desde", "ate", "principal"),
        (
            (doc(v.empresa_id), v.contrato_id, v.desde, v.ate or "", "S" if v.principal else "N")
            for v in carteira.vinculos
        ),
    )
    _gravar(
        pasta / "movimento.csv",
        ("documento", "competencia", *DIRECIONADORES),
        (
            (doc(d.empresa_id), d.competencia, *(d.valor(n) for n in DIRECIONADORES))
            for d in carteira.direcionadores
        ),
    )
    _gravar(
        pasta / "horas.csv",
        ("documento", "competencia", "departamento", "horas", "colaborador"),
        (
            (doc(h.empresa_id), h.competencia, h.departamento, _br(h.horas.valor), "Maria Souza")
            for h in carteira.horas
        ),
    )
    _gravar(
        pasta / "honorarios.csv",
        ("contrato", "competencia", "valor"),
        ((h.contrato_id, h.competencia, _br(h.valor)) for h in carteira.honorarios),
    )
