"""API real sobre banco real, montada pelo Composition Root."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.seguranca import ChavesEs256, HashDeSenhaArgon2
from dynaprice.principal import ConfiguracaoDaApi, criar_api
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.fakes import RelogioFixo


def chaves_de_teste() -> ChavesEs256:
    privada = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return ChavesEs256("k1", privada.decode())


@pytest.fixture
def relogio() -> RelogioFixo:
    return RelogioFixo()


@pytest.fixture
def configuracao(pool: ConnectionPool, relogio: RelogioFixo) -> ConfiguracaoDaApi:
    return ConfiguracaoDaApi(
        pool=pool,
        relogio=relogio,
        chaves=chaves_de_teste(),
        chaves_mestras={"k1": bytes(range(32))},
        hash_de_senha=HashDeSenhaArgon2(tempo=1, memoria_kib=1024, paralelismo=1),
        origem_permitida="https://dynaprice.teste",
    )


@pytest.fixture
def cliente(configuracao: ConfiguracaoDaApi) -> Iterator[TestClient]:
    with TestClient(
        criar_api(configuracao), base_url="https://dynaprice.teste", raise_server_exceptions=False
    ) as aberto:
        yield aberto


@pytest.fixture
def preco(cliente: TestClient, novo_tenant: UUID, banco: object) -> CenarioDePreco:
    auth = cliente.app.state.servicos.auth  # type: ignore[attr-defined]
    return CenarioDePreco(auth.fabrica, auth.relogio, novo_tenant, banco)  # type: ignore[arg-type]
