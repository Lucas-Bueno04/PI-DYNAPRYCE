"""F1.22: importação por planilha, raw versionado, quarentena e conectores sem vazar credencial."""

from uuid import uuid4

import pytest

from dynaprice.adaptadores.saida.planilha import Pseudonimizador
from dynaprice.adaptadores.saida.planilha.upload import LeitorDeArquivoEnviado, LimitesDeUpload
from dynaprice.adaptadores.saida.seguranca import CifradorAesGcm
from dynaprice.aplicacao.casos_de_uso.conectores import ConfigurarConector, ListarConectores
from dynaprice.aplicacao.casos_de_uso.importar import ImportarPlanilha
from dynaprice.aplicacao.erros import AcessoNegado
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.adaptadores.test_planilha import ABAS, planilha
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

INICIO, FIM = Competencia(2026, 1), Competencia(2026, 12)
CIFRADOR = CifradorAesGcm({"k1": bytes(range(32))})


def _analista(preco: CenarioDePreco) -> Principal:
    return Principal(uuid4(), preco.tenant, frozenset({Papel.ANALISAR}), False)


def _admin(preco: CenarioDePreco) -> Principal:
    return Principal(uuid4(), preco.tenant, frozenset({Papel.ADMINISTRAR}), True)


def _importar(preco: CenarioDePreco, conteudo: bytes):  # type: ignore[no-untyped-def]
    leitor = LeitorDeArquivoEnviado(Pseudonimizador(b"chave-de-teste-com-16+"), LimitesDeUpload())
    return ImportarPlanilha(preco.fabrica, preco.relogio, leitor).executar(
        _analista(preco), "carga.xlsx", conteudo, INICIO, FIM
    )


def _extracoes(preco: CenarioDePreco) -> list[tuple[object, ...]]:
    return preco.consulta(
        "SELECT versao, origem, substituida FROM raw.extracao WHERE tenant_id=%s ORDER BY versao",
        preco.tenant,
    )


def test_importar_grava_raw_e_fatos(preco: CenarioDePreco) -> None:
    resultado = _importar(preco, planilha())
    assert (resultado.versao, resultado.repetida) == (1, False)
    assert _extracoes(preco) == [(1, "planilha", False)]
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        assert [c.id for c in uow.contratos.listar()] == ["C1"]
        assert len(uow.fatos.direcionadores_do_regime_atual(INICIO, FIM)) == 1


def test_raw_nao_contem_o_documento(preco: CenarioDePreco) -> None:
    _importar(preco, planilha())
    (linha,) = preco.consulta(
        "SELECT conteudo::text FROM raw.extracao WHERE tenant_id=%s", preco.tenant
    )
    assert '"11"' not in linha[0]


def test_reimportar_o_mesmo_arquivo_nao_duplica(preco: CenarioDePreco) -> None:
    conteudo = planilha()
    _importar(preco, conteudo)
    assert _importar(preco, conteudo).repetida is True
    assert len(_extracoes(preco)) == 1


def test_arquivo_alterado_vira_nova_versao(preco: CenarioDePreco) -> None:
    _importar(preco, planilha())
    alterado = planilha(
        {"honorarios": [["contrato", "competencia", "valor"], ["C1", "2026-01", "500,00"]]}
    )
    assert _importar(preco, alterado).versao == 2
    assert _extracoes(preco) == [(1, "planilha", True), (2, "planilha", False)]


def test_reimportar_nao_troca_o_preco_de_contrato_existente(preco: CenarioDePreco) -> None:
    _importar(preco, planilha())
    alterado = planilha({"contratos": [ABAS["contratos"][0], ["C1", "999,00", 3, "N", ""]]})
    _importar(preco, alterado)
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        contrato = uow.contratos.obter("C1")
    assert contrato is not None
    assert str(contrato.preco_vigente) == "437.00"


def test_linhas_invalidas_vao_para_quarentena(preco: CenarioDePreco) -> None:
    ruim = planilha(
        {"contratos": [ABAS["contratos"][0], ABAS["contratos"][1], ["C2", "xx", 3, "N", ""]]}
    )
    assert _importar(preco, ruim).quarentena == 1
    (linha,) = preco.consulta(
        "SELECT linha, motivo FROM raw.quarentena WHERE tenant_id=%s", preco.tenant
    )
    assert linha[0] == {"arquivo": "contratos.csv", "linha": 2}


def test_referencia_a_empresa_rejeitada_vai_para_quarentena(preco: CenarioDePreco) -> None:
    ruim = planilha(
        {"vinculos": [ABAS["vinculos"][0], ABAS["vinculos"][1], ["99", "C1", "2025-01", "", "N"]]}
    )
    assert _importar(preco, ruim).quarentena == 1


def test_importar_agenda_conciliacao_e_recalibracao(preco: CenarioDePreco) -> None:
    _importar(preco, planilha())
    tipos = preco.consulta(
        "SELECT tipo FROM job.job WHERE tenant_id=%s ORDER BY tipo", preco.tenant
    )
    assert tipos == [("conciliar",), ("recalibrar",)]


def test_importar_e_auditado(preco: CenarioDePreco) -> None:
    _importar(preco, planilha())
    assert ("carteira_importada",) in preco.consulta(
        "SELECT tipo FROM audit.evento WHERE tenant_id=%s", preco.tenant
    )


def test_importar_exige_papel(preco: CenarioDePreco) -> None:
    leitor = LeitorDeArquivoEnviado(Pseudonimizador(b"chave-de-teste-com-16+"), LimitesDeUpload())
    aprovador = Principal(uuid4(), preco.tenant, frozenset({Papel.APROVAR}), True)
    with pytest.raises(AcessoNegado):
        ImportarPlanilha(preco.fabrica, preco.relogio, leitor).executar(
            aprovador, "c.xlsx", planilha(), INICIO, FIM
        )


def test_credencial_de_conector_e_cifrada_e_nao_volta(preco: CenarioDePreco) -> None:
    ConfigurarConector(preco.fabrica, CIFRADOR).executar(
        _admin(preco), "omie", {"app_secret": "segredo-do-omie"}, {"url": "x"}, 5
    )
    (linha,) = preco.consulta(
        "SELECT credencial_cifrada FROM core.conector_config WHERE tenant_id=%s", preco.tenant
    )
    assert b"segredo-do-omie" not in bytes(linha[0])
    resposta = ListarConectores(preco.fabrica).executar(_admin(preco))
    assert "segredo-do-omie" not in repr(resposta)
    assert [c.tipo for c in resposta] == ["omie"]


def test_agendamento_extrai_a_competencia_fechada(preco: CenarioDePreco) -> None:
    from datetime import UTC, datetime

    from dynaprice.aplicacao.casos_de_uso.conectores import AgendarCiclo

    ConfigurarConector(preco.fabrica, CIFRADOR).executar(_admin(preco), "omie", {"k": "v"}, {}, 5)
    preco.relogio.instante = datetime(2027, 3, 4, 12, tzinfo=UTC)
    AgendarCiclo(preco.fabrica, preco.relogio).executar(preco.tenant)
    assert preco.consulta(
        "SELECT count(*) FROM job.job WHERE tenant_id=%s AND tipo='extrair'", preco.tenant
    ) == [(0,)]
    preco.relogio.instante = datetime(2027, 3, 6, 12, tzinfo=UTC)
    AgendarCiclo(preco.fabrica, preco.relogio).executar(preco.tenant)
    AgendarCiclo(preco.fabrica, preco.relogio).executar(preco.tenant)
    assert preco.consulta(
        "SELECT chave_idempotencia FROM job.job WHERE tenant_id=%s AND tipo='extrair'",
        preco.tenant,
    ) == [("extrair:omie:2027-02",)]


def test_em_janeiro_agenda_a_estimacao_anual(preco: CenarioDePreco) -> None:
    from datetime import UTC, datetime

    from dynaprice.aplicacao.casos_de_uso.conectores import AgendarCiclo

    preco.relogio.instante = datetime(2027, 1, 20, 12, tzinfo=UTC)
    AgendarCiclo(preco.fabrica, preco.relogio).executar(preco.tenant)
    assert preco.consulta(
        "SELECT tipo, parametros FROM job.job WHERE tenant_id=%s AND tipo='estimar_politica'",
        preco.tenant,
    ) == [("estimar_politica", {"ano": 2026})]


def _testar(preco: CenarioDePreco, fonte: object) -> str:
    from dynaprice.aplicacao.casos_de_uso.conectores import TestarConector

    ConfigurarConector(preco.fabrica, CIFRADOR).executar(_admin(preco), "x", {"k": "v"}, {}, 5)
    fontes = {"x": lambda _c, _p: fonte}
    caso = TestarConector(preco.fabrica, preco.relogio, CIFRADOR, fontes)  # type: ignore[arg-type]
    return caso.executar(_admin(preco), "x").situacao


class _Fonte:
    def __init__(self, erro: Exception | None = None) -> None:
        self.erro = erro

    def extrair(self, inicio: Competencia, fim: Competencia) -> object:
        if self.erro:
            raise self.erro
        return object()


def test_testar_conexao_ok(preco: CenarioDePreco) -> None:
    assert _testar(preco, _Fonte()) == "ok"


def test_testar_conexao_indisponivel(preco: CenarioDePreco) -> None:
    from dynaprice.aplicacao.portas import ConectorIndisponivel

    assert _testar(preco, _Fonte(ConectorIndisponivel("x"))) == "indisponivel"


def test_testar_conexao_credencial(preco: CenarioDePreco) -> None:
    from dynaprice.aplicacao.portas import CredencialInvalida

    assert _testar(preco, _Fonte(CredencialInvalida("x"))) == "credencial_invalida"
