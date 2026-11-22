"""Comandos Typer da linha de comando `dynaprice`."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from dynaprice.aplicacao.casos_de_uso import ExportarCarteira, GerarRelatorioDoLaboratorio
from dynaprice.dominio.modelos import Competencia

Inicio = Annotated[str, typer.Option(help="Primeira competência (AAAA-MM).")]
Fim = Annotated[str, typer.Option(help="Última competência (AAAA-MM).")]


@dataclass(frozen=True, slots=True)
class FabricasDoLab:
    """O Composition Root injeta como montar cada caso de uso a partir dos argumentos."""

    sintetico: Callable[[int, int, Path], ExportarCarteira]
    relatorio: Callable[[str, Path, Path], GerarRelatorioDoLaboratorio]


def criar_grupo_lab(fabricas: FabricasDoLab) -> typer.Typer:
    """Grupo `lab` (laboratório offline)."""
    lab = typer.Typer(help="Laboratório: estimação e simulação sobre dados históricos.")
    _comando_sintetico(lab, fabricas)
    _comando_relatorio(lab, fabricas)
    return lab


def _comando_sintetico(lab: typer.Typer, fabricas: FabricasDoLab) -> None:

    @lab.command("sintetico")
    def sintetico(
        semente: Annotated[int, typer.Option(help="Semente do gerador (G1).")] = 42,
        saida: Annotated[Path, typer.Option(help="Pasta dos CSV.")] = Path("build/sintetico"),
        contratos: Annotated[int, typer.Option(help="Número de contratos.")] = 500,
        inicio: Inicio = "2025-01",
        fim: Fim = "2025-12",
    ) -> None:
        """Gera a carteira sintética calibrada no artigo e grava em CSV."""
        caso = fabricas.sintetico(semente, contratos, saida)
        resumo = caso.executar(Competencia.de_texto(inicio), Competencia.de_texto(fim))
        typer.echo(
            f"{resumo.contratos} contratos, {resumo.empresas} empresas, "
            f"{resumo.meses_empresa} meses-empresa em {saida}"
        )


def _comando_relatorio(lab: typer.Typer, fabricas: FabricasDoLab) -> None:
    @lab.command("relatorio")
    def relatorio(
        entrada: Annotated[Path, typer.Option(help="Pasta com os CSV da carteira.")],
        fonte: Annotated[
            str, typer.Option(help="csv (exportação do sintético) ou planilha.")
        ] = "csv",
        saida: Annotated[Path, typer.Option(help="Pasta do relatório.")] = Path("build/relatorio"),
        inicio: Inicio = "2025-01",
        fim: Fim = "2025-12",
    ) -> None:
        """Diagnóstico, estimação e simulação: relatório Markdown e rascunho de política."""
        caso = fabricas.relatorio(fonte, entrada, saida)
        gerado = caso.executar(Competencia.de_texto(inicio), Competencia.de_texto(fim))
        typer.echo(f"{len(gerado.secoes)} seções em {saida / 'relatorio.md'}")


def criar_cli(versao: str, lab: typer.Typer) -> typer.Typer:
    """Monta a CLI raiz com a versão e os grupos recebidos do Composition Root."""
    app = typer.Typer(
        help="DynaPrice: precificação dinâmica orientada a esforço para serviços profissionais."
    )

    @app.command("versao")
    def mostrar_versao() -> None:
        """Imprime a versão do pacote."""
        typer.echo(versao)

    app.add_typer(lab, name="lab")
    return app
