"""Login por senha, conclusão por TOTP e bloqueio progressivo (ADR-002)."""

from collections.abc import Sequence
from uuid import UUID

from dynaprice.aplicacao.casos_de_uso.autenticacao.base import (
    DependenciasDeAutenticacao,
    ParDeTokens,
    ResultadoDeEntrada,
    abrir_sessao,
    contexto_totp,
    usuario_do_desafio,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao.controle import ControleDeFalhas
from dynaprice.aplicacao.erros import NaoAutenticado
from dynaprice.aplicacao.portas import UnidadeDeAutenticacao
from dynaprice.dominio.modelos.autenticacao import PAPEIS_COM_MFA, Usuario


def _exige_mfa(uow: UnidadeDeAutenticacao, usuario: Usuario, inquilinos: Sequence[UUID]) -> bool:
    return any(uow.usuarios.papeis(usuario.id, t) & PAPEIS_COM_MFA for t in inquilinos)


def proxima_etapa(
    deps: DependenciasDeAutenticacao, uow: UnidadeDeAutenticacao, usuario: Usuario
) -> ResultadoDeEntrada:
    """Depois de provar quem é (senha ou IdP): sem inquilino, TOTP, cadastro de MFA ou sessão."""
    inquilinos = uow.usuarios.inquilinos(usuario.id)
    if not inquilinos:
        return ResultadoDeEntrada()
    desafio = deps.emissor.emitir_desafio(usuario.id)
    if usuario.mfa_ativo:
        return ResultadoDeEntrada(desafio=desafio)
    if _exige_mfa(uow, usuario, inquilinos):
        return ResultadoDeEntrada(desafio=desafio, cadastro_mfa_requerido=True)
    return ResultadoDeEntrada(tokens=abrir_sessao(deps, uow, usuario, inquilinos[0], mfa=False))


class Entrar:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, email: str, senha: str, ip: str) -> ResultadoDeEntrada:
        controle = ControleDeFalhas(self._deps, ip)
        # O erro sobe só depois do commit: a falha contada precisa ficar gravada.
        with self._deps.fabrica.sem_tenant() as uow:
            controle.exigir_ip_livre(uow)
            usuario = uow.usuarios.obter_por_email(email)
            if usuario is not None:
                controle.exigir_conta_livre(usuario)
            aceito = self._conferir(usuario, senha)
            if usuario is None or not aceito:
                controle.contar(uow, usuario)
                resultado = None
            else:
                resultado = self._concluir(uow, controle, usuario, senha)
        if resultado is None:
            raise NaoAutenticado("credenciais inválidas")
        return resultado

    def _conferir(self, usuario: Usuario | None, senha: str) -> bool:
        if usuario is None or not usuario.ativo:
            self._deps.hash_de_senha.simular_verificacao(senha)
            return False
        return self._deps.hash_de_senha.verificar(usuario.senha_hash, senha)

    def _concluir(
        self,
        uow: UnidadeDeAutenticacao,
        controle: ControleDeFalhas,
        usuario: Usuario,
        senha: str,
    ) -> ResultadoDeEntrada | None:
        if self._credencial_mudou(uow, usuario):
            return None
        if not usuario.mfa_ativo:
            # Com MFA ativo, só o TOTP correto zera: senha certa não pode limpar palpites (A2).
            controle.zerar_conta(uow, usuario)
        self._atualizar_hash(uow, usuario, senha)
        return proxima_etapa(self._deps, uow, usuario)

    @staticmethod
    def _credencial_mudou(uow: UnidadeDeAutenticacao, usuario: Usuario) -> bool:
        """A credencial pode mudar durante o Argon2: a sessão não abre sobre a antiga (N2)."""
        atual = uow.usuarios.obter_travado(usuario.id)
        return atual is None or not atual.ativo or atual.senha_hash != usuario.senha_hash

    def _atualizar_hash(self, uow: UnidadeDeAutenticacao, usuario: Usuario, senha: str) -> None:
        if self._deps.hash_de_senha.precisa_refazer(usuario.senha_hash):
            novo = self._deps.hash_de_senha.gerar(senha)
            uow.usuarios.trocar_hash_se_igual(usuario.id, usuario.senha_hash, novo)


class ConcluirMfa:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, desafio: str, codigo: str, ip: str) -> ParDeTokens:
        controle = ControleDeFalhas(self._deps, ip)
        with self._deps.fabrica.sem_tenant() as uow:
            controle.exigir_ip_livre(uow)
            usuario = usuario_do_desafio(self._deps, uow, desafio)
            controle.exigir_conta_livre(usuario)
            passo = self._passo_aceito(usuario, codigo)
            if passo is None or not uow.usuarios.registrar_passo_totp(usuario.id, passo):
                controle.registrar_falha(uow, usuario)
                tokens = None
            else:
                tokens = self._abrir(uow, controle, usuario)
        if tokens is None:
            raise NaoAutenticado("código inválido")
        return tokens

    def _passo_aceito(self, usuario: Usuario, codigo: str) -> int | None:
        if usuario.totp_cifrado is None or not usuario.mfa_ativo:
            return None
        segredo = self._deps.cifrador.decifrar(usuario.totp_cifrado, contexto_totp(usuario.id))
        passo = self._deps.totp.passo_valido(segredo.decode(), codigo, self._deps.relogio.agora())
        ultimo = usuario.totp_ultimo_passo
        # RFC 6238 §5.2: o mesmo código não vale duas vezes.
        return None if passo is None or (ultimo is not None and passo <= ultimo) else passo

    def _abrir(
        self, uow: UnidadeDeAutenticacao, controle: ControleDeFalhas, usuario: Usuario
    ) -> ParDeTokens:
        atual = uow.usuarios.obter_travado(usuario.id)
        if atual is None or not atual.ativo:
            raise NaoAutenticado("usuário inativo")
        controle.zerar_conta(uow, usuario)
        inquilinos = uow.usuarios.inquilinos(usuario.id)
        if not inquilinos:
            raise NaoAutenticado("usuário sem inquilino")
        return abrir_sessao(self._deps, uow, usuario, inquilinos[0], mfa=True)
