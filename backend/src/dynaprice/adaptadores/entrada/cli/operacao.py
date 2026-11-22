"""Comandos de operação da cli: migração, primeiro administrador, worker e manutenção."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from dynaprice.aplicacao.casos_de_uso.ancora import ResultadoDaVerificacao
from dynaprice.aplicacao.casos_de_uso.indices import ResumoDaCargaDoIndice
from dynaprice.aplicacao.casos_de_uso.recalcular import ComparacaoDoRecalculo
from dynaprice.aplicacao.erros import ErroDeAplicacao
from dynaprice.dominio.modelos import Competencia, ValorInvalido

_VARIAVEL_DA_SENHA = "DYNAPRICE_SENHA_ADMIN"


@dataclass(frozen=True, slots=True)
class FabricasDeOperacao:
    migrar: Callable[[], None]
    criar_admin: Callable[[str, str, str], UUID]
    recalcular: Callable[[UUID, UUID], ComparacaoDoRecalculo]
    worker: Callable[[bool], None]
    rotacionar_chave: Callable[[], int]
    exportar_openapi: Callable[[Path], None]
    atualizar_indice: Callable[[Competencia, Competencia], ResumoDaCargaDoIndice]
    ancorar_auditoria: Callable[[], int]
    verificar_auditoria: Callable[[], tuple[ResultadoDaVerificacao, ...]]


def registrar_operacao(app: typer.Typer, fabricas: FabricasDeOperacao) -> None:
    banco = typer.Typer(help="Banco de dados.")

    @banco.command("migrar")
    def migrar() -> None:
        """Aplica as migrações pendentes (usar a credencial do migrador)."""
        fabricas.migrar()
        typer.echo("banco na revisão mais recente")

    app.add_typer(banco, name="banco")
    app.add_typer(_grupo_indice(fabricas), name="indice")
    app.add_typer(_grupo_auditoria(fabricas), name="auditoria")
    _comandos_de_operacao(app, fabricas)
    _comandos_de_manutencao(app, fabricas)


def _comandos_de_operacao(app: typer.Typer, fabricas: FabricasDeOperacao) -> None:
    @app.command("criar-admin")
    def criar_admin(
        inquilino: Annotated[str, typer.Option(help="Nome do escritório.")],
        email: Annotated[str, typer.Option(help="E-mail do administrador.")],
    ) -> None:
        """Cria o primeiro inquilino e administrador; só funciona com o banco sem administrador."""
        senha = os.environ.get(_VARIAVEL_DA_SENHA) or typer.prompt("Senha", hide_input=True)
        try:
            tenant = fabricas.criar_admin(inquilino, email, senha)
        except (ErroDeAplicacao, ValorInvalido) as erro:
            typer.echo(str(erro))
            raise typer.Exit(1) from erro
        typer.echo(f"inquilino {tenant}")

    @app.command("recalcular")
    def recalcular(
        tenant: Annotated[UUID, typer.Option(help="Inquilino.")],
        identificador: Annotated[UUID, typer.Option("--id", help="Id do preço-alvo.")],
    ) -> None:
        """Refaz o preço-alvo a partir das entradas gravadas e compara ao centavo."""
        comparacao = fabricas.recalcular(tenant, identificador)
        typer.echo(f"gravado {comparacao.gravado} recalculado {comparacao.recalculado}")
        if comparacao.gravado != comparacao.recalculado:
            raise typer.Exit(1)


def _comandos_de_manutencao(app: typer.Typer, fabricas: FabricasDeOperacao) -> None:
    @app.command("worker")
    def worker(
        uma_vez: Annotated[bool, typer.Option("--uma-vez", help="Processa um job e sai.")] = False,
    ) -> None:
        """Consome a fila de jobs."""
        fabricas.worker(uma_vez)

    @app.command("rotacionar-chave")
    def rotacionar_chave() -> None:
        """Recifra os segredos com a chave mestra mais nova."""
        typer.echo(f"{fabricas.rotacionar_chave()} segredos recifrados")

    @app.command("openapi")
    def openapi(
        saida: Annotated[Path, typer.Option(help="Arquivo de saída.")] = Path(
            "frontend/openapi.json"
        ),
    ) -> None:
        """Exporta o contrato OpenAPI usado para gerar o cliente."""
        fabricas.exportar_openapi(saida)


def _competencia(texto: str) -> Competencia:
    try:
        return Competencia.de_texto(texto)
    except ValorInvalido as erro:
        raise typer.BadParameter(f"competência inválida: {texto} (use AAAA-MM)") from erro


def _grupo_indice(fabricas: FabricasDeOperacao) -> typer.Typer:
    indice = typer.Typer(help="Índice de inflação (global; exige a credencial do migrador).")

    @indice.command("atualizar")
    def atualizar(
        inicio: Annotated[str, typer.Option(help="Primeira competência (AAAA-MM).")],
        fim: Annotated[str, typer.Option(help="Última competência (AAAA-MM).")],
    ) -> None:
        """Carrega o IPCA do BCB sem sobrescrever o que já foi gravado."""
        primeira, ultima = _competencia(inicio), _competencia(fim)
        if ultima < primeira:
            raise typer.BadParameter("o fim é anterior ao início")
        resumo = fabricas.atualizar_indice(primeira, ultima)
        typer.echo(
            f"{resumo.inseridos} gravados, {resumo.iguais} já existiam, "
            f"{len(resumo.divergentes)} divergentes"
        )
        for d in resumo.divergentes:
            typer.echo(f"divergente {d.competencia}: gravado {d.gravado}, BCB {d.da_fonte}")
        if resumo.divergentes:
            raise typer.Exit(1)

    return indice


def _linhas_do_problema(resultado: ResultadoDaVerificacao) -> list[str]:
    linhas = [f"inquilino {resultado.tenant_id}:"]
    if resultado.quebra_interna is not None:
        linhas.append(f"  cadeia quebrada no evento {resultado.quebra_interna}")
    for d in resultado.divergencias:
        motivo = "evento ausente" if d.no_banco is None else "hash diferente"
        linhas.append(f"  âncora do evento {d.seq} não confere ({motivo})")
    return linhas


def _grupo_auditoria(fabricas: FabricasDeOperacao) -> typer.Typer:
    auditoria = typer.Typer(help="Trilha de auditoria e âncora externa (RNF06).")

    @auditoria.command("ancorar")
    def ancorar() -> None:
        """Publica na âncora externa a cabeça da cadeia de cada inquilino com evento novo."""
        typer.echo(f"{fabricas.ancorar_auditoria()} âncoras gravadas")

    @auditoria.command("verificar")
    def verificar() -> None:
        """Confere a cadeia e as âncoras; sai com código 1 se algo não conferir."""
        resultados = fabricas.verificar_auditoria()
        problemas = [r for r in resultados if not r.integro]
        for r in problemas:
            for linha in _linhas_do_problema(r):
                typer.echo(linha)
        if problemas:
            raise typer.Exit(1)
        typer.echo(f"{len(resultados)} inquilino(s) íntegro(s)")

    return auditoria
