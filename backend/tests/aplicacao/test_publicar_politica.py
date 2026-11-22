"""F1.21: política como dado, publicação com aprovar + TOTP, imutabilidade no banco."""

from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg.errors import IntegrityConstraintViolation

from dynaprice.aplicacao.casos_de_uso.politicas import CriarRascunhoDePolitica, PublicarPolitica
from dynaprice.aplicacao.erros import AcessoNegado, Conflito
from dynaprice.dominio.modelos import ValorInvalido
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco
from tests.dominio.modelos.documentos import documento_tabela_7


def _publicar(preco: CenarioDePreco) -> PublicarPolitica:
    return PublicarPolitica(preco.fabrica, preco.relogio)


def _rascunho(preco: CenarioDePreco, documento: dict[str, Any] | None = None) -> int:
    return CriarRascunhoDePolitica(preco.fabrica).executar(
        preco.aprovador, documento or documento_tabela_7()
    )


def test_rascunho_valida_o_documento(preco: CenarioDePreco) -> None:
    documento = documento_tabela_7()
    del documento["kappa_maximo"]
    with pytest.raises(ValorInvalido):
        _rascunho(preco, documento)


def test_rascunho_numera_as_versoes(preco: CenarioDePreco) -> None:
    assert [_rascunho(preco), _rascunho(preco)] == [1, 2]


def test_versao_do_documento_e_a_da_tabela(preco: CenarioDePreco) -> None:
    _rascunho(preco)
    segunda = _rascunho(preco)
    _publicar(preco).executar(preco.aprovador, segunda)
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        publicada = uow.politicas.publicada()
    assert publicada is not None
    assert publicada.versao == 2


def test_publicar_substitui_a_anterior(preco: CenarioDePreco) -> None:
    primeira, segunda = _rascunho(preco), _rascunho(preco)
    _publicar(preco).executar(preco.aprovador, primeira)
    _publicar(preco).executar(preco.aprovador, segunda)
    assert preco.consulta(
        "SELECT versao, estado FROM core.politica_versao WHERE tenant_id = %s ORDER BY versao",
        preco.tenant,
    ) == [(1, "substituida"), (2, "publicada")]


@pytest.mark.parametrize(
    "principal",
    [
        Principal(uuid4(), uuid4(), frozenset({Papel.APROVAR}), mfa_verificado=False),
        Principal(uuid4(), uuid4(), frozenset({Papel.ANALISAR}), mfa_verificado=True),
    ],
)
def test_publicar_exige_aprovar_com_totp(preco: CenarioDePreco, principal: Principal) -> None:
    with pytest.raises(AcessoNegado):
        _publicar(preco).executar(principal, 1)


def test_publicar_e_auditado(preco: CenarioDePreco) -> None:
    aprovador = preco.aprovador
    _publicar(preco).executar(aprovador, _rascunho(preco))
    assert preco.consulta(
        "SELECT tipo, usuario_id FROM audit.evento WHERE tenant_id = %s AND tipo = %s",
        preco.tenant,
        "politica_publicada",
    ) == [("politica_publicada", aprovador.usuario_id)]


def test_publicada_nao_republica(preco: CenarioDePreco) -> None:
    versao = _rascunho(preco)
    _publicar(preco).executar(preco.aprovador, versao)
    with pytest.raises(Conflito):
        _publicar(preco).executar(preco.aprovador, versao)


def test_portao_de_aceite_reprovado_nao_publica(preco: CenarioDePreco) -> None:
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        versao = uow.politicas.salvar_rascunho(documento_tabela_7(), portao_aceite=False)
    with pytest.raises(Conflito):
        _publicar(preco).executar(preco.aprovador, versao)


def test_update_em_publicada_falha_no_banco(preco: CenarioDePreco) -> None:
    versao = _rascunho(preco)
    _publicar(preco).executar(preco.aprovador, versao)
    with (
        psycopg.connect(preco.banco.superusuario) as s,
        pytest.raises(IntegrityConstraintViolation),
    ):
        s.execute(
            """UPDATE core.politica_versao SET documento = '{"x": 1}'
               WHERE tenant_id = %s AND versao = %s""",
            (preco.tenant, versao),
        )
