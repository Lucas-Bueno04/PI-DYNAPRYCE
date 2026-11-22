"""Aceite F0.19: `dynaprice lab relatorio` na carteira sintética, com a fonte de cada número."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dynaprice.adaptadores.saida.arquivos import LeitorDeCarteiraCsv
from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.dominio.estimacao.diagnostico import AnalisadorDoLaboratorio
from dynaprice.dominio.modelos import Competencia, Relatorio, fabricar_politica
from dynaprice.principal import app

SECOES = (
    "Carteira",
    "Curva preço × esforço",
    "Concentração (Lorenz e Gini)",
    "Desalinhamento entre preço e esforço",
    "Equações de tempo (Huber)",
    "Modelo de esforço (Ridge)",
    "Pisos propostos por regime (D2)",
    "Tarifa (D3)",
    "Sensibilidade de θ e δ (D4)",
    "Credibilidade s²/v²",
    "Validação por ocultação (EPAM)",
    "Contratos mistos (D1)",
    "Mudanças de regime na janela (D13)",
    "Dias de fechamento (D10)",
)
REF = Competencia(2025, 12)


@pytest.fixture(scope="module")
def relatorio() -> Relatorio:
    carteira = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=42)).extrair(
        Competencia(2025, 1), REF
    )
    return AnalisadorDoLaboratorio().analisar(carteira, REF)


def test_todas_as_secoes_e_a_fonte_de_cada_numero(relatorio: Relatorio) -> None:
    assert tuple(s.titulo for s in relatorio.secoes) == SECOES
    for secao in relatorio.secoes:
        assert secao.itens or secao.tabelas, secao.titulo
        assert all(i.fonte.strip() for i in secao.itens), secao.titulo
        assert all(t.fonte.strip() for t in secao.tabelas), secao.titulo


def test_numeros_na_forma_do_artigo(relatorio: Relatorio) -> None:
    tarifa = {i.rotulo: i.valor for i in relatorio.secao("Tarifa (D3)").itens}
    tau = Decimal(tarifa["τ̂ (preço revelado)"].replace(".", "").replace(",", "."))
    assert Decimal(80) <= tau <= Decimal(130)
    curva = {i.rotulo: i.valor for i in relatorio.secao("Curva preço × esforço").itens}
    assert "b" in curva and "a" in curva


def test_anexo_e_um_rascunho_de_politica_valido(relatorio: Relatorio) -> None:
    documento = json.loads(relatorio.anexos["politica_rascunho.json"], parse_float=Decimal)
    politica = fabricar_politica(documento)
    assert politica.tarifa.valor > 0
    assert len(politica.equacoes) == 3


def test_cli_lab_relatorio(tmp_path: Path) -> None:
    entrada, saida = tmp_path / "sintetico-42", tmp_path / "relatorio"
    runner = CliRunner()
    gerar = runner.invoke(
        app, ["lab", "sintetico", "--semente", "42", "--contratos", "60", "--saida", str(entrada)]
    )
    assert gerar.exit_code == 0, gerar.output
    assert LeitorDeCarteiraCsv(entrada).extrair(Competencia(2025, 1), REF).contratos
    resultado = runner.invoke(
        app, ["lab", "relatorio", "--entrada", str(entrada), "--saida", str(saida)]
    )
    assert resultado.exit_code == 0, resultado.output
    texto = (saida / "relatorio.md").read_text(encoding="utf-8")
    assert all(f"## {titulo}" in texto for titulo in SECOES)
    assert (saida / "politica_rascunho.json").exists()


def test_ocultacao_registra_epam_por_estimador(relatorio: Relatorio) -> None:
    secao = relatorio.secao("Validação por ocultação (EPAM)")
    (tabela,) = secao.tabelas
    nomes = {linha[0] for linha in tabela.linhas}
    assert {"piso_regime", "credibilidade", "vizinhos_k3", "credibilidade_com_vizinhos_k3"} <= nomes
    assert all(valor.endswith("%") for linha in tabela.linhas for valor in linha[1:])
    assert any(i.rotulo == "Contratos avaliados" and int(i.valor) >= 10 for i in secao.itens)
