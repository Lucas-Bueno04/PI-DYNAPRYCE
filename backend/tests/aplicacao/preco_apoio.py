"""Cenário de preço: contrato da Tabela 7 no banco, política publicada e relógio fixo."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres
from dynaprice.dominio.modelos import (
    Competencia,
    Contrato,
    Dinheiro,
    Direcionadores,
    Empresa,
    Regime,
    Vinculo,
)
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.conftest import Banco
from tests.dominio.modelos.documentos import documento_tabela_7
from tests.fakes import RelogioFixo

MES = {"notas_entrada": Decimal(30), "lancamentos_manuais": Decimal(40), "empregados": Decimal(2)}
REFERENCIA = Competencia(2027, 1)


@dataclass
class CenarioDePreco:
    fabrica: FabricaDeUnidadesPostgres
    relogio: RelogioFixo
    tenant: UUID
    banco: Banco

    @property
    def aprovador(self) -> Principal:
        return Principal(uuid4(), self.tenant, frozenset({Papel.APROVAR}), mfa_verificado=True)

    def publicar_politica(self, documento: dict[str, Any] | None = None) -> int:
        with self.fabrica.para_tenant(self.tenant) as uow:
            versao = uow.politicas.salvar_rascunho(documento or documento_tabela_7())
            uow.politicas.publicar(versao, self.aprovador.usuario_id, self.relogio.agora())
        return versao

    def contrato_tabela_7(
        self,
        contrato_id: str = "C1",
        mes_reajuste: int | None = 3,
        meses: int = 12,
        provisorio: bool = False,
        vigente: str = "437",
    ) -> str:
        empresa = f"E-{contrato_id}"
        with self.fabrica.para_tenant(self.tenant) as uow:
            uow.contratos.salvar(
                Contrato(
                    contrato_id,
                    Dinheiro.de(vigente),
                    mes_reajuste=mes_reajuste,
                    provisorio=provisorio,
                )
            )
            uow.empresas.salvar(Empresa(empresa, Regime.LP))
            uow.vinculos.salvar(Vinculo(empresa, contrato_id, Competencia(2020, 1), principal=True))
            for i in range(meses):
                registro = Direcionadores(empresa, REFERENCIA.somar(-i), MES)
                uow.fatos.gravar_empresa_mes(registro, {}, 1, Regime.LP)
        return contrato_id

    def consulta(self, sql: str, *args: object) -> list[tuple[Any, ...]]:
        with psycopg.connect(self.banco.superusuario) as s:
            return s.execute(sql.encode(), args).fetchall()


@pytest.fixture
def preco(pool: ConnectionPool, novo_tenant: UUID, banco: Banco) -> CenarioDePreco:
    relogio = RelogioFixo()
    return CenarioDePreco(FabricaDeUnidadesPostgres(pool, relogio), relogio, novo_tenant, banco)
