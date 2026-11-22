"""F1.30: diagnóstico sobre a carteira gravada, pela mesma análise do laboratório."""

from uuid import uuid4

import pytest

from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.aplicacao.casos_de_uso.diagnostico import ConsultarDiagnostico
from dynaprice.aplicacao.casos_de_uso.importar import gravar_carteira
from dynaprice.aplicacao.erros import AcessoNegado
from dynaprice.dominio.estimacao.diagnostico import AnalisadorDoLaboratorio
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

INICIO, FIM = Competencia(2025, 1), Competencia(2025, 12)


def test_mesmas_secoes_e_numeros_do_relatorio_da_cli(preco: CenarioDePreco) -> None:
    carteira = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=42, contratos=60)).extrair(
        INICIO, FIM
    )
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        gravar_carteira(uow, carteira, 1)
    analisador = AnalisadorDoLaboratorio()
    principal = Principal(uuid4(), preco.tenant, frozenset({Papel.ANALISAR}), False)
    relatorio = ConsultarDiagnostico(preco.fabrica, analisador).executar(principal, FIM)
    direto = analisador.analisar(carteira, FIM)
    assert [s.titulo for s in relatorio.secoes] == [s.titulo for s in direto.secoes]
    assert relatorio.anexos.keys() == direto.anexos.keys()
    assert relatorio.secoes[0] == direto.secoes[0]


def test_diagnostico_exige_papel(preco: CenarioDePreco) -> None:
    sem_papel = Principal(uuid4(), preco.tenant, frozenset(), False)
    with pytest.raises(AcessoNegado):
        ConsultarDiagnostico(preco.fabrica, AnalisadorDoLaboratorio()).executar(sem_papel, FIM)
