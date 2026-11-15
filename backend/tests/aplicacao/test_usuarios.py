"""F1.19: usuários, papéis por inquilino e primeiro administrador."""

from uuid import UUID, uuid4

import psycopg
import pytest

from dynaprice.aplicacao.casos_de_uso.autenticacao import Entrar, RenovarSessao
from dynaprice.aplicacao.casos_de_uso.usuarios import (
    CriarPrimeiroAdministrador,
    CriarUsuario,
    DefinirPapeis,
    DesativarUsuario,
    ListarUsuarios,
)
from dynaprice.aplicacao.erros import AcessoNegado, Conflito, NaoAutenticado, NaoEncontrado
from dynaprice.dominio.modelos import ValorInvalido
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.aplicacao.test_autenticar import SENHA, Cenario, _ip_unico
from tests.aplicacao.test_autenticar import cenario as cenario
from tests.conftest import Banco

ANALISTA = frozenset({Papel.ANALISAR})


def _admin(tenant: UUID) -> Principal:
    return Principal(uuid4(), tenant, frozenset({Papel.ADMINISTRAR}), mfa_verificado=True)


def test_criar_usuario_no_inquilino_do_administrador(cenario: Cenario) -> None:
    email = f"{uuid4()}@teste.com"
    usuario_id = CriarUsuario(cenario.deps).executar(_admin(cenario.tenant), email, SENHA, ANALISTA)
    usuarios = ListarUsuarios(cenario.deps).executar(_admin(cenario.tenant))
    assert [(u.id, p) for u, p in usuarios if u.id == usuario_id] == [(usuario_id, ANALISTA)]


def test_analista_nao_gerencia_usuarios(cenario: Cenario) -> None:
    analista = Principal(uuid4(), cenario.tenant, ANALISTA, mfa_verificado=True)
    with pytest.raises(AcessoNegado):
        CriarUsuario(cenario.deps).executar(analista, "x@y.z", SENHA, ANALISTA)


def test_administrador_sem_mfa_nao_gerencia_usuarios(cenario: Cenario) -> None:
    admin = Principal(uuid4(), cenario.tenant, frozenset({Papel.ADMINISTRAR}), False)
    with pytest.raises(AcessoNegado):
        ListarUsuarios(cenario.deps).executar(admin)


def test_email_repetido_e_recusado(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with pytest.raises(Conflito):
        CriarUsuario(cenario.deps).executar(
            _admin(cenario.tenant), usuario.email.upper(), SENHA, ANALISTA
        )


def test_senha_curta_e_recusada(cenario: Cenario) -> None:
    with pytest.raises(ValorInvalido):
        CriarUsuario(cenario.deps).executar(_admin(cenario.tenant), "a@b.c", "curta", ANALISTA)


def test_administrador_nao_mexe_em_usuario_de_outro_inquilino(
    cenario: Cenario, banco: Banco
) -> None:
    usuario, _ = cenario.criar_usuario()
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        linha = s.execute("INSERT INTO core.tenant (nome) VALUES ('B') RETURNING id").fetchone()
    assert linha is not None
    with pytest.raises(NaoEncontrado):
        DefinirPapeis(cenario.deps).executar(_admin(linha[0]), usuario.id, ANALISTA)
    with pytest.raises(NaoEncontrado):
        DesativarUsuario(cenario.deps).executar(_admin(linha[0]), usuario.id)


def test_mudar_papeis_derruba_as_sessoes(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    refresh = cenario.entrar(usuario, _ip_unico()).refresh
    DefinirPapeis(cenario.deps).executar(
        _admin(cenario.tenant), usuario.id, frozenset({Papel.ANALISAR, Papel.APROVAR})
    )
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(refresh)


def test_desativar_impede_login_e_derruba_sessoes(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    refresh = cenario.entrar(usuario, _ip_unico()).refresh
    DesativarUsuario(cenario.deps).executar(_admin(cenario.tenant), usuario.id)
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(refresh)
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())


def test_administrador_novo_precisa_cadastrar_mfa(cenario: Cenario, banco: Banco) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.ADMINISTRAR}))
    resultado = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert resultado.cadastro_mfa_requerido is True


def test_criar_admin_so_com_banco_sem_administrador(cenario: Cenario, banco: Banco) -> None:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute("DELETE FROM auth.usuario_papel WHERE papel = 'administrar'")
    email = f"{uuid4()}@teste.com"
    tenant = CriarPrimeiroAdministrador(cenario.deps).executar("Escritório", email, SENHA)
    with psycopg.connect(banco.superusuario) as s:
        linha = s.execute(
            "SELECT count(*) FROM auth.usuario_papel "
            "WHERE tenant_id = %s AND papel = 'administrar'",
            (tenant,),
        ).fetchone()
        eventos = s.execute(
            "SELECT tipo FROM audit.evento WHERE tenant_id = %s", (tenant,)
        ).fetchall()
    assert linha == (1,)
    assert eventos == [("administrador_criado",)]
    with pytest.raises(Conflito):
        CriarPrimeiroAdministrador(cenario.deps).executar("Outro", f"{uuid4()}@t.com", SENHA)


def test_m1_desativar_so_afeta_o_inquilino_do_administrador(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    outro = cenario.novo_inquilino()
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.definir_papeis(usuario.id, outro, ANALISTA)
    DesativarUsuario(cenario.deps).executar(_admin(cenario.tenant), usuario.id)
    assert cenario.consulta("SELECT ativo FROM auth.usuario WHERE id=%s", usuario.id) == [(True,)]
    with cenario.fabrica.sem_tenant() as uow:
        assert uow.usuarios.inquilinos(usuario.id) == [outro]


def test_m1_mudar_papeis_nao_derruba_sessao_de_outro_inquilino(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    outro = cenario.novo_inquilino()
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.definir_papeis(usuario.id, outro, ANALISTA)
        sessao = uow.sessoes.criar_familia(
            usuario.id, outro, False, cenario.relogio.agora(), cenario.relogio.agora()
        )
    DefinirPapeis(cenario.deps).executar(
        _admin(cenario.tenant), usuario.id, frozenset({Papel.APROVAR})
    )
    assert cenario.consulta("SELECT revogada_em FROM auth.sessao_familia WHERE id=%s", sessao) == [
        (None,)
    ]
