"""Rotação da chave mestra (D-ROT-CHAVE): recifra TOTP e credenciais de conector."""

from dataclasses import replace

from dynaprice.aplicacao.casos_de_uso.autenticacao.base import contexto_totp
from dynaprice.aplicacao.portas import Cifrador, FabricaDeUnidades


class RotacionarChaveMestra:
    def __init__(self, fabrica: FabricaDeUnidades, cifrador: Cifrador) -> None:
        self._fabrica = fabrica
        self._cifrador = cifrador

    def executar(self) -> int:
        """Devolve quantos segredos foram recifrados."""
        total = 0
        with self._fabrica.sem_tenant() as uow:
            inquilinos = uow.usuarios.inquilinos_ativos()
            for usuario_id, cifrado in uow.usuarios.com_totp():
                novo = self._cifrador.recifrar(cifrado, contexto_totp(usuario_id))
                uow.usuarios.trocar_totp(usuario_id, novo)
                total += 1
        for tenant_id in inquilinos:
            with self._fabrica.para_tenant(tenant_id) as uow:
                for conector in uow.conectores.listar():
                    if conector.credencial_cifrada is None:
                        continue
                    contexto = f"conector:{tenant_id}:{conector.tipo}"
                    novo = self._cifrador.recifrar(conector.credencial_cifrada, contexto)
                    uow.conectores.salvar(replace(conector, credencial_cifrada=novo))
                    total += 1
        return total
