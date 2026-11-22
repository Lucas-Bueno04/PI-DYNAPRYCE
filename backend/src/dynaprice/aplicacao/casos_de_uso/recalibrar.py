"""Recalibração mensal (m_recal, seção 4.2): usa a política vigente; nunca reestima os β."""

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from dynaprice.aplicacao.portas import ErroPermanente, FabricaDeUnidades, Relogio, UnidadeDeTrabalho
from dynaprice.dominio.modelos import Competencia, Contrato, Dinheiro, PoliticaVersao
from dynaprice.dominio.modelos.recomendacao import Recomendacao
from dynaprice.dominio.precificacao import (
    AgregadoDoContrato,
    AgregadorDeContratos,
    NucleoDePreco,
    PrecoInferido,
)

JANELA_MESES = 12
_LIMITE_DE_CICLOS = 60


@dataclass(frozen=True, slots=True)
class ResumoDaRecalibracao:
    recomendacoes: int
    monitorados: int
    expiradas: int
    pulados: tuple[str, ...]
    sem_mes_de_reajuste: tuple[str, ...]
    pendencias: tuple[str, ...]


def trajetoria_ate_o_alvo(
    nucleo: NucleoDePreco,
    vigente: Dinheiro,
    alvo: Dinheiro,
    inflacao: Decimal,
    revisao_integral: bool = False,
) -> tuple[Dinheiro, ...]:
    """Passos do Algoritmo 3 até o alvo, com inflação só no primeiro ciclo (alvo real constante)."""
    passos: list[Dinheiro] = []
    atual, variacao = vigente, inflacao
    for _ in range(_LIMITE_DE_CICLOS):
        passo = nucleo.transicao.proximo(atual, alvo, variacao, revisao_integral)
        if passo.novo == atual:
            break
        passos.append(passo.novo)
        atual, variacao = passo.novo, Decimal(0)
        if atual >= alvo or revisao_integral:
            break
    return tuple(passos)


@dataclass(slots=True)
class _Contagem:
    recomendacoes: int = 0
    monitorados: int = 0
    pulados: list[str] = field(default_factory=list)
    sem_mes: list[str] = field(default_factory=list)


class _Ciclo:
    """Estado de uma execução: a política fica fixa do início ao fim."""

    def __init__(
        self, uow: UnidadeDeTrabalho, politica: PoliticaVersao, competencia: Competencia
    ) -> None:
        self._uow = uow
        self._politica = politica
        self._nucleo = NucleoDePreco.da_politica(politica)
        self._competencia = competencia
        self._efeito = competencia.somar(politica.antecedencia_reajuste_meses)
        self._aguardando = uow.recomendacoes.contratos_aguardando_exportacao()
        inicio = competencia.somar(1 - JANELA_MESES)
        indice = uow.fatos.inflacao_acumulada(inicio, competencia)
        self._inflacao_ausente = indice is None
        self._inflacao = Decimal(0) if indice is None else max(indice, Decimal(0))
        self.contagem = _Contagem()

    def agregar(self) -> tuple[tuple[AgregadoDoContrato, ...], tuple[str, ...]]:
        fatos = self._uow.fatos.direcionadores_do_regime_atual(
            self._competencia.somar(1 - JANELA_MESES), self._competencia
        )
        resultado = AgregadorDeContratos(self._nucleo.equacoes).agregar(
            self._competencia, self._uow.empresas.listar(), self._uow.vinculos.listar(), fatos
        )
        return resultado.contratos, tuple(p.referencia for p in resultado.pendencias)

    def alertar_indice_ausente(self) -> None:
        if self._inflacao_ausente:
            self._uow.alertas.registrar("indice_ausente", str(self._competencia))

    def avaliar(self, agregado: AgregadoDoContrato, contrato: Contrato) -> None:
        horas = agregado.horas_padrao.total if agregado.meses else None
        inferido = self._nucleo.inferencia.preco(
            agregado.regime, horas, agregado.meses, contrato.kappa
        )
        alvo_id = self._gravar_alvo(agregado, contrato, inferido)
        if alvo_id is None:
            return
        if contrato.id in self._aguardando:
            self.contagem.pulados.append(contrato.id)
            self._uow.alertas.registrar("recomendacao_nao_exportada", contrato.id)
            return
        if inferido.provisorio:
            self._monitorar_provisorio(contrato)
            return
        self._decidir_recomendacao(contrato, inferido, alvo_id)

    def _gravar_alvo(
        self, agregado: AgregadoDoContrato, contrato: Contrato, inferido: PrecoInferido
    ) -> UUID | None:
        entradas: dict[str, Any] = {
            "regime": agregado.regime.value,
            "meses": agregado.meses,
            "credibilidade": str(inferido.credibilidade),
            "horas_padrao": str(agregado.horas_padrao.total.valor),
            "horas_por_departamento": {
                d.value: str(agregado.horas_padrao.horas(d))
                for d in agregado.horas_padrao.departamentos
            },
            "kappa": str(contrato.kappa.valor),
            "empresas": list(agregado.empresas),
            "inflacao": str(self._inflacao),
            "inflacao_ausente": self._inflacao_ausente,
        }
        return self._uow.precos_alvo.gravar(
            contrato.id,
            self._competencia,
            self._politica.versao,
            inferido.nivel.value,
            agregado.horas_padrao.total.valor if agregado.meses else None,
            entradas,
            inferido.valor.valor,
        )

    def _monitorar_provisorio(self, contrato: Contrato) -> None:
        if not contrato.provisorio:
            # D13: mudança de regime derruba ℓ; o contrato volta a provisório.
            self._uow.contratos.salvar(replace(contrato, provisorio=True))
        self.contagem.monitorados += 1

    def _decidir_recomendacao(
        self, contrato: Contrato, inferido: PrecoInferido, alvo_id: UUID
    ) -> None:
        integral = contrato.provisorio
        if not integral and not self._na_janela(contrato, inferido):
            return
        passos = trajetoria_ate_o_alvo(
            self._nucleo, contrato.preco_vigente, inferido.valor, self._inflacao, integral
        )
        if not passos:
            self.contagem.monitorados += 1
            return
        self._uow.recomendacoes.inserir(
            Recomendacao(
                id=uuid4(),
                contrato_id=contrato.id,
                preco_alvo_id=alvo_id,
                politica_versao=self._politica.versao,
                competencia=self._competencia,
                efeito=self._efeito,
                preco_vigente=contrato.preco_vigente,
                preco_proposto=passos[0],
                trajetoria=passos,
                kappa=contrato.kappa,
            )
        )
        self.contagem.recomendacoes += 1

    def _na_janela(self, contrato: Contrato, inferido: PrecoInferido) -> bool:
        if contrato.mes_reajuste is None:
            self.contagem.sem_mes.append(contrato.id)
            return False
        vigente = contrato.preco_vigente
        dispara = (
            vigente.valor > 0 and self._nucleo.gatilho.avaliar(vigente, inferido.valor).dispara
        )
        if contrato.mes_reajuste != self._efeito.mes or not dispara:
            self.contagem.monitorados += 1
            return False
        return True


class Recalibrar:
    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(self, tenant_id: UUID, competencia: Competencia) -> ResumoDaRecalibracao:
        with self._fabrica.para_tenant(tenant_id) as uow:
            politica = uow.politicas.publicada()
            if politica is None:
                raise ErroPermanente("nenhuma política publicada")
            expiradas = self._expirar_antigas(uow, competencia)
            ciclo = _Ciclo(uow, politica, competencia)
            agregados, pendencias = ciclo.agregar()
            por_id = {c.id: c for c in uow.contratos.listar()}
            for agregado in agregados:
                if agregado.contrato_id in por_id:
                    ciclo.avaliar(agregado, por_id[agregado.contrato_id])
            ciclo.alertar_indice_ausente()
            contagem = ciclo.contagem
            uow.auditoria.registrar(
                "recalibracao_concluida",
                {
                    "competencia": str(competencia),
                    "politica": politica.versao,
                    "recomendacoes": contagem.recomendacoes,
                },
            )
        return ResumoDaRecalibracao(
            contagem.recomendacoes,
            contagem.monitorados,
            expiradas,
            tuple(contagem.pulados),
            tuple(contagem.sem_mes),
            pendencias,
        )

    @staticmethod
    def _expirar_antigas(uow: UnidadeDeTrabalho, competencia: Competencia) -> int:
        antigas = uow.recomendacoes.pendentes_anteriores(competencia)
        for recomendacao in antigas:
            uow.recomendacoes.salvar(recomendacao.expirar(), recomendacao.versao)
        return len(antigas)
