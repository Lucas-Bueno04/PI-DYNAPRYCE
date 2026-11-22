"""Fixtures compartilhadas: carteira sintética e banco real em contêiner (postgres:18.6)."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg_pool import ConnectionPool
from testcontainers.community.postgres import PostgresContainer

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres, abrir_pool
from dynaprice.adaptadores.saida.postgres.migracoes import migrar
from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.dominio.modelos import Carteira, Competencia
from tests.fakes import RelogioFixo

PAPEIS = Path(__file__).resolve().parents[2] / "deploy" / "compose" / "init" / "papeis.sql.in"
INICIO = Competencia(2025, 1)
FIM = Competencia(2025, 12)
SENHA_MIGRADOR = "senha-de-teste-migrador"
SENHA_APP = "senha-de-teste-app"


@dataclass(frozen=True, slots=True)
class Banco:
    superusuario: str
    migrador: str
    app: str
    conteiner: PostgresContainer


def _url(base: str, usuario: str, senha: str, banco: str) -> str:
    return f"postgresql://{usuario}:{senha}@{base}/{banco}"


def _provisionar(url_super: str) -> None:
    sql = PAPEIS.read_text(encoding="utf-8")
    sql = sql.replace(":'migrador'", f"'{SENHA_MIGRADOR}'").replace(":'app'", f"'{SENHA_APP}'")
    with psycopg.connect(url_super, autocommit=True) as conexao:
        for comando in filter(str.strip, sql.split(";\n")):
            conexao.execute(comando.encode())


@pytest.fixture(scope="session")
def banco() -> Iterator[Banco]:
    with PostgresContainer("postgres:18.6", driver=None) as pg:
        base = f"{pg.get_container_host_ip()}:{pg.get_exposed_port(5432)}"
        url_inicial = _url(base, pg.username, pg.password, pg.dbname)
        _provisionar(url_inicial)
        urls = Banco(
            superusuario=_url(base, pg.username, pg.password, "dynaprice"),
            migrador=_url(base, "dynaprice_migrador", SENHA_MIGRADOR, "dynaprice"),
            app=_url(base, "dynaprice_app", SENHA_APP, "dynaprice"),
            conteiner=pg,
        )
        migrar(urls.migrador)
        yield urls


@pytest.fixture
def novo_tenant(banco: Banco) -> UUID:
    """Um inquilino novo por teste: os testes não dependem de limpeza entre si."""
    tenant = uuid4()
    with psycopg.connect(banco.superusuario, autocommit=True) as conexao:
        conexao.execute("INSERT INTO core.tenant (id, nome) VALUES (%s, %s)", (tenant, "teste"))
    return tenant


@pytest.fixture(scope="session")
def pool(banco: Banco) -> Iterator[ConnectionPool]:
    with abrir_pool(banco.app, tamanho_maximo=8) as aberto:
        yield aberto


@pytest.fixture(scope="session")
def fabrica(pool: ConnectionPool) -> FabricaDeUnidadesPostgres:
    return FabricaDeUnidadesPostgres(pool, RelogioFixo())


@pytest.fixture(scope="session")
def carteira() -> Carteira:
    return GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=42)).extrair(INICIO, FIM)
