"""F1.17: login, MFA e sessões (ADR-002), com a simulação mw9kw9i514upw:13."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import cast
from uuid import UUID, uuid4

import psycopg
import pyotp
import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from dynaprice.adaptadores.saida.seguranca import (
    CifradorAesGcm,
    EmissorJwtEs256,
    HashDeSenhaArgon2,
    VerificadorTotpPyotp,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao import (
    CadastrarMfa,
    ConcluirMfa,
    ConfirmarMfa,
    DependenciasDeAutenticacao,
    Entrar,
    ParDeTokens,
    RenovarSessao,
    Sair,
    TrocarInquilino,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao.base import contexto_totp
from dynaprice.aplicacao.erros import (
    AcessoNegado,
    MuitasTentativas,
    NaoAutenticado,
    RenovacaoConcorrente,
)
from dynaprice.aplicacao.portas import HashDeSenha
from dynaprice.dominio.modelos.autenticacao import (
    Papel,
    ParametrosDeSessao,
    Principal,
    Usuario,
)
from tests.api.conftest import chaves_de_teste
from tests.conftest import Banco
from tests.fakes import RelogioFixo

SENHA = "senha-bem-longa-123"
IP = "203.0.113.7"


@dataclass
class Cenario:
    deps: DependenciasDeAutenticacao
    relogio: RelogioFixo
    fabrica: FabricaDeUnidadesPostgres
    tenant: UUID
    banco: Banco

    def criar_usuario(
        self, papeis: frozenset[Papel] = frozenset({Papel.ANALISAR}), *, mfa: bool = False
    ) -> tuple[Usuario, str]:
        usuario = Usuario(uuid4(), f"{uuid4()}@teste.com", self.deps.hash_de_senha.gerar(SENHA))
        segredo = ""
        if mfa:
            segredo = pyotp.random_base32()
            usuario = replace(
                usuario,
                mfa_ativo=True,
                totp_cifrado=self.deps.cifrador.cifrar(segredo.encode(), contexto_totp(usuario.id)),
            )
        with self.fabrica.sem_tenant() as uow:
            uow.usuarios.criar(usuario)
            uow.usuarios.definir_papeis(usuario.id, self.tenant, papeis)
        return usuario, segredo

    def excluir_usuario(self, usuario_id: UUID) -> None:
        with psycopg.connect(self.banco.superusuario, autocommit=True) as s:
            s.execute("DELETE FROM auth.usuario WHERE id = %s", (usuario_id,))

    def novo_inquilino(self) -> UUID:
        with psycopg.connect(self.banco.superusuario, autocommit=True) as s:
            linha = s.execute("INSERT INTO core.tenant (nome) VALUES ('B') RETURNING id").fetchone()
        assert linha is not None
        tenant: UUID = linha[0]
        return tenant

    def codigo(self, segredo: str) -> str:
        return pyotp.TOTP(segredo).at(self.relogio.agora())

    def entrar(self, usuario: Usuario, ip: str = IP) -> ParDeTokens:
        tokens = Entrar(self.deps).executar(usuario.email, SENHA, ip).tokens
        assert tokens is not None
        return tokens

    def consulta(self, sql: str, *args: object) -> list[tuple[object, ...]]:
        with psycopg.connect(self.banco.superusuario) as s:
            return s.execute(sql.encode(), args).fetchall()


@pytest.fixture
def cenario(pool: ConnectionPool, novo_tenant: UUID, banco: Banco) -> Cenario:
    relogio = RelogioFixo()
    fabrica = FabricaDeUnidadesPostgres(pool, relogio)
    deps = DependenciasDeAutenticacao(
        fabrica=fabrica,
        relogio=relogio,
        hash_de_senha=HashDeSenhaArgon2(tempo=1, memoria_kib=1024, paralelismo=1),
        totp=VerificadorTotpPyotp(),
        emissor=EmissorJwtEs256(chaves_de_teste(), relogio, "dynaprice", "dynaprice-api"),
        cifrador=CifradorAesGcm({"k1": bytes(range(32))}),
        pseudonimo_ip=lambda ip: ip.encode(),
    )
    return Cenario(deps, relogio, fabrica, novo_tenant, banco)


def _ip_unico() -> str:
    return f"ip-{uuid4()}"


def test_analista_entra_sem_mfa(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    principal = cenario.deps.emissor.verificar(cenario.entrar(usuario, _ip_unico()).acesso)
    assert principal.usuario_id == usuario.id
    assert principal.tenant_id == cenario.tenant
    assert principal.papeis == {Papel.ANALISAR}
    assert principal.mfa_verificado is False


def test_senha_errada_e_email_inexistente_tem_o_mesmo_erro(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with pytest.raises(NaoAutenticado) as errada:
        Entrar(cenario.deps).executar(usuario.email, "errada", _ip_unico())
    with pytest.raises(NaoAutenticado) as inexistente:
        Entrar(cenario.deps).executar("nao@existe.com", SENHA, _ip_unico())
    assert str(errada.value) == str(inexistente.value)


def test_usuario_inativo_nao_entra(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.desativar(usuario.id)
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())


def test_bloqueio_progressivo_por_conta(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    for _ in range(5):
        with pytest.raises(NaoAutenticado):
            Entrar(cenario.deps).executar(usuario.email, "errada", _ip_unico())
    # A senha certa não entra durante o bloqueio de 30 s.
    with pytest.raises(MuitasTentativas) as erro:
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert 0 < erro.value.espera_s <= 31
    cenario.relogio.avancar(31)
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(usuario.email, "errada", _ip_unico())
    # A sexta falha dobra a espera.
    with pytest.raises(MuitasTentativas) as erro:
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert 30 < erro.value.espera_s <= 61


def test_bloqueio_por_ip_entre_contas(cenario: Cenario) -> None:
    ip = _ip_unico()
    for _ in range(cenario.deps.parametros.falhas_antes_do_bloqueio_ip):
        with pytest.raises(NaoAutenticado):
            Entrar(cenario.deps).executar(f"{uuid4()}@teste.com", "errada", ip)
    usuario, _ = cenario.criar_usuario()
    with pytest.raises(MuitasTentativas):
        Entrar(cenario.deps).executar(usuario.email, SENHA, ip)


def test_sucesso_zera_as_falhas(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    for _ in range(4):
        with pytest.raises(NaoAutenticado):
            Entrar(cenario.deps).executar(usuario.email, "errada", _ip_unico())
    cenario.entrar(usuario, _ip_unico())
    linhas = cenario.consulta("SELECT falhas_login FROM auth.usuario WHERE id = %s", usuario.id)
    assert linhas == [(0,)]


def test_falha_de_login_e_auditada(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(usuario.email, "errada", _ip_unico())
    linhas = cenario.consulta("SELECT tipo FROM audit.evento WHERE tenant_id = %s", cenario.tenant)
    assert linhas == [("login_falhou",)]


def test_mfa_ativo_exige_codigo(cenario: Cenario) -> None:
    usuario, segredo = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    resultado = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert resultado.tokens is None
    assert resultado.desafio is not None
    tokens = ConcluirMfa(cenario.deps).executar(
        resultado.desafio, cenario.codigo(segredo), _ip_unico()
    )
    assert cenario.deps.emissor.verificar(tokens.acesso).mfa_verificado is True


def test_mesmo_codigo_totp_nao_vale_duas_vezes(cenario: Cenario) -> None:
    usuario, segredo = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    codigo = cenario.codigo(segredo)
    ConcluirMfa(cenario.deps).executar(desafio, codigo, _ip_unico())
    with pytest.raises(NaoAutenticado):
        ConcluirMfa(cenario.deps).executar(desafio, codigo, _ip_unico())


def test_codigo_errado_conta_para_o_bloqueio(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    for _ in range(5):
        with pytest.raises(NaoAutenticado):
            ConcluirMfa(cenario.deps).executar(desafio, "000000", _ip_unico())
    with pytest.raises(MuitasTentativas):
        ConcluirMfa(cenario.deps).executar(desafio, "000000", _ip_unico())


@pytest.mark.parametrize("papel", [Papel.APROVAR, Papel.ADMINISTRAR])
def test_mfa_obrigatorio_para_quem_aprova_ou_administra(cenario: Cenario, papel: Papel) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({papel}))
    resultado = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())
    assert resultado.tokens is None
    assert resultado.cadastro_mfa_requerido is True


def test_cadastro_de_mfa_entrega_dez_codigos(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.APROVAR}))
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    cadastro = CadastrarMfa(cenario.deps).executar(desafio)
    confirmado = ConfirmarMfa(cenario.deps).executar(desafio, cenario.codigo(cadastro.segredo))
    assert len(set(confirmado.codigos_de_recuperacao)) == 10
    assert cenario.deps.emissor.verificar(confirmado.tokens.acesso).mfa_verificado is True


def test_desafio_nao_troca_mfa_ativo(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    with pytest.raises(AcessoNegado):
        CadastrarMfa(cenario.deps).executar(desafio)


class TestSimulacaoReusoDeRefresh:
    """Simulação mw9kw9i514upw:13, passo a passo."""

    def test_cinco_passos(self, cenario: Cenario) -> None:
        usuario, _ = cenario.criar_usuario()
        # Passo 1: sessão aberta com R1.
        r1 = cenario.entrar(usuario, _ip_unico()).refresh
        # Passo 2: renovação normal, R1 → R2.
        r2 = RenovarSessao(cenario.deps).executar(r1).refresh
        assert r2 != r1
        # Passo 3: R1 reapresentado dentro da janela não derruba a sessão.
        cenario.relogio.avancar(5)
        with pytest.raises(RenovacaoConcorrente):
            RenovarSessao(cenario.deps).executar(r1)
        assert cenario.consulta(
            "SELECT revogada_em FROM auth.sessao_familia WHERE usuario_id = %s", usuario.id
        ) == [(None,)]
        # Passo 4: fora da janela, revoga a família e audita.
        cenario.relogio.avancar(6)
        with pytest.raises(NaoAutenticado):
            RenovarSessao(cenario.deps).executar(r1)
        linhas = cenario.consulta(
            "SELECT motivo_revogacao FROM auth.sessao_familia WHERE usuario_id = %s", usuario.id
        )
        assert linhas == [("reuso",)]
        auditoria = cenario.consulta(
            "SELECT tipo FROM audit.evento WHERE usuario_id = %s", usuario.id
        )
        assert auditoria == [("refresh_reusado",)]
        # Passo 5: o token vigente também cai.
        with pytest.raises(NaoAutenticado):
            RenovarSessao(cenario.deps).executar(r2)


def test_uso_concorrente_nao_derruba_a_sessao(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    r1 = cenario.entrar(usuario, _ip_unico()).refresh

    def renovar(_: int) -> str:
        try:
            RenovarSessao(cenario.deps).executar(r1)
        except RenovacaoConcorrente:
            return "concorrente"
        return "ok"

    with ThreadPoolExecutor(4) as executor:
        resultados = sorted(executor.map(renovar, range(4)))
    assert resultados == ["concorrente", "concorrente", "concorrente", "ok"]
    assert cenario.consulta(
        "SELECT revogada_em FROM auth.sessao_familia WHERE usuario_id = %s", usuario.id
    ) == [(None,)]


def test_refresh_expira_com_doze_horas_de_inatividade(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    r1 = cenario.entrar(usuario, _ip_unico()).refresh
    cenario.relogio.avancar(12 * 3600 + 1)
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(r1)


def test_refresh_expira_em_sete_dias_mesmo_com_uso(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    refresh = cenario.entrar(usuario, _ip_unico()).refresh
    for _ in range(15):
        cenario.relogio.avancar(11 * 3600 + 60)
        refresh = RenovarSessao(cenario.deps).executar(refresh).refresh
    cenario.relogio.avancar(11 * 3600)
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(refresh)


def test_refresh_inexistente_e_recusado(cenario: Cenario) -> None:
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar("nao-existe")


def test_refresh_guardado_so_como_hash(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    r1 = cenario.entrar(usuario, _ip_unico()).refresh
    linhas = cenario.consulta(
        """SELECT t.hash_sha256 FROM auth.refresh_token t
           JOIN auth.sessao_familia f ON f.id = t.familia_id WHERE f.usuario_id = %s""",
        usuario.id,
    )
    assert len(linhas) == 1
    assert r1.encode() not in cast(bytes, linhas[0][0])


def test_sair_revoga_a_familia(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    r1 = cenario.entrar(usuario, _ip_unico()).refresh
    Sair(cenario.deps).executar(r1)
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(r1)


def test_renovar_reflete_papeis_atuais(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    r1 = cenario.entrar(usuario, _ip_unico()).refresh
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.definir_papeis(
            usuario.id, cenario.tenant, frozenset({Papel.ANALISAR, Papel.APROVAR})
        )
    novo = RenovarSessao(cenario.deps).executar(r1)
    assert cenario.deps.emissor.verificar(novo.acesso).papeis == {Papel.ANALISAR, Papel.APROVAR}


def test_troca_de_inquilino_so_onde_tem_papel(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    principal = cenario.deps.emissor.verificar(tokens.acesso)
    with pytest.raises(AcessoNegado):
        TrocarInquilino(cenario.deps).executar(principal, tokens.refresh, uuid4())


def test_troca_de_inquilino_emite_token_do_novo(cenario: Cenario, banco: Banco) -> None:
    usuario, _ = cenario.criar_usuario()
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        linha = s.execute("INSERT INTO core.tenant (nome) VALUES ('B') RETURNING id").fetchone()
    assert linha is not None
    outro: UUID = linha[0]
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.definir_papeis(usuario.id, outro, frozenset({Papel.ANALISAR}))
    tokens = cenario.entrar(usuario, _ip_unico())
    principal = cenario.deps.emissor.verificar(tokens.acesso)
    novos = TrocarInquilino(cenario.deps).executar(principal, tokens.refresh, outro)
    assert cenario.deps.emissor.verificar(novos.acesso).tenant_id == outro
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(tokens.refresh)


# --- Achados da revisão de segurança F1.20 ---------------------------------------------------


class _HashComEfeito:
    """Executa uma ação durante a verificação: reproduz corridas de forma determinística."""

    def __init__(self, base: object, efeito: Callable[[], None]) -> None:
        self._base = base
        self._efeito = efeito

    def __getattr__(self, nome: str) -> object:
        return getattr(self._base, nome)

    def verificar(self, guardado: str, senha: str) -> bool:
        resultado = bool(self._base.verificar(guardado, senha))  # type: ignore[attr-defined]
        efeito, self._efeito = self._efeito, lambda: None
        efeito()
        return resultado


def _com_efeito(cenario: Cenario, efeito: Callable[[], None]) -> HashDeSenha:
    return cast(HashDeSenha, _HashComEfeito(cenario.deps.hash_de_senha, efeito))


def _principal(cenario: Cenario, tokens: ParDeTokens) -> Principal:
    return cenario.deps.emissor.verificar(tokens.acesso)


def test_a1_troca_com_familia_revogada_e_recusada(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    Sair(cenario.deps).executar(tokens.refresh)
    with pytest.raises(NaoAutenticado):
        TrocarInquilino(cenario.deps).executar(
            _principal(cenario, tokens), tokens.refresh, cenario.tenant
        )


def test_a1_troca_com_usuario_desativado_e_recusada(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.desativar(usuario.id)
    with pytest.raises(NaoAutenticado):
        TrocarInquilino(cenario.deps).executar(
            _principal(cenario, tokens), tokens.refresh, cenario.tenant
        )


def test_a1_troca_com_refresh_expirado_e_recusada(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    principal = _principal(cenario, tokens)
    cenario.relogio.avancar(12 * 3600 + 1)
    with pytest.raises(NaoAutenticado):
        TrocarInquilino(cenario.deps).executar(principal, tokens.refresh, cenario.tenant)


def test_a1_troca_com_refresh_ja_usado_e_reuso(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    novo = RenovarSessao(cenario.deps).executar(tokens.refresh)
    cenario.relogio.avancar(11)
    with pytest.raises(NaoAutenticado):
        TrocarInquilino(cenario.deps).executar(
            _principal(cenario, tokens), tokens.refresh, cenario.tenant
        )
    with pytest.raises(NaoAutenticado):
        RenovarSessao(cenario.deps).executar(novo.refresh)


def test_a1_troca_nao_estende_o_limite_de_sete_dias(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    principal = _principal(cenario, tokens)
    cenario.relogio.avancar(11 * 3600)
    novos = TrocarInquilino(cenario.deps).executar(principal, tokens.refresh, cenario.tenant)
    linhas = cenario.consulta(
        """SELECT expira_em FROM auth.sessao_familia WHERE usuario_id = %s
           ORDER BY criada_em""",
        usuario.id,
    )
    assert linhas[0] == linhas[1]
    assert novos.refresh != tokens.refresh


def test_a1_troca_usa_o_mfa_da_familia_e_nao_o_do_token(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    tokens = cenario.entrar(usuario, _ip_unico())
    forjado = replace(_principal(cenario, tokens), mfa_verificado=True)
    novos = TrocarInquilino(cenario.deps).executar(forjado, tokens.refresh, cenario.tenant)
    assert _principal(cenario, novos).mfa_verificado is False


def test_a2_senha_correta_nao_zera_falhas_de_totp(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    for _ in range(5):
        desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
        assert desafio is not None
        with pytest.raises(NaoAutenticado):
            ConcluirMfa(cenario.deps).executar(desafio, "000000", _ip_unico())
    with pytest.raises(MuitasTentativas):
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())


def test_a2_totp_correto_zera_as_falhas(cenario: Cenario) -> None:
    usuario, segredo = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    with pytest.raises(NaoAutenticado):
        ConcluirMfa(cenario.deps).executar(desafio, "000000", _ip_unico())
    ConcluirMfa(cenario.deps).executar(desafio, cenario.codigo(segredo), _ip_unico())
    assert cenario.consulta("SELECT falhas_login FROM auth.usuario WHERE id=%s", usuario.id) == [
        (0,)
    ]


def test_a4_login_em_andamento_nao_desfaz_desativacao(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()

    def desativar() -> None:
        with cenario.fabrica.sem_tenant() as uow:
            uow.usuarios.desativar(usuario.id)

    deps = replace(cenario.deps, hash_de_senha=_com_efeito(cenario, desativar))
    with pytest.raises(NaoAutenticado):
        Entrar(deps).executar(usuario.email, SENHA, _ip_unico())
    assert cenario.consulta("SELECT ativo FROM auth.usuario WHERE id=%s", usuario.id) == [(False,)]


def test_a4_login_em_andamento_nao_desfaz_nova_senha(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()

    def redefinir() -> None:
        with cenario.fabrica.sem_tenant() as uow:
            uow.usuarios.redefinir_senha(usuario.id, "hash-novo")

    deps = replace(cenario.deps, hash_de_senha=_com_efeito(cenario, redefinir))
    with pytest.raises(NaoAutenticado):
        Entrar(deps).executar(usuario.email, SENHA, _ip_unico())
    assert cenario.consulta("SELECT senha_argon2id FROM auth.usuario WHERE id=%s", usuario.id) == [
        ("hash-novo",)
    ]


def test_a4_falha_de_login_em_andamento_nao_desfaz_desativacao(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()

    def desativar() -> None:
        with cenario.fabrica.sem_tenant() as uow:
            uow.usuarios.desativar(usuario.id)

    deps = replace(cenario.deps, hash_de_senha=_com_efeito(cenario, desativar))
    with pytest.raises(NaoAutenticado):
        Entrar(deps).executar(usuario.email, "errada", _ip_unico())
    assert cenario.consulta("SELECT ativo FROM auth.usuario WHERE id=%s", usuario.id) == [(False,)]


def test_m2_login_valido_nao_zera_o_limite_do_ip(cenario: Cenario) -> None:
    ip = _ip_unico()
    limite = cenario.deps.parametros.falhas_antes_do_bloqueio_ip
    usuario, _ = cenario.criar_usuario()
    for _ in range(limite - 1):
        with pytest.raises(NaoAutenticado):
            Entrar(cenario.deps).executar(f"{uuid4()}@teste.com", "errada", ip)
    cenario.entrar(usuario, ip)
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(f"{uuid4()}@teste.com", "errada", ip)
    with pytest.raises(MuitasTentativas):
        cenario.entrar(usuario, ip)


def test_m2_falhas_de_ip_decaem_depois_da_janela(cenario: Cenario) -> None:
    ip = _ip_unico()
    limite = cenario.deps.parametros.falhas_antes_do_bloqueio_ip
    for _ in range(limite - 1):
        with pytest.raises(NaoAutenticado):
            Entrar(cenario.deps).executar(f"{uuid4()}@teste.com", "errada", ip)
    cenario.relogio.avancar(cenario.deps.parametros.janela_de_falhas.total_seconds() + 1)
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(f"{uuid4()}@teste.com", "errada", ip)
    usuario, _ = cenario.criar_usuario()
    assert cenario.entrar(usuario, ip).acesso


def test_m4_mesmo_codigo_em_paralelo_so_vale_uma_vez(cenario: Cenario) -> None:
    usuario, segredo = cenario.criar_usuario(frozenset({Papel.APROVAR}), mfa=True)
    desafio = Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico()).desafio
    assert desafio is not None
    codigo = cenario.codigo(segredo)

    def concluir(_: int) -> str:
        try:
            ConcluirMfa(cenario.deps).executar(desafio, codigo, _ip_unico())
        except NaoAutenticado:
            return "recusado"
        return "ok"

    with ThreadPoolExecutor(4) as executor:
        resultados = list(executor.map(concluir, range(4)))
    assert resultados.count("ok") == 1


@pytest.mark.parametrize("falhas", [47, 1100, 10_000])
def test_n1_bloqueio_nao_estoura_com_muitas_falhas(falhas: int) -> None:
    assert ParametrosDeSessao().duracao_do_bloqueio(falhas) == timedelta(minutes=15)


def test_n1_falhas_acumuladas_continuam_registradas(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with psycopg.connect(cenario.banco.superusuario, autocommit=True) as s:
        s.execute("UPDATE auth.usuario SET falhas_login = 5000 WHERE id = %s", (usuario.id,))
    with pytest.raises(NaoAutenticado):
        Entrar(cenario.deps).executar(usuario.email, "errada", _ip_unico())
    assert cenario.consulta("SELECT falhas_login FROM auth.usuario WHERE id=%s", usuario.id) == [
        (5001,)
    ]
    with pytest.raises(MuitasTentativas):
        Entrar(cenario.deps).executar(usuario.email, SENHA, _ip_unico())


def test_n2_login_em_andamento_nao_abre_sessao_apos_redefinicao(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()

    def redefinir() -> None:
        with cenario.fabrica.sem_tenant() as uow:
            uow.usuarios.redefinir_senha(usuario.id, "hash-novo")

    deps = replace(cenario.deps, hash_de_senha=_com_efeito(cenario, redefinir))
    with pytest.raises(NaoAutenticado):
        Entrar(deps).executar(usuario.email, SENHA, _ip_unico())
    assert cenario.consulta(
        "SELECT count(*) FROM auth.sessao_familia WHERE usuario_id=%s", usuario.id
    ) == [(0,)]


def test_n3_ativar_mfa_exige_o_segredo_verificado(cenario: Cenario) -> None:
    usuario, _ = cenario.criar_usuario()
    with cenario.fabrica.sem_tenant() as uow:
        uow.usuarios.iniciar_cadastro_mfa(usuario.id, b"segredo-novo")
        assert uow.usuarios.ativar_mfa(usuario.id, 1, b"segredo-antigo") is False
        assert uow.usuarios.ativar_mfa(usuario.id, 1, b"segredo-novo") is True
    # Não deixa no banco compartilhado um TOTP que nenhum cifrador abre.
    cenario.excluir_usuario(usuario.id)
