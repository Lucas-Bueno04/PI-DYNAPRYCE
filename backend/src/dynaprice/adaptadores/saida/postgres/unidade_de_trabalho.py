"""Unidade de trabalho: uma transação com o inquilino fixado por set_config local (RLS)."""

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from psycopg import Transaction
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres.conexao import Conexao
from dynaprice.adaptadores.saida.postgres.repositorios import (
    AgendaDeJobsPostgres,
    AlertasPostgres,
    LimiteDeTentativasPostgres,
    RepositorioDeConectoresPostgres,
    RepositorioDeContratosPostgres,
    RepositorioDeCotacoesPostgres,
    RepositorioDeDivergenciasPostgres,
    RepositorioDeEmpresasPostgres,
    RepositorioDeExtracoesPostgres,
    RepositorioDeFatosPostgres,
    RepositorioDeLotesPostgres,
    RepositorioDePoliticasPostgres,
    RepositorioDePrecosAlvoPostgres,
    RepositorioDeRecomendacoesPostgres,
    RepositorioDeRecuperacaoPostgres,
    RepositorioDeSessoesPostgres,
    RepositorioDeUsuariosPostgres,
    RepositorioDeVinculosPostgres,
    RetencaoPostgres,
    TrilhaDeAuditoriaPostgres,
)
from dynaprice.aplicacao.portas import Relogio


class UnidadeDeTrabalhoPostgres:
    contratos: RepositorioDeContratosPostgres
    empresas: RepositorioDeEmpresasPostgres
    vinculos: RepositorioDeVinculosPostgres
    auditoria: TrilhaDeAuditoriaPostgres
    fila: AgendaDeJobsPostgres
    usuarios: RepositorioDeUsuariosPostgres
    sessoes: RepositorioDeSessoesPostgres
    recuperacao: RepositorioDeRecuperacaoPostgres
    limites: LimiteDeTentativasPostgres
    politicas: RepositorioDePoliticasPostgres
    precos_alvo: RepositorioDePrecosAlvoPostgres
    cotacoes: RepositorioDeCotacoesPostgres
    recomendacoes: RepositorioDeRecomendacoesPostgres
    fatos: RepositorioDeFatosPostgres
    alertas: AlertasPostgres
    divergencias: RepositorioDeDivergenciasPostgres
    lotes: RepositorioDeLotesPostgres
    extracoes: RepositorioDeExtracoesPostgres
    conectores: RepositorioDeConectoresPostgres
    retencao: RetencaoPostgres

    def __init__(self, pool: ConnectionPool[Any], relogio: Relogio, tenant_id: UUID | None) -> None:
        self._pool = pool
        self._relogio = relogio
        self._tenant_id = tenant_id
        self._conexao: Conexao
        self._transacao: AbstractContextManager[Transaction]

    def __enter__(self) -> Self:
        self._conexao = self._pool.getconn()
        self._transacao = self._conexao.transaction()
        self._transacao.__enter__()
        if self._tenant_id is not None:
            self.fixar_tenant(self._tenant_id)
        self._montar_repositorios()
        return self

    def fixar_tenant(self, tenant_id: UUID) -> None:
        # O terceiro argumento true limita o valor a esta transação (conexão vem do pool).
        self._conexao.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))

    def _montar_repositorios(self) -> None:
        self.contratos = RepositorioDeContratosPostgres(self._conexao)
        self.empresas = RepositorioDeEmpresasPostgres(self._conexao)
        self.vinculos = RepositorioDeVinculosPostgres(self._conexao)
        self.auditoria = TrilhaDeAuditoriaPostgres(self._conexao, self._relogio)
        self.fila = AgendaDeJobsPostgres(self._conexao)
        self.usuarios = RepositorioDeUsuariosPostgres(self._conexao)
        self.sessoes = RepositorioDeSessoesPostgres(self._conexao)
        self.recuperacao = RepositorioDeRecuperacaoPostgres(self._conexao)
        self.limites = LimiteDeTentativasPostgres(self._conexao)
        self.politicas = RepositorioDePoliticasPostgres(self._conexao)
        self.precos_alvo = RepositorioDePrecosAlvoPostgres(self._conexao)
        self.cotacoes = RepositorioDeCotacoesPostgres(self._conexao)
        self.recomendacoes = RepositorioDeRecomendacoesPostgres(self._conexao)
        self.fatos = RepositorioDeFatosPostgres(self._conexao)
        self.alertas = AlertasPostgres(self._conexao)
        self.divergencias = RepositorioDeDivergenciasPostgres(self._conexao)
        self.lotes = RepositorioDeLotesPostgres(self._conexao)
        self.extracoes = RepositorioDeExtracoesPostgres(self._conexao)
        self.conectores = RepositorioDeConectoresPostgres(self._conexao)
        self.retencao = RetencaoPostgres(self._conexao)

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        erro: BaseException | None,
        rastro: TracebackType | None,
    ) -> None:
        try:
            self._transacao.__exit__(tipo, erro, rastro)
        finally:
            self._pool.putconn(self._conexao)

    def tenant_configurado(self) -> str:
        linha = self._conexao.execute("SELECT current_setting('app.tenant_id', true)").fetchone()
        return (linha[0] if linha else "") or ""


class FabricaDeUnidadesPostgres:
    def __init__(self, pool: ConnectionPool[Any], relogio: Relogio) -> None:
        self._pool = pool
        self._relogio = relogio

    def para_tenant(self, tenant_id: UUID) -> UnidadeDeTrabalhoPostgres:
        return UnidadeDeTrabalhoPostgres(self._pool, self._relogio, tenant_id)

    def sem_tenant(self) -> UnidadeDeTrabalhoPostgres:
        """Só para o que é global ao produto (auth): a RLS não mostra dado de inquilino."""
        return UnidadeDeTrabalhoPostgres(self._pool, self._relogio, None)
