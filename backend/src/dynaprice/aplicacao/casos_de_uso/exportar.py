"""Exportação por lote (F1.28): idempotente, com estado de falha e nova tentativa."""

import hashlib
from dataclasses import replace
from uuid import UUID

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.erros import NaoEncontrado
from dynaprice.aplicacao.portas import (
    ErroDeExportacao,
    ErroPermanente,
    ErroTransitorio,
    ExportadorDeRecomendacoes,
    FabricaDeUnidades,
    JobReservado,
    Relogio,
    UnidadeDeTrabalho,
)
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.modelos.recomendacao import EstadoRecomendacao, Recomendacao

TIPO_DO_JOB = "exportar"


def _chave(hash_do_lote: str) -> str:
    return f"{TIPO_DO_JOB}:{hash_do_lote}"


class SolicitarExportacao:
    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(self, principal: Principal) -> UUID | None:
        autorizar(principal, Acao.EXPORTAR_RECOMENDACOES)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            aprovadas = uow.recomendacoes.listar(EstadoRecomendacao.APROVADA)
            if not aprovadas:
                return None
            ids = sorted(str(r.id) for r in aprovadas)
            hash_do_lote = hashlib.sha256("|".join(ids).encode()).hexdigest()
            lote = uow.lotes.criar(hash_do_lote)
            for r in aprovadas:
                if r.lote_id != lote:
                    uow.recomendacoes.salvar(
                        replace(r, lote_id=lote, versao=r.versao + 1), r.versao
                    )
            uow.fila.enfileirar(
                TIPO_DO_JOB, _chave(hash_do_lote), {"lote_id": str(lote)}, self._relogio.agora()
            )
            return lote


class ExecutarExportacao:
    """Manipulador do job: gera o arquivo, marca exportadas e reajusta o preço vigente."""

    def __init__(
        self,
        fabrica: FabricaDeUnidades,
        relogio: Relogio,
        exportador: ExportadorDeRecomendacoes,
        max_tentativas: int,
    ) -> None:
        self._fabrica = fabrica
        self._relogio = relogio
        self._exportador = exportador
        self._max_tentativas = max_tentativas

    def executar(self, job: JobReservado) -> None:
        lote = UUID(job.parametros["lote_id"])
        falha: ErroDeExportacao | None = None
        # O erro sobe depois do commit: o estado de falha precisa ficar gravado.
        with self._fabrica.para_tenant(job.tenant_id) as uow:
            aprovadas = [
                r
                for r in uow.recomendacoes.do_lote(lote)
                if r.estado is EstadoRecomendacao.APROVADA
            ]
            if aprovadas:
                try:
                    self._concluir(uow, lote, aprovadas)
                except ErroDeExportacao as erro:
                    falha = erro
                    self._registrar_falha(uow, job, aprovadas)
        if falha is not None:
            self._relancar(job, falha)

    def _concluir(self, uow: UnidadeDeTrabalho, lote: UUID, aprovadas: list[Recomendacao]) -> None:
        arquivo = self._exportador.gerar(aprovadas)
        digesto = hashlib.sha256(arquivo).hexdigest()
        uow.lotes.gravar_arquivo(lote, arquivo, digesto, self._relogio.agora())
        for r in aprovadas:
            uow.recomendacoes.salvar(r.exportar(lote), r.versao)
            contrato = uow.contratos.obter(r.contrato_id)
            if contrato is not None:
                uow.contratos.salvar(contrato.reajustar(r.preco_proposto))
        uow.auditoria.registrar(
            "lote_exportado", {"lote": str(lote), "sha256": digesto, "itens": len(aprovadas)}
        )

    def _registrar_falha(
        self, uow: UnidadeDeTrabalho, job: JobReservado, aprovadas: list[Recomendacao]
    ) -> None:
        if job.tentativas < self._max_tentativas:
            return
        for r in aprovadas:
            uow.recomendacoes.salvar(r.falhar_exportacao(), r.versao)
        uow.alertas.registrar("exportacao_falhou", job.parametros["lote_id"])

    def _relancar(self, job: JobReservado, falha: ErroDeExportacao) -> None:
        if job.tentativas >= self._max_tentativas:
            raise ErroPermanente(str(falha)) from falha
        raise ErroTransitorio(str(falha)) from falha


class TentarExportarDeNovo:
    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(self, principal: Principal, lote: UUID) -> None:
        autorizar(principal, Acao.EXPORTAR_RECOMENDACOES)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            hash_do_lote = uow.lotes.hash_de(lote)
            if hash_do_lote is None:
                raise NaoEncontrado("lote")
            for r in uow.recomendacoes.do_lote(lote):
                if r.estado is EstadoRecomendacao.FALHA_EXPORTACAO:
                    uow.recomendacoes.salvar(r.tentar_de_novo(), r.versao)
            uow.fila.reabrir(_chave(hash_do_lote), self._relogio.agora())
            uow.auditoria.registrar(
                "exportacao_reaberta", {"lote": str(lote)}, usuario_id=principal.usuario_id
            )
