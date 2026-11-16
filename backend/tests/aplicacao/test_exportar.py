"""F1.28: exportação por lote e simulação mw9kw9i514upw:15 (falha na exportação)."""

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.entrada.worker import LacoDoWorker
from dynaprice.adaptadores.saida.arquivos.exportador import ExportadorCsvDeRecomendacoes
from dynaprice.adaptadores.saida.postgres import FilaPostgres
from dynaprice.aplicacao.casos_de_uso.decidir import Aprovar, DecidirRecomendacao
from dynaprice.aplicacao.casos_de_uso.exportar import (
    ExecutarExportacao,
    SolicitarExportacao,
    TentarExportarDeNovo,
)
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.aplicacao.erros import AcessoNegado, NaoEncontrado
from dynaprice.aplicacao.portas import ErroDeExportacao
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from dynaprice.dominio.modelos.fila import ParametrosDeFila
from dynaprice.dominio.modelos.recomendacao import Recomendacao
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

PARAMETROS = ParametrosDeFila(max_tentativas=2, variacao=0.0)


class ExportadorQueFalha:
    def __init__(self, falhar: bool = True) -> None:
        self.falhar = falhar
        self.chamadas = 0

    def gerar(self, recomendacoes: Sequence[Recomendacao]) -> bytes:
        self.chamadas += 1
        if self.falhar:
            raise ErroDeExportacao("disco cheio")
        return b"arquivo"


def _aprovada(preco: CenarioDePreco) -> UUID:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)
    (linha,) = preco.consulta("SELECT id FROM core.recomendacao WHERE tenant_id=%s", preco.tenant)
    DecidirRecomendacao(preco.fabrica, preco.relogio).executar(
        preco.aprovador, linha[0], 1, Aprovar()
    )
    identificador: UUID = linha[0]
    return identificador


def _lotes(preco: CenarioDePreco) -> list[tuple[object, ...]]:
    return preco.consulta(
        "SELECT id, arquivo_sha256 FROM core.lote_exportacao WHERE tenant_id=%s", preco.tenant
    )


def _estado(preco: CenarioDePreco) -> str:
    (linha,) = preco.consulta(
        "SELECT estado FROM core.recomendacao WHERE tenant_id=%s ORDER BY competencia LIMIT 1",
        preco.tenant,
    )
    return str(linha[0])


def _job(preco: CenarioDePreco) -> str:
    (linha,) = preco.consulta(
        "SELECT estado FROM job.job WHERE tenant_id=%s AND tipo='exportar'", preco.tenant
    )
    return str(linha[0])


def _laco(
    preco: CenarioDePreco, pool: ConnectionPool, exportador: ExportadorQueFalha
) -> LacoDoWorker:
    fila = FilaPostgres(pool, preco.relogio, PARAMETROS, dono="w")
    execucao = ExecutarExportacao(
        preco.fabrica, preco.relogio, exportador, PARAMETROS.max_tentativas
    )
    return LacoDoWorker(fila, {"exportar": execucao.executar}, preco.relogio)


@pytest.fixture(autouse=True)
def fila_vazia(preco: CenarioDePreco) -> None:
    import psycopg

    with psycopg.connect(preco.banco.superusuario, autocommit=True) as s:
        s.execute("DELETE FROM job.job")


def test_exportar_gera_um_arquivo_e_reajusta(preco: CenarioDePreco, pool: ConnectionPool) -> None:
    _aprovada(preco)
    SolicitarExportacao(preco.fabrica, preco.relogio).executar(preco.aprovador)
    exportador = ExportadorQueFalha(falhar=False)
    assert _laco(preco, pool, exportador).executar_um() is True
    assert _estado(preco) == "exportada"
    assert len(_lotes(preco)) == 1
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        contrato = uow.contratos.obter("C1")
    assert contrato is not None
    assert contrato.preco_vigente.valor == Decimal("502.55")


def test_exportar_o_mesmo_lote_duas_vezes_nao_gera_dois(preco: CenarioDePreco) -> None:
    _aprovada(preco)
    solicitar = SolicitarExportacao(preco.fabrica, preco.relogio)
    primeiro = solicitar.executar(preco.aprovador)
    assert solicitar.executar(preco.aprovador) == primeiro
    assert len(_lotes(preco)) == 1
    assert len(preco.consulta("SELECT 1 FROM job.job WHERE tenant_id=%s", preco.tenant)) == 1


def test_reexecutar_o_job_nao_refaz_o_arquivo(preco: CenarioDePreco) -> None:
    from uuid import uuid4

    from dynaprice.aplicacao.portas import JobReservado

    _aprovada(preco)
    lote = SolicitarExportacao(preco.fabrica, preco.relogio).executar(preco.aprovador)
    exportador = ExportadorQueFalha(falhar=False)
    execucao = ExecutarExportacao(preco.fabrica, preco.relogio, exportador, 2)
    job = JobReservado(uuid4(), preco.tenant, "exportar", {"lote_id": str(lote)}, 1)
    execucao.executar(job)
    execucao.executar(job)
    assert exportador.chamadas == 1
    assert preco.consulta(
        "SELECT count(*) FROM audit.evento WHERE tenant_id=%s AND tipo='lote_exportado'",
        preco.tenant,
    ) == [(1,)]


def test_sem_aprovadas_nao_cria_lote(preco: CenarioDePreco) -> None:
    assert SolicitarExportacao(preco.fabrica, preco.relogio).executar(preco.aprovador) is None
    assert _lotes(preco) == []


def test_exportar_exige_aprovar_com_totp(preco: CenarioDePreco) -> None:
    sem_mfa = Principal(preco.aprovador.usuario_id, preco.tenant, frozenset({Papel.APROVAR}), False)
    with pytest.raises(AcessoNegado):
        SolicitarExportacao(preco.fabrica, preco.relogio).executar(sem_mfa)


def test_nova_tentativa_em_lote_de_outro_inquilino_nao_existe(preco: CenarioDePreco) -> None:
    from uuid import uuid4

    with pytest.raises(NaoEncontrado):
        TentarExportarDeNovo(preco.fabrica, preco.relogio).executar(preco.aprovador, uuid4())


class TestSimulacaoFalhaNaExportacao:
    """Simulação mw9kw9i514upw:15, passo a passo."""

    def test_cinco_passos(self, preco: CenarioDePreco, pool: ConnectionPool) -> None:
        # Passo 1: aprovada aguardando lote.
        _aprovada(preco)
        assert _estado(preco) == "aprovada"
        lote = SolicitarExportacao(preco.fabrica, preco.relogio).executar(preco.aprovador)
        # Passo 2: geração falha; o job volta à fila e nenhum arquivo é gravado.
        falha = ExportadorQueFalha()
        _laco(preco, pool, falha).executar_um()
        assert _job(preco) == "pendente"
        assert _lotes(preco)[0][1] is None
        # Passo 3: tentativas esgotadas.
        preco.relogio.avancar(3600)
        _laco(preco, pool, falha).executar_um()
        assert _estado(preco) == "falha_exportacao"
        assert _job(preco) == "falhou"
        assert ("exportacao_falhou",) in preco.consulta(
            "SELECT tipo FROM core.alerta WHERE tenant_id=%s", preco.tenant
        )
        # Passo 4: a recalibração seguinte não mexe nela.
        resumo = Recalibrar(preco.fabrica, preco.relogio).executar(
            preco.tenant, Competencia(2028, 1)
        )
        assert resumo.recomendacoes == 0
        assert resumo.pulados == ("C1",)
        assert _estado(preco) == "falha_exportacao"
        # Passo 5: nova tentativa manual reaproveita o lote.
        assert lote is not None
        TentarExportarDeNovo(preco.fabrica, preco.relogio).executar(preco.aprovador, lote)
        preco.relogio.avancar(1)
        _laco(preco, pool, ExportadorQueFalha(falhar=False)).executar_um()
        assert _estado(preco) == "exportada"
        lotes = _lotes(preco)
        assert len(lotes) == 1
        assert lotes[0][0] == lote
        assert lotes[0][1] is not None


def test_arquivo_csv_tem_decimal_e_neutraliza_formula() -> None:
    from uuid import uuid4

    from dynaprice.dominio.modelos import Dinheiro

    rec = Recomendacao(
        id=uuid4(),
        contrato_id="=HYPERLINK()",
        preco_alvo_id=uuid4(),
        politica_versao=1,
        competencia=Competencia(2027, 1),
        efeito=Competencia(2027, 3),
        preco_vigente=Dinheiro.de(437),
        preco_proposto=Dinheiro.de("502.55"),
        trajetoria=(Dinheiro.de("502.55"),),
    )
    texto = ExportadorCsvDeRecomendacoes().gerar([rec]).decode("utf-8-sig")
    linhas = texto.strip().splitlines()
    assert linhas[0].split(";") == ["contrato", "competencia_efeito", "valor"]
    assert linhas[1] == "'=HYPERLINK();2027-03;502,55"
