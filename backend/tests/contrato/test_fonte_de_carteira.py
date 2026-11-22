"""Teste de contrato da porta FonteDeCarteira (Liskov, principios.md §3).

Os mesmos testes rodam em todas as implementações: gerador sintético e leitor de CSV
(e, nos passos seguintes, planilha e Domínio).
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from dynaprice.adaptadores.saida.arquivos import EscritorDeCarteiraCsv, LeitorDeCarteiraCsv
from dynaprice.adaptadores.saida.planilha import LeitorDePlanilhaDoEscritorio, Pseudonimizador
from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.aplicacao.portas import FonteDeCarteira
from dynaprice.dominio.modelos import Competencia, ValorInvalido
from tests.adaptadores.planilha_exemplo import escrever_planilha

INICIO, FIM = Competencia(2025, 1), Competencia(2025, 12)
type Fabrica = Callable[[Path], FonteDeCarteira]


def _sintetica(_: Path) -> FonteDeCarteira:
    return GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=9, contratos=40))


def _csv(pasta: Path) -> FonteDeCarteira:
    EscritorDeCarteiraCsv(pasta).escrever(_sintetica(pasta).extrair(INICIO, FIM))
    return LeitorDeCarteiraCsv(pasta)


def _planilha(pasta: Path) -> FonteDeCarteira:
    escrever_planilha(_sintetica(pasta).extrair(INICIO, FIM), pasta)
    return LeitorDePlanilhaDoEscritorio(pasta, Pseudonimizador(b"chave-de-teste-de-contrato-123"))


@pytest.fixture(params=[_sintetica, _csv, _planilha], ids=["sintetica", "csv", "planilha"])
def fonte(request: pytest.FixtureRequest, tmp_path: Path) -> FonteDeCarteira:
    fabrica: Fabrica = request.param
    return fabrica(tmp_path)


def test_fatos_ficam_na_janela_pedida(fonte: FonteDeCarteira) -> None:
    carteira = fonte.extrair(Competencia(2025, 4), Competencia(2025, 6))
    meses = {d.competencia for d in carteira.direcionadores} | {
        h.competencia for h in carteira.horas
    }
    assert meses and all(Competencia(2025, 4) <= m <= Competencia(2025, 6) for m in meses)
    assert all(
        Competencia(2025, 4) <= h.competencia <= Competencia(2025, 6) for h in carteira.honorarios
    )


def test_referencias_consistentes(fonte: FonteDeCarteira) -> None:
    carteira = fonte.extrair(INICIO, FIM)
    empresas = {e.id for e in carteira.empresas}
    contratos = {c.id for c in carteira.contratos}
    assert {v.empresa_id for v in carteira.vinculos} <= empresas
    assert {v.contrato_id for v in carteira.vinculos} <= contratos
    assert {h.empresa_id for h in carteira.horas} <= empresas
    assert {h.contrato_id for h in carteira.honorarios} <= contratos


def test_janela_invertida_e_recusada(fonte: FonteDeCarteira) -> None:
    with pytest.raises(ValorInvalido):
        fonte.extrair(FIM, INICIO)


def test_csv_reproduz_a_carteira_escrita(tmp_path: Path) -> None:
    original = _sintetica(tmp_path).extrair(INICIO, FIM)
    EscritorDeCarteiraCsv(tmp_path).escrever(original)
    assert LeitorDeCarteiraCsv(tmp_path).extrair(INICIO, FIM) == original


def test_csv_pasta_inexistente(tmp_path: Path) -> None:
    with pytest.raises(ValorInvalido):
        LeitorDeCarteiraCsv(tmp_path / "nada").extrair(INICIO, FIM)
