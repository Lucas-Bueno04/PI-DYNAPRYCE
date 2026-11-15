"""Matriz papel × ação (S5): a autorização é regra de negócio, no anel 2 (ADR-001 item 8)."""

from dataclasses import dataclass
from enum import StrEnum

from dynaprice.aplicacao.erros import AcessoNegado
from dynaprice.dominio.modelos.autenticacao import Papel, Principal


class Acao(StrEnum):
    VER_CARTEIRA = "ver_carteira"
    COTAR_SERVICO = "cotar_servico"
    USAR_LABORATORIO = "usar_laboratorio"
    IMPORTAR_DADOS = "importar_dados"
    GERIR_VINCULOS = "gerir_vinculos"
    DECIDIR_RECOMENDACAO = "decidir_recomendacao"
    EXPORTAR_RECOMENDACOES = "exportar_recomendacoes"
    TRATAR_DIVERGENCIA = "tratar_divergencia"
    PUBLICAR_POLITICA = "publicar_politica"
    GERIR_CONECTORES = "gerir_conectores"
    GERIR_USUARIOS = "gerir_usuarios"


@dataclass(frozen=True, slots=True)
class Regra:
    papeis: frozenset[Papel]
    exige_mfa: bool = False


_LEITORES = frozenset(Papel)
_ANALISTAS = frozenset({Papel.ANALISAR, Papel.ADMINISTRAR})
_APROVADORES = frozenset({Papel.APROVAR})
_ADMINISTRADORES = frozenset({Papel.ADMINISTRAR})

MATRIZ: dict[Acao, Regra] = {
    Acao.VER_CARTEIRA: Regra(_LEITORES),
    Acao.COTAR_SERVICO: Regra(_LEITORES),
    Acao.USAR_LABORATORIO: Regra(_LEITORES),
    Acao.IMPORTAR_DADOS: Regra(_ANALISTAS),
    Acao.GERIR_VINCULOS: Regra(_ANALISTAS),
    Acao.DECIDIR_RECOMENDACAO: Regra(_APROVADORES, exige_mfa=True),
    Acao.EXPORTAR_RECOMENDACOES: Regra(_APROVADORES, exige_mfa=True),
    Acao.TRATAR_DIVERGENCIA: Regra(_APROVADORES, exige_mfa=True),
    Acao.PUBLICAR_POLITICA: Regra(_APROVADORES, exige_mfa=True),
    Acao.GERIR_CONECTORES: Regra(_ADMINISTRADORES, exige_mfa=True),
    Acao.GERIR_USUARIOS: Regra(_ADMINISTRADORES, exige_mfa=True),
}


def autorizar(principal: Principal, acao: Acao) -> None:
    regra = MATRIZ[acao]
    if not principal.papeis & regra.papeis:
        raise AcessoNegado(f"sem papel para {acao.value}")
    if regra.exige_mfa and not principal.mfa_verificado:
        raise AcessoNegado(f"{acao.value} exige TOTP verificado na sessão")
