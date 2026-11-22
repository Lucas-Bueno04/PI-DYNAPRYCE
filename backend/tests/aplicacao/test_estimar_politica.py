"""F1.30: estimação anual e simulação mw9kw9i514upw:17 (portão de aceite reprovado)."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from dynaprice.aplicacao.casos_de_uso.estimar import EstimarPolitica
from dynaprice.aplicacao.casos_de_uso.politicas import PublicarPolitica
from dynaprice.aplicacao.erros import Conflito
from dynaprice.aplicacao.portas import EstimativaDePolitica, JobReservado
from dynaprice.dominio.estimacao.anual import EstimadorAnual, portao_de_aceite
from dynaprice.dominio.modelos import Carteira, PoliticaVersao
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco
from tests.dominio.modelos.documentos import documento_tabela_7


class EstimadorDeTeste:
    def __init__(self, aceito: bool) -> None:
        self.aceito = aceito
        self.vigente: PoliticaVersao | None = None

    def estimar(
        self, carteira: Carteira, referencia: Any, vigente: PoliticaVersao | None
    ) -> EstimativaDePolitica:
        self.vigente = vigente
        relatorio: Mapping[str, Any] = {"portao": "aprovado" if self.aceito else "reprovado"}
        return EstimativaDePolitica(documento_tabela_7(), self.aceito, relatorio)


def _job(preco: CenarioDePreco) -> JobReservado:
    return JobReservado(uuid4(), preco.tenant, "estimar_politica", {"ano": 2026}, 1)


class TestSimulacaoPortaoReprovado:
    """Simulação mw9kw9i514upw:17; o passo 2 usa estimador de teste, e o portão real abaixo."""

    def test_quatro_passos(self, preco: CenarioDePreco) -> None:
        vigente = preco.publicar_politica()
        # Passos 1 e 2: estimação anual com erro fora da amostra pior.
        estimador = EstimadorDeTeste(aceito=False)
        EstimarPolitica(preco.fabrica, estimador).executar(_job(preco))
        assert estimador.vigente is not None
        # Passo 3: fica como rascunho marcado; nada é publicado.
        (linha,) = preco.consulta(
            "SELECT versao, estado, portao_aceite, relatorio FROM core.politica_versao "
            "WHERE tenant_id=%s AND versao<>%s",
            preco.tenant,
            vigente,
        )
        assert linha[1:3] == ("rascunho", False)
        assert linha[3]["portao"] == "reprovado"
        # Passo 4: publicar é recusado e a vigente não muda.
        with pytest.raises(Conflito):
            PublicarPolitica(preco.fabrica, preco.relogio).executar(preco.aprovador, linha[0])
        with preco.fabrica.para_tenant(preco.tenant) as uow:
            assert uow.politicas.versao_publicada() == vigente


def test_job_so_gera_rascunho(preco: CenarioDePreco) -> None:
    EstimarPolitica(preco.fabrica, EstimadorDeTeste(aceito=True)).executar(_job(preco))
    assert preco.consulta(
        "SELECT estado FROM core.politica_versao WHERE tenant_id=%s", preco.tenant
    ) == [("rascunho",)]


def test_repetir_o_job_nao_duplica_o_rascunho(preco: CenarioDePreco) -> None:
    estimar = EstimarPolitica(preco.fabrica, EstimadorDeTeste(aceito=True))
    estimar.executar(_job(preco))
    estimar.executar(_job(preco))
    assert (
        len(preco.consulta("SELECT 1 FROM core.politica_versao WHERE tenant_id=%s", preco.tenant))
        == 1
    )


@pytest.mark.parametrize(
    ("novo", "vigente", "esperado"),
    [
        (Decimal("1.00"), Decimal("1.00"), True),
        (Decimal("1.05"), Decimal("1.00"), True),
        (Decimal("1.06"), Decimal("1.00"), False),
        (Decimal("0.50"), None, True),
    ],
)
def test_portao_compara_o_erro_fora_da_amostra(
    novo: Decimal, vigente: Decimal | None, esperado: bool
) -> None:
    assert portao_de_aceite(novo, vigente, betas_validos=True) is esperado


def test_portao_sem_vigente_exige_betas_validos() -> None:
    assert portao_de_aceite(Decimal("0.5"), None, betas_validos=False) is False


def test_estimador_real_sem_vigente_aprova_carteira_sintetica(carteira: Carteira) -> None:
    from dynaprice.dominio.modelos import Competencia

    resultado = EstimadorAnual(semente=7).estimar(carteira, Competencia(2025, 12), None)
    assert resultado.portao_aceite is True
    assert resultado.documento["tarifa_hora_padrao"]["origem"] == "preco_revelado"
    assert Decimal(resultado.relatorio["eam_novo"]) > 0


def test_estimador_real_reprova_quando_a_vigente_e_melhor(carteira: Carteira) -> None:
    """Com a amostra de ajuste reduzida a quase nada, a equação nova perde para a vigente."""
    from dynaprice.dominio.modelos import Competencia, fabricar_politica

    referencia = Competencia(2025, 12)
    boa = EstimadorAnual(semente=7).estimar(carteira, referencia, None)
    vigente = fabricar_politica(boa.documento)
    pequeno = EstimadorAnual(semente=7, fracao_de_ajuste=0.03)
    resultado = pequeno.estimar(carteira, referencia, vigente)
    assert resultado.portao_aceite is False
    assert Decimal(resultado.relatorio["eam_novo"]) > Decimal(resultado.relatorio["eam_vigente"])
