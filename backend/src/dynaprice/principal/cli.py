"""Composição da linha de comando."""

import os
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

import httpx
import typer

from dynaprice.adaptadores.entrada.api.aplicacao import criar_app
from dynaprice.adaptadores.entrada.cli.comandos import FabricasDoLab, criar_cli, criar_grupo_lab
from dynaprice.adaptadores.entrada.cli.operacao import FabricasDeOperacao, registrar_operacao
from dynaprice.adaptadores.saida.arquivos import (
    EscritorDeCarteiraCsv,
    EscritorDeRelatorioMarkdown,
    LeitorDeCarteiraCsv,
)
from dynaprice.adaptadores.saida.arquivos.ancora import AncoraEmArquivo
from dynaprice.adaptadores.saida.conectores.bcb import ConectorBcbIpca
from dynaprice.adaptadores.saida.planilha import LeitorDePlanilhaDoEscritorio, Pseudonimizador
from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres, abrir_pool
from dynaprice.adaptadores.saida.postgres.indices import IndicesDeInflacaoPostgres
from dynaprice.adaptadores.saida.postgres.migracoes import migrar
from dynaprice.adaptadores.saida.relogio import RelogioDoSistema
from dynaprice.adaptadores.saida.seguranca import (
    CifradorAesGcm,
    EmissorJwtEs256,
    HashDeSenhaArgon2,
    VerificadorTotpPyotp,
    carregar_chaves_es256,
    carregar_chaves_mestras,
)
from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.aplicacao.casos_de_uso import ExportarCarteira, GerarRelatorioDoLaboratorio
from dynaprice.aplicacao.casos_de_uso.ancora import (
    AncorarAuditoria,
    ResultadoDaVerificacao,
    VerificarAuditoria,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao import DependenciasDeAutenticacao
from dynaprice.aplicacao.casos_de_uso.indices import (
    AtualizarIndiceDeInflacao,
    ResumoDaCargaDoIndice,
)
from dynaprice.aplicacao.casos_de_uso.recalcular import ComparacaoDoRecalculo, RecalcularPrecoAlvo
from dynaprice.aplicacao.casos_de_uso.rotacionar_chave import RotacionarChaveMestra
from dynaprice.aplicacao.casos_de_uso.usuarios import CriarPrimeiroAdministrador
from dynaprice.aplicacao.portas import FonteDeCarteira
from dynaprice.dominio.estimacao.diagnostico import AnalisadorDoLaboratorio
from dynaprice.dominio.modelos import Competencia
from dynaprice.principal.api import AUDIENCIA_JWT, EMISSOR_JWT, exportar_openapi
from dynaprice.principal.comum import (
    caminho_do_segredo,
    exigir_ambiente,
    ler_segredo,
    pseudonimo_de_ip,
)
from dynaprice.principal.worker import rodar_worker

VARIAVEL_DA_CHAVE = "DYNAPRICE_CHAVE_PSEUDONIMO"


def exportar_sintetico(semente: int, contratos: int, saida: Path) -> ExportarCarteira:
    fonte = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=semente, contratos=contratos))
    return ExportarCarteira(fonte, EscritorDeCarteiraCsv(saida))


def fonte_de_arquivo(tipo: str, entrada: Path) -> FonteDeCarteira:
    if tipo == "csv":
        return LeitorDeCarteiraCsv(entrada)
    if tipo == "planilha":
        chave = os.environ.get(VARIAVEL_DA_CHAVE, "")
        if not chave:
            raise typer.BadParameter(f"defina {VARIAVEL_DA_CHAVE} (chave de pseudonimização)")
        return LeitorDePlanilhaDoEscritorio(entrada, Pseudonimizador(chave.encode()))
    raise typer.BadParameter(f"fonte desconhecida: {tipo} (use csv ou planilha)")


def relatorio_do_laboratorio(tipo: str, entrada: Path, saida: Path) -> GerarRelatorioDoLaboratorio:
    return GerarRelatorioDoLaboratorio(
        fonte_de_arquivo(tipo, entrada),
        AnalisadorDoLaboratorio(),
        EscritorDeRelatorioMarkdown(saida),
    )


def _migrar() -> None:
    migrar(ler_segredo("DYNAPRICE_DB_URL_FILE"))


def _criar_admin(inquilino: str, email: str, senha: str) -> UUID:
    relogio = RelogioDoSistema()
    with abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE"), tamanho_maximo=2) as pool:
        chaves = carregar_chaves_mestras(caminho_do_segredo("DYNAPRICE_CHAVES_MESTRAS_FILE"))
        deps = DependenciasDeAutenticacao(
            fabrica=FabricaDeUnidadesPostgres(pool, relogio),
            relogio=relogio,
            hash_de_senha=HashDeSenhaArgon2(),
            totp=VerificadorTotpPyotp(),
            emissor=EmissorJwtEs256(
                carregar_chaves_es256(caminho_do_segredo("DYNAPRICE_CHAVE_ES256_FILE")),
                relogio,
                EMISSOR_JWT,
                AUDIENCIA_JWT,
            ),
            cifrador=CifradorAesGcm(chaves),
            pseudonimo_ip=pseudonimo_de_ip(chaves),
        )
        return CriarPrimeiroAdministrador(deps).executar(inquilino, email, senha)


def _recalcular(tenant: UUID, identificador: UUID) -> ComparacaoDoRecalculo:
    with abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE"), tamanho_maximo=2) as pool:
        fabrica = FabricaDeUnidadesPostgres(pool, RelogioDoSistema())
        return RecalcularPrecoAlvo(fabrica).executar(tenant, identificador)


def _rotacionar_chave() -> int:
    chaves = carregar_chaves_mestras(caminho_do_segredo("DYNAPRICE_CHAVES_MESTRAS_FILE"))
    with abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE"), tamanho_maximo=2) as pool:
        fabrica = FabricaDeUnidadesPostgres(pool, RelogioDoSistema())
        return RotacionarChaveMestra(fabrica, CifradorAesGcm(chaves)).executar()


def _atualizar_indice(inicio: Competencia, fim: Competencia) -> ResumoDaCargaDoIndice:
    """Roda com a credencial do migrador (DYNAPRICE_DB_URL_FILE): a aplicação não grava o índice."""
    with (
        abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE"), tamanho_maximo=2) as pool,
        httpx.Client(timeout=30, follow_redirects=False) as http,
    ):
        caso = AtualizarIndiceDeInflacao(
            ConectorBcbIpca(http), IndicesDeInflacaoPostgres(pool), "bcb:sgs433"
        )
        return caso.executar(inicio, fim)


def _arquivo_de_ancora() -> AncoraEmArquivo:
    return AncoraEmArquivo(Path(exigir_ambiente("DYNAPRICE_ANCORA_ARQUIVO")))


def _ancorar_auditoria() -> int:
    relogio = RelogioDoSistema()
    with abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE"), tamanho_maximo=2) as pool:
        fabrica = FabricaDeUnidadesPostgres(pool, relogio)
        return AncorarAuditoria(fabrica, _arquivo_de_ancora(), relogio).executar()


def _verificar_auditoria() -> tuple[ResultadoDaVerificacao, ...]:
    with abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE"), tamanho_maximo=2) as pool:
        fabrica = FabricaDeUnidadesPostgres(pool, RelogioDoSistema())
        return VerificarAuditoria(fabrica, _arquivo_de_ancora()).executar()


def _exportar_openapi(saida: Path) -> None:
    from dynaprice.adaptadores.entrada.api.seguranca import Servicos

    exportar_openapi(saida, criar_app(Servicos(None, "")))  # type: ignore[arg-type]


def montar_cli() -> typer.Typer:
    """Compõe a CLI injetando a versão instalada e os grupos de comando."""
    fabricas = FabricasDoLab(sintetico=exportar_sintetico, relatorio=relatorio_do_laboratorio)
    cli = criar_cli(versao=version("dynaprice"), lab=criar_grupo_lab(fabricas))
    registrar_operacao(
        cli,
        FabricasDeOperacao(
            migrar=_migrar,
            criar_admin=_criar_admin,
            recalcular=_recalcular,
            worker=rodar_worker,
            rotacionar_chave=_rotacionar_chave,
            exportar_openapi=_exportar_openapi,
            atualizar_indice=_atualizar_indice,
            ancorar_auditoria=_ancorar_auditoria,
            verificar_auditoria=_verificar_auditoria,
        ),
    )
    return cli
