"""Porta p_rel: repositórios por necessidade do caso de uso (ISP) e unidade de trabalho."""

from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID

from dynaprice.aplicacao.portas.fila import AgendaDeJobs
from dynaprice.aplicacao.portas.persistencia_auth import (
    LimiteDeTentativas,
    RepositorioDeRecuperacao,
    RepositorioDeSessoes,
    RepositorioDeUsuarios,
)
from dynaprice.aplicacao.portas.persistencia_preco import (
    Alertas,
    RepositorioDeConectores,
    RepositorioDeCotacoes,
    RepositorioDeDivergencias,
    RepositorioDeExtracoes,
    RepositorioDeFatos,
    RepositorioDeLotes,
    RepositorioDePoliticas,
    RepositorioDePrecosAlvo,
    RepositorioDeRecomendacoes,
    Retencao,
)
from dynaprice.dominio.modelos import Contrato, Empresa, Vinculo


class RepositorioDeContratos(Protocol):
    def obter(self, contrato_id: str) -> Contrato | None: ...

    def listar(self) -> Sequence[Contrato]: ...

    def salvar(self, contrato: Contrato) -> None: ...


class RepositorioDeEmpresas(Protocol):
    def obter(self, empresa_id: str) -> Empresa | None: ...

    def listar(self) -> Sequence[Empresa]: ...

    def salvar(self, empresa: Empresa) -> None: ...


class RepositorioDeVinculos(Protocol):
    def listar(self) -> Sequence[Vinculo]: ...

    def salvar(self, vinculo: Vinculo) -> None: ...


class TrilhaDeAuditoria(Protocol):
    def registrar(
        self,
        tipo: str,
        conteudo: Mapping[str, Any],
        *,
        usuario_id: UUID | None = None,
        request_id: str | None = None,
    ) -> None: ...

    def primeira_quebra(self) -> int | None:
        """seq do primeiro evento que não confere com a cadeia; None se está íntegra."""
        ...

    def cabeca(self) -> tuple[int, str] | None:
        """(seq, hash em hex) do último evento; None se não há eventos."""
        ...

    def hash_em(self, seq: int) -> str | None:
        """Hash (hex) do evento `seq`; None se ele não existe."""
        ...


class UnidadeDeAutenticacao(Protocol):
    """Transação sobre `auth`; fixa o inquilino quando precisa gravar auditoria."""

    @property
    def usuarios(self) -> RepositorioDeUsuarios: ...

    @property
    def sessoes(self) -> RepositorioDeSessoes: ...

    @property
    def recuperacao(self) -> RepositorioDeRecuperacao: ...

    @property
    def limites(self) -> LimiteDeTentativas: ...

    @property
    def auditoria(self) -> TrilhaDeAuditoria: ...

    def fixar_tenant(self, tenant_id: UUID) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastro: TracebackType | None,
    ) -> None: ...


class UnidadeDeTrabalho(Protocol):
    """Transação de um inquilino: confirma ao sair sem erro, desfaz em caso de erro."""

    @property
    def contratos(self) -> RepositorioDeContratos: ...

    @property
    def empresas(self) -> RepositorioDeEmpresas: ...

    @property
    def vinculos(self) -> RepositorioDeVinculos: ...

    @property
    def auditoria(self) -> TrilhaDeAuditoria: ...

    @property
    def fila(self) -> AgendaDeJobs: ...

    @property
    def politicas(self) -> RepositorioDePoliticas: ...

    @property
    def precos_alvo(self) -> RepositorioDePrecosAlvo: ...

    @property
    def cotacoes(self) -> RepositorioDeCotacoes: ...

    @property
    def recomendacoes(self) -> RepositorioDeRecomendacoes: ...

    @property
    def fatos(self) -> RepositorioDeFatos: ...

    @property
    def alertas(self) -> Alertas: ...

    @property
    def divergencias(self) -> RepositorioDeDivergencias: ...

    @property
    def lotes(self) -> RepositorioDeLotes: ...

    @property
    def extracoes(self) -> RepositorioDeExtracoes: ...

    @property
    def conectores(self) -> RepositorioDeConectores: ...

    @property
    def retencao(self) -> Retencao: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastro: TracebackType | None,
    ) -> None: ...


class FabricaDeUnidades(Protocol):
    def para_tenant(self, tenant_id: UUID) -> UnidadeDeTrabalho: ...

    def sem_tenant(self) -> UnidadeDeAutenticacao: ...
