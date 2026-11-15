"""F1.19: recuperação de senha e de MFA revoga todas as sessões (ADR-002)."""

from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.autenticacao import (
    CadastrarMfa,
    ConfirmarMfa,
    Entrar,
    RenovarSessao,
)
from dynaprice.aplicacao.casos_de_uso.recuperar_acesso import (
    GerarRedefinicao,
    RecuperarMfa,
    RedefinirSenha,
)
from dynaprice.aplicacao.erros import (
    AcessoNegado,
    MuitasTentativas,
    NaoAutenticado,
    NaoEncontrado,
)
from dynaprice.aplicacao.portas import HashDeSenha
from dynaprice.dominio.modelos.autenticacao import Papel, Principal, Usuario
from tests.aplicacao.test_autenticar import SENHA, Cenario, _ip_unico
from tests.aplicacao.test_autenticar import cenario as cenario

NOVA = "outra-senha-bem-longa"


def _admin(tenant: UUID) -> Principal:
    return Principal(uuid4(), tenant, frozenset({Papel.ADMINISTRAR}), mfa_verificado=True)


def _link(cenario: Cenario, usuario: Usuario) -> str:
    return GerarRedefinicao(cenario.deps).executar(_admin(cenario.tenant), usuario.id)


def test_redefinicao_troca_a_senha_e_revoga_sessoes(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    refresh = cenario.entrar(usuario, _ip_unico()).refresh
    RedefinirSenha(cenario.deps).executar(_link(cenario, usuario), NOVA)
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(refresh)
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert Entrar(cenario.deps).executar(usuario.email, NOVA, _ip_unico()).tokens is not None


def test_redefinicao_e_auditada(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    RedefinirSenha(cenario.deps).executar(_link(cenario, usuario), NOVA)
    assert ("senha_redefinida",) in cenario.consulta(
        "SELECT tipo FROM audit.evento WHERE usuario_id = %s", usuario.id
    )


def test_link_e_de_uso_unico(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    link = _link(cenario, usuario)
    RedefinirSenha(cenario.deps).executar(link, NOVA)
    with pytest.raises(NaoAutenticado):
        RedefinirSenha(cenario.deps).executar(link, "mais-uma-senha-longa")


def test_link_expira_em_trinta_minutos(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    link = _link(cenario, usuario)
    cenario.relogio.avancar(30 * 60 + 1)
    with pytest.raises(NaoAutenticado):
        RedefinirSenha(cenario.deps).executar(link, NOVA)


def test_link_invalido_e_recusado(cenario: Cenario) -> None:
    with pytest.raises(NaoAutenticado):
        RedefinirSenha(cenario.deps).executar("nao-existe", NOVA)


def test_link_nao_e_guardado_em_claro(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    link = _link(cenario, usuario)
    linhas = cenario.consulta(
        "SELECT hash_sha256 FROM auth.redefinicao_senha WHERE usuario_id = %s", usuario.id
    )
    assert link.encode() not in cast(bytes, linhas[0][0])


def test_administrador_nao_gera_link_para_outro_inquilino(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with pytest.raises(NaoEncontrado):
        GerarRedefinicao(cenario.deps).executar(_admin(uuid4()), usuario.id)


def _com_mfa(cenario: Cenario) -> tuple[Usuario, tuple[str, ...], str]:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.APROVAR}))
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    cadastro = CadastrarMfa(cenario.deps).executar(desafio)
    confirmado = ConfirmarMfa(cenario.deps).executar(desafio, cenario.codigo(cadastro.segredo))
    return usuario, confirmado.codigos_de_recuperacao, confirmado.tokens.refresh


def test_recuperar_mfa_desliga_e_revoga_sessoes(cenario: Cenario) -> None:
    usuario, codigos, refresh = _com_mfa(cenario)
    RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, codigos[0], _ip_unico())
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(refresh)
    resultado = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert resultado.cadastro_mfa_requerido is True


def test_codigo_de_recuperacao_e_de_uso_unico(cenario: Cenario) -> None:
    usuario, codigos, _ = _com_mfa(cenario)
    RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, codigos[0], _ip_unico())
    with pytest.raises(NaoAutenticado):
        RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, codigos[0], _ip_unico())


def test_recuperar_mfa_exige_senha_e_codigo(cenario: Cenario) -> None:
    usuario, codigos, _ = _com_mfa(cenario)
    with pytest.raises(NaoAutenticado):
        RecuperarMfa(cenario.deps).executar(usuario.email, "errada", codigos[0], _ip_unico())
    with pytest.raises(NaoAutenticado):
        RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, "codigo-errado", _ip_unico())


# --- Achados da revisão de segurança F1.20 ---------------------------------------------------


class _Contador:
    def __init__(self, base: object) -> None:
        self._base = base
        self.verificacoes = 0

    def __getattr__(self, nome: str) -> object:
        return getattr(self._base, nome)

    def verificar(self, guardado: str, senha: str) -> bool:
        self.verificacoes += 1
        return bool(self._base.verificar(guardado, senha))  # type: ignore[attr-defined]

    def simular_verificacao(self, senha: str) -> None:
        self.verificacoes += 1
        self._base.simular_verificacao(senha)  # type: ignore[attr-defined]


def _custo(cenario: Cenario, email: str, senha: str, codigo: str) -> int:
    contador = _Contador(cenario.deps.hash_de_senha)
    deps = replace(cenario.deps, hash_de_senha=cast(HashDeSenha, contador))
    with pytest.raises(NaoAutenticado):
        RecuperarMfa(deps).executar(email, senha, codigo, _ip_unico())
    return contador.verificacoes


def test_a3_custo_nao_revela_senha_nem_existencia(cenario: Cenario) -> None:
    usuario, codigos, _ = _com_mfa(cenario)
    invalido = f"{uuid4().hex}.0000000000000000"
    custos = {
        _custo(cenario, "nao@existe.com", SENHA, codigos[0]),
        _custo(cenario, usuario.email, "errada", codigos[0]),
        _custo(cenario, usuario.email, SENHA, invalido),
        _custo(cenario, usuario.email, SENHA, "sem-formato"),
    }
    assert custos == {2}


def test_a3_recuperar_mfa_conta_falhas_e_bloqueia(cenario: Cenario) -> None:
    usuario, codigos, _ = _com_mfa(cenario)
    for _ in range(5):
        with pytest.raises(NaoAutenticado):
            RecuperarMfa(cenario.deps).executar(usuario.email, "errada", codigos[0], _ip_unico())
    with pytest.raises(MuitasTentativas):
        RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, codigos[0], _ip_unico())


def test_a3_recuperar_mfa_bloqueia_por_ip(cenario: Cenario) -> None:
    usuario, codigos, _ = _com_mfa(cenario)
    ip = _ip_unico()
    for _ in range(cenario.deps.parametros.falhas_antes_do_bloqueio_ip):
        with pytest.raises(NaoAutenticado):
            RecuperarMfa(cenario.deps).executar(f"{uuid4()}@t.com", "errada", codigos[0], ip)
    with pytest.raises(MuitasTentativas):
        RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, codigos[0], ip)


def test_a3_usuario_inativo_nao_recupera(cenario: Cenario) -> None:
    usuario, codigos, _ = _com_mfa(cenario)
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.desativar(usuario.id)
    with pytest.raises(NaoAutenticado):
        RecuperarMfa(cenario.deps).executar(usuario.email, SENHA, codigos[0], _ip_unico())


def test_m1_nao_redefine_quem_tem_papel_em_outro_inquilino(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    outro = cenario.novo_inquilino()
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.definir_papeis(usuario.id, outro, frozenset({Papel.ANALISAR}))
    with pytest.raises(AcessoNegado):
        GerarRedefinicao(cenario.deps).executar(_admin(cenario.tenant), usuario.id)


def test_b5_link_novo_invalida_o_anterior(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    antigo = _link(cenario, usuario)
    novo = _link(cenario, usuario)
    with pytest.raises(NaoAutenticado):
        RedefinirSenha(cenario.deps).executar(antigo, NOVA)
    RedefinirSenha(cenario.deps).executar(novo, NOVA)
