"""Conectores (uc_conn): credencial cifrada, extração por job e agendamento mensal."""

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.importar import carteira_em_json, registrar_extracao
from dynaprice.aplicacao.portas import (
    Cifrador,
    ConectorIndisponivel,
    ConfiguracaoDeConector,
    CredencialInvalida,
    ErroPermanente,
    FabricaDeUnidades,
    FonteDeCarteira,
    JobReservado,
    Relogio,
)
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.autenticacao import Principal

type FabricaDeFonte = Callable[[Mapping[str, Any], Mapping[str, Any]], FonteDeCarteira]


def _contexto(tenant_id: UUID, tipo: str) -> str:
    return f"conector:{tenant_id}:{tipo}"


@dataclass(frozen=True, slots=True)
class ResumoDoConector:
    """O que a API pode devolver: nunca a credencial."""

    tipo: str
    parametros: Mapping[str, Any]
    dias_fechamento: int
    credencial_configurada: bool


class ConfigurarConector:
    def __init__(self, fabrica: FabricaDeUnidades, cifrador: Cifrador) -> None:
        self._fabrica = fabrica
        self._cifrador = cifrador

    def executar(
        self,
        principal: Principal,
        tipo: str,
        credencial: Mapping[str, Any],
        parametros: Mapping[str, Any],
        dias_fechamento: int,
    ) -> None:
        autorizar(principal, Acao.GERIR_CONECTORES)
        cifrado = self._cifrador.cifrar(
            json.dumps(dict(credencial)).encode(), _contexto(principal.tenant_id, tipo)
        )
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            uow.conectores.salvar(
                ConfiguracaoDeConector(tipo, cifrado, parametros, dias_fechamento)
            )
            uow.auditoria.registrar(
                "conector_configurado", {"tipo": tipo}, usuario_id=principal.usuario_id
            )


class ListarConectores:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal) -> Sequence[ResumoDoConector]:
        autorizar(principal, Acao.GERIR_CONECTORES)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            return [
                ResumoDoConector(
                    c.tipo, c.parametros, c.dias_fechamento, c.credencial_cifrada is not None
                )
                for c in uow.conectores.listar()
            ]


class ExtrairCompetencia:
    """Job `extrair`. A leitura da fonte roda fora de transação (G5)."""

    def __init__(
        self,
        fabrica: FabricaDeUnidades,
        relogio: Relogio,
        cifrador: Cifrador,
        fontes: Mapping[str, FabricaDeFonte],
    ) -> None:
        self._fabrica = fabrica
        self._relogio = relogio
        self._cifrador = cifrador
        self._fontes = fontes

    def executar(self, job: JobReservado) -> None:
        tipo = str(job.parametros["fonte"])
        competencia = Competencia.de_texto(str(job.parametros["competencia"]))
        fonte = self._montar_fonte(job.tenant_id, tipo)
        carteira = fonte.extrair(competencia, competencia)
        canonico = json.dumps(carteira_em_json(carteira), sort_keys=True)
        with self._fabrica.para_tenant(job.tenant_id) as uow:
            registrar_extracao(
                uow,
                self._relogio,
                tipo,
                competencia,
                carteira,
                hashlib.sha256(canonico.encode()).hexdigest(),
            )

    def _montar_fonte(self, tenant_id: UUID, tipo: str) -> FonteDeCarteira:
        with self._fabrica.para_tenant(tenant_id) as uow:
            configuracao = uow.conectores.obter(tipo)
        if configuracao is None or configuracao.credencial_cifrada is None:
            raise ErroPermanente(f"conector {tipo} sem configuração")
        fabricar = self._fontes.get(tipo)
        if fabricar is None:
            raise ErroPermanente(f"conector {tipo} desconhecido")
        aberta = self._cifrador.decifrar(
            configuracao.credencial_cifrada, _contexto(tenant_id, tipo)
        )
        return fabricar(json.loads(aberta), configuracao.parametros)


@dataclass(frozen=True, slots=True)
class ResultadoDoTeste:
    situacao: str  # ok, indisponivel, credencial_invalida ou falhou
    detalhe: str = ""


class TestarConector(ExtrairCompetencia):
    """Faz uma leitura real da competência corrente e descarta o resultado."""

    __test__ = False  # o nome não é de um teste do pytest

    def executar(self, principal: Principal, tipo: str) -> ResultadoDoTeste:  # type: ignore[override]
        autorizar(principal, Acao.GERIR_CONECTORES)
        try:
            fonte = self._montar_fonte(principal.tenant_id, tipo)
            atual = self._relogio.competencia_atual()
            fonte.extrair(atual, atual)
        except ConectorIndisponivel:
            return ResultadoDoTeste("indisponivel")
        except CredencialInvalida:
            return ResultadoDoTeste("credencial_invalida")
        except ErroPermanente:
            return ResultadoDoTeste("falhou", "conector desconhecido")
        return ResultadoDoTeste("ok")


FECHAMENTO_PADRAO = 5
MES_DA_ESTIMACAO = 1


class AgendarCiclo:
    """Enfileira o que vence no mês; as chaves de idempotência tornam a repetição inofensiva."""

    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(self, tenant_id: UUID) -> None:
        dia = self._relogio.dia_do_mes()
        atual = self._relogio.competencia_atual()
        fechada = atual.anterior()
        agora = self._relogio.agora()
        with self._fabrica.para_tenant(tenant_id) as uow:
            for conector in uow.conectores.listar():
                if dia > conector.dias_fechamento:
                    uow.fila.enfileirar(
                        "extrair",
                        f"extrair:{conector.tipo}:{fechada}",
                        {"fonte": conector.tipo, "competencia": str(fechada)},
                        agora,
                    )
            if dia > FECHAMENTO_PADRAO:
                uow.fila.enfileirar("retencao", f"retencao:{atual}", {}, agora)
            if atual.mes == MES_DA_ESTIMACAO and dia > FECHAMENTO_PADRAO:
                uow.fila.enfileirar(
                    "estimar_politica",
                    f"estimar_politica:{atual.ano - 1}",
                    {"ano": atual.ano - 1},
                    agora,
                )
