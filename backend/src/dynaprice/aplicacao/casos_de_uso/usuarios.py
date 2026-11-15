"""Gestão de usuários e papéis por inquilino (uc_users), criação do primeiro administrador."""

from collections.abc import Sequence
from uuid import UUID, uuid4

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.autenticacao import DependenciasDeAutenticacao
from dynaprice.aplicacao.erros import Conflito, NaoEncontrado
from dynaprice.dominio.modelos import ValorInvalido
from dynaprice.dominio.modelos.autenticacao import Papel, Principal, Usuario

TAMANHO_MINIMO_DA_SENHA = 12
TAMANHO_MAXIMO_DA_SENHA = 1024


def validar_senha(senha: str) -> None:
    if not TAMANHO_MINIMO_DA_SENHA <= len(senha) <= TAMANHO_MAXIMO_DA_SENHA:
        raise ValorInvalido(f"a senha precisa ter ao menos {TAMANHO_MINIMO_DA_SENHA} caracteres")


class CriarUsuario:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(
        self, principal: Principal, email: str, senha: str, papeis: frozenset[Papel]
    ) -> UUID:
        autorizar(principal, Acao.GERIR_USUARIOS)
        validar_senha(senha)
        with self._deps.fabrica.sem_tenant() as uow:
            existente = uow.usuarios.obter_por_email(email)
            if existente is not None:
                raise Conflito("e-mail já cadastrado")
            usuario = Usuario(uuid4(), email, self._deps.hash_de_senha.gerar(senha))
            uow.usuarios.criar(usuario)
            uow.usuarios.definir_papeis(usuario.id, principal.tenant_id, papeis)
            uow.fixar_tenant(principal.tenant_id)
            uow.auditoria.registrar(
                "usuario_criado",
                {"usuario": str(usuario.id), "papeis": sorted(papeis)},
                usuario_id=principal.usuario_id,
            )
            return usuario.id


class ListarUsuarios:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, principal: Principal) -> Sequence[tuple[Usuario, frozenset[Papel]]]:
        autorizar(principal, Acao.GERIR_USUARIOS)
        with self._deps.fabrica.sem_tenant() as uow:
            return [
                (usuario, uow.usuarios.papeis(usuario.id, principal.tenant_id))
                for usuario in uow.usuarios.listar_do_inquilino(principal.tenant_id)
            ]


class DefinirPapeis:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, principal: Principal, usuario_id: UUID, papeis: frozenset[Papel]) -> None:
        autorizar(principal, Acao.GERIR_USUARIOS)
        with self._deps.fabrica.sem_tenant() as uow:
            if not uow.usuarios.papeis(usuario_id, principal.tenant_id):
                raise NaoEncontrado("usuário não pertence ao inquilino")
            uow.usuarios.definir_papeis(usuario_id, principal.tenant_id, papeis)
            uow.sessoes.revogar_no_inquilino(
                usuario_id, principal.tenant_id, self._deps.relogio.agora(), "papeis"
            )
            uow.fixar_tenant(principal.tenant_id)
            uow.auditoria.registrar(
                "papeis_definidos",
                {"usuario": str(usuario_id), "papeis": sorted(papeis)},
                usuario_id=principal.usuario_id,
            )


class DesativarUsuario:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, principal: Principal, usuario_id: UUID) -> None:
        autorizar(principal, Acao.GERIR_USUARIOS)
        with self._deps.fabrica.sem_tenant() as uow:
            inquilinos = set(uow.usuarios.inquilinos(usuario_id))
            if principal.tenant_id not in inquilinos:
                raise NaoEncontrado("usuário não pertence ao inquilino")
            if inquilinos == {principal.tenant_id}:
                uow.usuarios.desativar(usuario_id)
            # Em conta de vários inquilinos, sai só deste: os outros não são dele (M1).
            uow.usuarios.definir_papeis(usuario_id, principal.tenant_id, frozenset())
            uow.sessoes.revogar_no_inquilino(
                usuario_id, principal.tenant_id, self._deps.relogio.agora(), "desativado"
            )
            uow.fixar_tenant(principal.tenant_id)
            uow.auditoria.registrar(
                "usuario_desativado", {"usuario": str(usuario_id)}, usuario_id=principal.usuario_id
            )


class CriarPrimeiroAdministrador:
    """Só funciona com o banco sem administrador: é o ponto de partida da instalação."""

    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, nome_do_inquilino: str, email: str, senha: str) -> UUID:
        validar_senha(senha)
        with self._deps.fabrica.sem_tenant() as uow:
            if uow.usuarios.existe_administrador():
                raise Conflito("já existe administrador")
            tenant_id = uuid4()
            uow.usuarios.criar_inquilino(tenant_id, nome_do_inquilino)
            usuario = Usuario(uuid4(), email, self._deps.hash_de_senha.gerar(senha))
            uow.usuarios.criar(usuario)
            uow.usuarios.definir_papeis(
                usuario.id, tenant_id, frozenset({Papel.ADMINISTRAR, Papel.APROVAR})
            )
            uow.auditoria.registrar("administrador_criado", {}, usuario_id=usuario.id)
            return tenant_id
