"""Repositórios do adaptador a_db."""

from dynaprice.adaptadores.saida.postgres.repositorios.agenda import AgendaDeJobsPostgres
from dynaprice.adaptadores.saida.postgres.repositorios.auditoria import TrilhaDeAuditoriaPostgres
from dynaprice.adaptadores.saida.postgres.repositorios.autenticacao import (
    RepositorioDeUsuariosPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.cadastro import (
    RepositorioDeContratosPostgres,
    RepositorioDeEmpresasPostgres,
    RepositorioDeVinculosPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.cotacoes import (
    RepositorioDeCotacoesPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.divergencias import (
    RepositorioDeDivergenciasPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.extracoes import (
    RepositorioDeConectoresPostgres,
    RepositorioDeExtracoesPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.fatos import (
    AlertasPostgres,
    RepositorioDeFatosPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.lotes import RepositorioDeLotesPostgres
from dynaprice.adaptadores.saida.postgres.repositorios.precificacao import (
    RepositorioDePoliticasPostgres,
    RepositorioDePrecosAlvoPostgres,
    RepositorioDeRecomendacoesPostgres,
)
from dynaprice.adaptadores.saida.postgres.repositorios.retencao import RetencaoPostgres
from dynaprice.adaptadores.saida.postgres.repositorios.sessoes import (
    LimiteDeTentativasPostgres,
    RepositorioDeRecuperacaoPostgres,
    RepositorioDeSessoesPostgres,
)

__all__ = [
    "AgendaDeJobsPostgres",
    "AlertasPostgres",
    "LimiteDeTentativasPostgres",
    "RepositorioDeConectoresPostgres",
    "RepositorioDeContratosPostgres",
    "RepositorioDeCotacoesPostgres",
    "RepositorioDeDivergenciasPostgres",
    "RepositorioDeEmpresasPostgres",
    "RepositorioDeExtracoesPostgres",
    "RepositorioDeFatosPostgres",
    "RepositorioDeLotesPostgres",
    "RepositorioDePoliticasPostgres",
    "RepositorioDePrecosAlvoPostgres",
    "RepositorioDeRecomendacoesPostgres",
    "RepositorioDeRecuperacaoPostgres",
    "RepositorioDeSessoesPostgres",
    "RepositorioDeUsuariosPostgres",
    "RepositorioDeVinculosPostgres",
    "RetencaoPostgres",
    "TrilhaDeAuditoriaPostgres",
]
