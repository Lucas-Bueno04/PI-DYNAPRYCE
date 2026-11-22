"""Repositórios do ciclo de preço: política, preço-alvo, recomendação, fatos e divergência."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Direcionadores,
    Honorario,
    PoliticaVersao,
    Regime,
)
from dynaprice.dominio.modelos.divergencia import Divergencia
from dynaprice.dominio.modelos.recomendacao import EstadoRecomendacao, Recomendacao


@dataclass(frozen=True, slots=True)
class RegistroDePolitica:
    versao: int
    estado: str
    documento: Mapping[str, Any]
    portao_aceite: bool | None
    relatorio: Mapping[str, Any] | None


class RepositorioDePoliticas(Protocol):
    def salvar_rascunho(
        self,
        documento: Mapping[str, Any],
        portao_aceite: bool | None = None,
        relatorio: Mapping[str, Any] | None = None,
    ) -> int: ...

    def obter(self, versao: int) -> RegistroDePolitica | None: ...

    def listar(self) -> Sequence[RegistroDePolitica]: ...

    def versao_publicada(self) -> int | None: ...

    def publicada(self) -> PoliticaVersao | None: ...

    def publicar(self, versao: int, por: UUID | None, agora: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class PrecoAlvoRegistrado:
    id: UUID
    contrato_id: str
    competencia: Competencia
    politica_versao: int
    nivel: int
    horas_padrao: Decimal | None
    entradas: Mapping[str, Any]
    preco_alvo: Decimal


class RepositorioDePrecosAlvo(Protocol):
    def gravar(
        self,
        contrato_id: str,
        competencia: Competencia,
        politica_versao: int,
        nivel: int,
        horas_padrao: Decimal | None,
        entradas: Mapping[str, Any],
        preco_alvo: Decimal,
    ) -> UUID | None:
        """Devolve o id; None se já havia preço-alvo (reexecução idempotente)."""
        ...

    def obter(self, preco_alvo_id: UUID) -> PrecoAlvoRegistrado | None: ...

    def da_competencia(self, competencia: Competencia) -> Sequence[PrecoAlvoRegistrado]: ...


class RepositorioDeRecomendacoes(Protocol):
    def inserir(self, recomendacao: Recomendacao) -> None: ...

    def obter(self, recomendacao_id: UUID) -> Recomendacao | None: ...

    def listar(self, estado: EstadoRecomendacao | None = None) -> Sequence[Recomendacao]: ...

    def salvar(self, recomendacao: Recomendacao, versao_esperada: int) -> None:
        """Concorrência otimista: versão diferente levanta Conflito."""
        ...

    def pendentes_anteriores(self, competencia: Competencia) -> Sequence[Recomendacao]: ...

    def contratos_aguardando_exportacao(self) -> frozenset[str]: ...

    def do_lote(self, lote_id: UUID) -> Sequence[Recomendacao]: ...

    def ultima_exportada(
        self, contrato_id: str, competencia: Competencia
    ) -> Recomendacao | None: ...


class RepositorioDeFatos(Protocol):
    def gravar_empresa_mes(
        self,
        direcionadores: Direcionadores,
        horas: Mapping[str, Decimal],
        versao: int,
        regime: Regime | None,
    ) -> None: ...

    def gravar_honorario(self, honorario: Honorario) -> None: ...

    def honorarios_da_competencia(self, competencia: Competencia) -> Sequence[Honorario]: ...

    def direcionadores_do_regime_atual(
        self, inicio: Competencia, fim: Competencia
    ) -> Sequence[Direcionadores]: ...

    def inflacao_acumulada(self, inicio: Competencia, fim: Competencia) -> Decimal | None:
        """Variação acumulada; None se faltar o índice de algum mês da janela."""
        ...

    def carteira(self, inicio: Competencia, fim: Competencia) -> Carteira: ...


@dataclass(frozen=True, slots=True)
class Alerta:
    id: UUID
    tipo: str
    referencia: str
    criado_em: datetime


class Alertas(Protocol):
    def registrar(
        self, tipo: str, referencia: str, detalhe: Mapping[str, Any] | None = None
    ) -> None: ...

    def nao_reconhecidos(self) -> Sequence[Alerta]: ...


class RepositorioDeLotes(Protocol):
    def criar(self, hash_recomendacoes: str) -> UUID:
        """Devolve o lote desse conjunto, criando-o se preciso (idempotente)."""
        ...

    def criar_com_id(self, lote_id: UUID, hash_recomendacoes: str) -> None: ...

    def hash_de(self, lote_id: UUID) -> str | None: ...

    def gravar_arquivo(
        self, lote_id: UUID, arquivo: bytes, sha256: str, agora: datetime
    ) -> None: ...

    def arquivo(self, lote_id: UUID) -> bytes | None: ...


class RepositorioDeExtracoes(Protocol):
    def versao_do_hash(
        self, fonte: str, competencia: Competencia, hash_conteudo: str
    ) -> int | None: ...

    def proxima_versao(self, fonte: str, competencia: Competencia) -> int: ...

    def gravar(
        self,
        fonte: str,
        competencia: Competencia,
        versao: int,
        origem: str,
        hash_conteudo: str,
        conteudo: Mapping[str, Any],
        agora: datetime,
    ) -> UUID:
        """Grava a versão e marca as anteriores como substituídas."""
        ...

    def quarentenar(self, extracao_id: UUID, arquivo: str, linha: int, motivo: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ConfiguracaoDeConector:
    tipo: str
    credencial_cifrada: bytes | None
    parametros: Mapping[str, Any]
    dias_fechamento: int


class RepositorioDeConectores(Protocol):
    def salvar(self, configuracao: ConfiguracaoDeConector) -> None: ...

    def obter(self, tipo: str) -> ConfiguracaoDeConector | None: ...

    def listar(self) -> Sequence[ConfiguracaoDeConector]: ...


class Retencao(Protocol):
    def apagar_raw_substituido(self, antes_de: datetime) -> int: ...

    def apagar_refresh_expirado(self, tenant_id: UUID, antes_de: datetime) -> int: ...

    def apagar_cotacoes(self, antes_de: datetime) -> int: ...


class RepositorioDeDivergencias(Protocol):
    def abrir(self, divergencia: Divergencia, recomendacao_id: UUID) -> bool:
        """False se já existia para o contrato e a competência."""
        ...

    def obter(self, divergencia_id: UUID) -> Divergencia | None: ...

    def salvar(self, divergencia: Divergencia) -> None: ...

    def listar(self) -> Sequence[Divergencia]: ...


@dataclass(frozen=True, slots=True)
class CotacaoRegistrada:
    id: UUID
    regime: str
    politica_versao: int
    entradas: Mapping[str, Any]
    preco: Decimal
    decomposicao: Mapping[str, Any]


class RepositorioDeCotacoes(Protocol):
    def gravar(
        self,
        regime: str,
        politica_versao: int,
        entradas: Mapping[str, Any],
        preco: Decimal,
        decomposicao: Mapping[str, Any],
        criada_por: UUID,
    ) -> UUID: ...

    def obter(self, cotacao_id: UUID) -> CotacaoRegistrada | None: ...
