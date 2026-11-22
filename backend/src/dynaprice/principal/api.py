"""Composição da API."""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.entrada.api.aplicacao import criar_app
from dynaprice.adaptadores.entrada.api.logs import configurar_logs
from dynaprice.adaptadores.entrada.api.rotas.casos import CasosDeUso
from dynaprice.adaptadores.entrada.api.seguranca import Servicos
from dynaprice.adaptadores.saida.oidc import ProvedorOidcHttp, descobrir_configuracao
from dynaprice.adaptadores.saida.planilha import Pseudonimizador
from dynaprice.adaptadores.saida.planilha.upload import LeitorDeArquivoEnviado, LimitesDeUpload
from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres, abrir_pool
from dynaprice.adaptadores.saida.relogio import RelogioDoSistema
from dynaprice.adaptadores.saida.seguranca import (
    ChavesEs256,
    CifradorAesGcm,
    EmissorJwtEs256,
    HashDeSenhaArgon2,
    VerificadorTotpPyotp,
    carregar_chaves_es256,
    carregar_chaves_mestras,
)
from dynaprice.aplicacao.casos_de_uso import autenticacao
from dynaprice.aplicacao.casos_de_uso.carteira import ConsultarPainel, ListarClientes
from dynaprice.aplicacao.casos_de_uso.conciliar import TratarDivergencia
from dynaprice.aplicacao.casos_de_uso.conectores import (
    ConfigurarConector,
    ListarConectores,
    TestarConector,
)
from dynaprice.aplicacao.casos_de_uso.consultas import (
    BaixarLote,
    ListarAlertas,
    ListarDivergencias,
    ListarPoliticas,
    ListarRecomendacoes,
    SimularRascunho,
)
from dynaprice.aplicacao.casos_de_uso.cotar import CotarServico, ReproduzirCotacao
from dynaprice.aplicacao.casos_de_uso.decidir import DecidirRecomendacao
from dynaprice.aplicacao.casos_de_uso.diagnostico import ConsultarDiagnostico
from dynaprice.aplicacao.casos_de_uso.exportar import SolicitarExportacao, TentarExportarDeNovo
from dynaprice.aplicacao.casos_de_uso.importar import ImportarPlanilha
from dynaprice.aplicacao.casos_de_uso.politicas import CriarRascunhoDePolitica, PublicarPolitica
from dynaprice.aplicacao.casos_de_uso.provisorios import ProvisoriosAbaixoDoEsforco
from dynaprice.aplicacao.casos_de_uso.vincular import CriarVinculo, ListarPendencias
from dynaprice.aplicacao.politica_em_memoria import PoliticaEmMemoria
from dynaprice.aplicacao.portas import HashDeSenha, Relogio
from dynaprice.aplicacao.portas.oidc import ProvedorOidc
from dynaprice.dominio.estimacao.anual import SimuladorDaCarteira
from dynaprice.dominio.estimacao.diagnostico import AnalisadorDoLaboratorio
from dynaprice.principal.comum import (
    caminho_do_segredo,
    exigir_ambiente,
    ler_segredo,
    pseudonimo_de_ip,
)
from dynaprice.principal.fontes import fontes_de_dados

EMISSOR_JWT = "dynaprice"
AUDIENCIA_JWT = "dynaprice-api"


@dataclass(frozen=True, slots=True)
class ConfiguracaoDaApi:
    pool: ConnectionPool[Any]
    relogio: Relogio
    chaves: ChavesEs256
    chaves_mestras: Mapping[str, bytes]
    origem_permitida: str
    hash_de_senha: HashDeSenha
    chave_pseudonimo: bytes = b"somente-para-testes-16"
    provedor_oidc: ProvedorOidc | None = None


def provedor_oidc_do_ambiente(origem: str, relogio: Relogio) -> ProvedorOidc | None:
    """Federação só liga com DYNAPRICE_OIDC_EMISSOR; o segredo do cliente vem de arquivo."""
    emissor = os.environ.get("DYNAPRICE_OIDC_EMISSOR")
    if not emissor:
        return None
    http = httpx.Client(timeout=10, follow_redirects=False)
    config = descobrir_configuracao(
        http,
        emissor,
        exigir_ambiente("DYNAPRICE_OIDC_CLIENTE_ID"),
        ler_segredo("DYNAPRICE_OIDC_SEGREDO_FILE"),
        f"{origem}/api/v1/auth/oidc/retorno",
    )
    return ProvedorOidcHttp(config, http, relogio)


def configuracao_do_ambiente() -> ConfiguracaoDaApi:
    relogio = RelogioDoSistema()
    origem = exigir_ambiente("DYNAPRICE_ORIGEM")
    return ConfiguracaoDaApi(
        pool=abrir_pool(ler_segredo("DYNAPRICE_DB_URL_FILE")),
        relogio=relogio,
        chaves=carregar_chaves_es256(caminho_do_segredo("DYNAPRICE_CHAVE_ES256_FILE")),
        chaves_mestras=carregar_chaves_mestras(caminho_do_segredo("DYNAPRICE_CHAVES_MESTRAS_FILE")),
        origem_permitida=origem,
        hash_de_senha=HashDeSenhaArgon2(),
        chave_pseudonimo=ler_segredo("DYNAPRICE_CHAVE_PSEUDONIMO_FILE").encode(),
        provedor_oidc=provedor_oidc_do_ambiente(origem, relogio),
    )


def montar_autenticacao(config: ConfiguracaoDaApi) -> autenticacao.DependenciasDeAutenticacao:
    return autenticacao.DependenciasDeAutenticacao(
        fabrica=FabricaDeUnidadesPostgres(config.pool, config.relogio),
        relogio=config.relogio,
        hash_de_senha=config.hash_de_senha,
        totp=VerificadorTotpPyotp(),
        emissor=EmissorJwtEs256(config.chaves, config.relogio, EMISSOR_JWT, AUDIENCIA_JWT),
        cifrador=CifradorAesGcm(config.chaves_mestras),
        pseudonimo_ip=pseudonimo_de_ip(config.chaves_mestras),
    )


def montar_casos(
    config: ConfiguracaoDaApi, auth: autenticacao.DependenciasDeAutenticacao
) -> CasosDeUso:
    fabrica, relogio = auth.fabrica, auth.relogio
    memoria = PoliticaEmMemoria()
    leitor = LeitorDeArquivoEnviado(Pseudonimizador(config.chave_pseudonimo), LimitesDeUpload())
    return CasosDeUso(
        listar_recomendacoes=ListarRecomendacoes(fabrica),
        decidir=DecidirRecomendacao(fabrica, relogio),
        solicitar_exportacao=SolicitarExportacao(fabrica, relogio),
        tentar_exportar=TentarExportarDeNovo(fabrica, relogio),
        baixar_lote=BaixarLote(fabrica),
        listar_politicas=ListarPoliticas(fabrica),
        criar_rascunho=CriarRascunhoDePolitica(fabrica),
        publicar=PublicarPolitica(fabrica, relogio),
        listar_divergencias=ListarDivergencias(fabrica),
        tratar_divergencia=TratarDivergencia(fabrica),
        criar_vinculo=CriarVinculo(fabrica),
        listar_pendencias=ListarPendencias(fabrica),
        importar=ImportarPlanilha(fabrica, relogio, leitor),
        configurar_conector=ConfigurarConector(fabrica, auth.cifrador),
        listar_conectores=ListarConectores(fabrica),
        testar_conector=TestarConector(
            fabrica, relogio, auth.cifrador, fontes_de_dados(config.chave_pseudonimo)
        ),
        listar_alertas=ListarAlertas(fabrica),
        diagnostico=ConsultarDiagnostico(fabrica, AnalisadorDoLaboratorio()),
        simular=SimularRascunho(fabrica, SimuladorDaCarteira()),
        cotar=CotarServico(fabrica, relogio, memoria),
        reproduzir_cotacao=ReproduzirCotacao(fabrica),
        provisorios=ProvisoriosAbaixoDoEsforco(fabrica),
        listar_clientes=ListarClientes(fabrica),
        painel=ConsultarPainel(fabrica),
    )


def criar_api(config: ConfiguracaoDaApi | None = None) -> FastAPI:
    """Fábrica usada pelo uvicorn (`--factory`) e pelos testes."""
    if config is None:
        configurar_logs()
    configuracao = config or configuracao_do_ambiente()
    auth = montar_autenticacao(configuracao)
    casos = montar_casos(configuracao, auth)
    return criar_app(
        Servicos(auth, configuracao.origem_permitida, casos, configuracao.provedor_oidc)
    )


def exportar_openapi(saida: Path, app: FastAPI) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
