"""F3.2: entrada por OIDC cai na mesma etapa de MFA da senha; conta nunca é criada pelo IdP."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.autenticacao import ConcluirMfa, ResultadoDeEntrada
from dynaprice.aplicacao.casos_de_uso.autenticacao.federacao import (
    ConcluirFederacao,
    IniciarFederacao,
)
from dynaprice.aplicacao.erros import NaoAutenticado
from dynaprice.aplicacao.portas import TokenInvalido
from dynaprice.aplicacao.portas.oidc import IdentidadeFederada
from dynaprice.dominio.modelos.autenticacao import Papel, Usuario
from tests.aplicacao.test_autenticar import IP, Cenario
from tests.aplicacao.test_autenticar import cenario as cenario


@dataclass
class ProvedorFalso:
    email: str = ""
    verificado: bool = True
    recusa: bool = False
    chamadas: list[tuple[str, str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.chamadas = []

    def url_de_autorizacao(self, state: str, nonce: str, desafio_pkce: str) -> str:
        return f"https://idp.teste/authorize?state={state}&nonce={nonce}&cc={desafio_pkce}"

    def identidade(self, codigo: str, verificador_pkce: str, nonce: str) -> IdentidadeFederada:
        self.chamadas.append((codigo, verificador_pkce, nonce))
        if self.recusa:
            raise TokenInvalido("recusado")
        return IdentidadeFederada("idp|1", self.email, self.verificado)


def _fluxo(
    cenario: Cenario, provedor: ProvedorFalso, state: str | None = None
) -> ResultadoDeEntrada:
    inicio = IniciarFederacao(cenario.deps, provedor).executar()
    estado = cenario.deps.emissor.verificar_estado_de_federacao(inicio.estado)
    return ConcluirFederacao(cenario.deps, provedor).executar(
        "codigo", state or estado.state, inicio.estado, IP
    )


def test_inicio_gera_url_com_state_nonce_e_pkce_e_estado_assinado(cenario: Cenario) -> None:
    inicio = IniciarFederacao(cenario.deps, ProvedorFalso()).executar()
    estado = cenario.deps.emissor.verificar_estado_de_federacao(inicio.estado)
    assert f"state={estado.state}" in inicio.url and f"nonce={estado.nonce}" in inicio.url
    assert len({estado.state, estado.nonce, estado.verificador_pkce}) == 3
    assert len(estado.verificador_pkce) >= 43
    outro = IniciarFederacao(cenario.deps, ProvedorFalso()).executar()
    assert cenario.deps.emissor.verificar_estado_de_federacao(outro.estado).state != estado.state


def test_analista_entra_sem_senha_e_o_provedor_recebe_verificador_e_nonce(
    cenario: Cenario,
) -> None:
    usuario, _ = cenario.criar_usuario()
    provedor = ProvedorFalso(email=usuario.email)
    resultado = _fluxo(cenario, provedor)
    assert resultado.tokens is not None and resultado.desafio is None
    principal = cenario.deps.emissor.verificar(resultado.tokens.acesso)
    assert (principal.usuario_id, principal.tenant_id) == (usuario.id, cenario.tenant)
    assert principal.mfa_verificado is False
    (codigo, verificador, nonce) = provedor.chamadas[0]
    assert codigo == "codigo" and len(verificador) >= 43 and nonce
    assert ("login_federado",) in cenario.consulta(
        "SELECT tipo FROM audit.evento WHERE usuario_id = %s", usuario.id
    )


def test_email_do_idp_casa_sem_diferenciar_caixa(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    resultado = _fluxo(cenario, ProvedorFalso(email=usuario.email.upper().lower()))
    assert resultado.tokens is not None


def test_com_mfa_ativo_devolve_desafio_e_o_totp_conclui(cenario: Cenario) -> None:
    usuario, segredo = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    resultado = _fluxo(cenario, ProvedorFalso(email=usuario.email))
    assert resultado.tokens is None and resultado.desafio
    tokens = ConcluirMfa(cenario.deps).executar(
        resultado.desafio,
        cenario.codigo(segredo),
        IP,
    )
    assert cenario.deps.emissor.verificar(tokens.acesso).mfa_verificado is True


def test_aprovador_sem_mfa_precisa_cadastrar(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.APROVAR}))
    resultado = _fluxo(cenario, ProvedorFalso(email=usuario.email))
    assert resultado.desafio and resultado.cadastro_mfa_requerido
    assert resultado.tokens is None


@pytest.mark.parametrize(
    "provedor",
    [
        ProvedorFalso(email="desconhecido@teste.com"),  # o IdP não cria conta
        ProvedorFalso(email="", verificado=True),
        ProvedorFalso(email="x@teste.com", verificado=False),
        ProvedorFalso(recusa=True),
    ],
)
def test_identidade_recusada(cenario: Cenario, provedor: ProvedorFalso) -> None:
    with pytest.raises(NaoAutenticado):
        _fluxo(cenario, provedor)


def test_email_nao_verificado_de_conta_existente_e_recusado(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with pytest.raises(NaoAutenticado):
        _fluxo(cenario, ProvedorFalso(email=usuario.email, verificado=False))


def test_usuario_inativo_e_recusado(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.desativar(usuario.id)
    with pytest.raises(NaoAutenticado):
        _fluxo(cenario, ProvedorFalso(email=usuario.email))


def test_state_diferente_do_cookie_e_recusado_sem_chamar_o_idp(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    provedor = ProvedorFalso(email=usuario.email)
    with pytest.raises(NaoAutenticado):
        _fluxo(cenario, provedor, state="forjado")
    assert provedor.chamadas == []


def test_estado_adulterado_ou_de_outro_tipo_e_recusado(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    provedor = ProvedorFalso(email=usuario.email)
    acesso = cenario.entrar(usuario).acesso
    for estado in ("lixo", acesso):
        with pytest.raises(NaoAutenticado):
            ConcluirFederacao(cenario.deps, provedor).executar("c", "s", estado, IP)
    assert provedor.chamadas == []


def test_usuario_sem_inquilino_nao_abre_sessao(cenario: Cenario) -> None:
    sem_acesso = Usuario(
        uuid4(), f"{uuid4()}@teste.com", cenario.deps.hash_de_senha.gerar("x" * 12)
    )
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.criar(sem_acesso)
    resultado = _fluxo(cenario, ProvedorFalso(email=sem_acesso.email))
    assert resultado.tokens is None and resultado.desafio is None
