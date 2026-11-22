"""F1.31: simulação mw9kw9i514upw:7 ponta a ponta, com banco, decisão, auditoria e arquivo."""

from decimal import Decimal
from uuid import UUID, uuid4

from dynaprice.adaptadores.saida.arquivos.exportador import ExportadorCsvDeRecomendacoes
from dynaprice.aplicacao.casos_de_uso.decidir import Aprovar, DecidirRecomendacao
from dynaprice.aplicacao.casos_de_uso.exportar import ExecutarExportacao, SolicitarExportacao
from dynaprice.aplicacao.casos_de_uso.recalcular import RecalcularPrecoAlvo
from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.aplicacao.portas import JobReservado
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco


def test_sim_mw9kw9i514upw_7_tabela_7_ponta_a_ponta(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()

    # Passos 1 a 6: recalibração gera recomendação PENDENTE com a trajetória exata.
    resumo = Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)
    assert resumo.recomendacoes == 1
    (linha,) = preco.consulta(
        """SELECT r.id, r.estado, r.preco_proposto, r.trajetoria, a.preco_alvo, a.id
           FROM core.recomendacao r JOIN core.preco_alvo a
             ON a.tenant_id = r.tenant_id AND a.id = r.preco_alvo_id
           WHERE r.tenant_id = %s""",
        preco.tenant,
    )
    recomendacao: UUID = linha[0]
    assert linha[1] == "pendente"
    assert linha[3] == ["502.55", "577.93", "614.27"]
    assert linha[4] == Decimal("614.27")

    # Passo 7: o gestor aprova, a auditoria encadeia e o arquivo é gerado.
    DecidirRecomendacao(preco.fabrica, preco.relogio).executar(
        preco.aprovador, recomendacao, 1, Aprovar()
    )
    lote = SolicitarExportacao(preco.fabrica, preco.relogio).executar(preco.aprovador)
    assert lote is not None
    ExecutarExportacao(preco.fabrica, preco.relogio, ExportadorCsvDeRecomendacoes(), 5).executar(
        JobReservado(uuid4(), preco.tenant, "exportar", {"lote_id": str(lote)}, 1)
    )

    with preco.fabrica.para_tenant(preco.tenant) as uow:
        arquivo = uow.lotes.arquivo(lote)
        assert uow.auditoria.primeira_quebra() is None
        contrato = uow.contratos.obter("C1")
    assert arquivo is not None
    assert "C1;2027-03;502,55" in arquivo.decode("utf-8-sig")
    assert contrato is not None
    assert contrato.preco_vigente.valor == Decimal("502.55")

    # Reprodução ao centavo a partir das entradas gravadas.
    comparacao = RecalcularPrecoAlvo(preco.fabrica).executar(preco.tenant, linha[5])
    assert comparacao.gravado == comparacao.recalculado == Decimal("614.27")
