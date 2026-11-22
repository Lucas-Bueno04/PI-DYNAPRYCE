"""Política de preço como dado (F1.21): rascunho validado e publicação imutável."""

from collections.abc import Mapping
from typing import Any

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.erros import Conflito, NaoEncontrado
from dynaprice.aplicacao.portas import FabricaDeUnidades, Relogio
from dynaprice.dominio.modelos import fabricar_politica
from dynaprice.dominio.modelos.autenticacao import Principal


class CriarRascunhoDePolitica:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, documento: Mapping[str, Any]) -> int:
        autorizar(principal, Acao.USAR_LABORATORIO)
        fabricar_politica({**documento, "versao": 1})
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            versao = uow.politicas.salvar_rascunho(documento)
            uow.auditoria.registrar(
                "politica_rascunho", {"versao": versao}, usuario_id=principal.usuario_id
            )
            return versao


class PublicarPolitica:
    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(self, principal: Principal, versao: int) -> None:
        autorizar(principal, Acao.PUBLICAR_POLITICA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            registro = uow.politicas.obter(versao)
            if registro is None:
                raise NaoEncontrado(f"política {versao}")
            if registro.estado != "rascunho":
                raise Conflito("só rascunho pode ser publicado")
            if registro.portao_aceite is False:
                raise Conflito("portão de aceite das equações reprovado")
            uow.politicas.publicar(versao, principal.usuario_id, self._relogio.agora())
            uow.auditoria.registrar(
                "politica_publicada", {"versao": versao}, usuario_id=principal.usuario_id
            )
