"""F0.6: exportação determinística em CSV (reprodutível byte a byte) e comando da CLI."""

import hashlib
from pathlib import Path

from typer.testing import CliRunner

from dynaprice.adaptadores.saida.arquivos import EscritorDeCarteiraCsv
from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.aplicacao.casos_de_uso import ExportarCarteira
from dynaprice.principal import app
from tests.sintetico.conftest import FIM, INICIO

ARQUIVOS = {
    "empresas.csv",
    "contratos.csv",
    "vinculos.csv",
    "direcionadores.csv",
    "horas.csv",
    "honorarios.csv",
}


def _hashes(pasta: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pasta.iterdir())}


def _exportar(semente: int, pasta: Path) -> None:
    fonte = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=semente, contratos=80))
    ExportarCarteira(fonte, EscritorDeCarteiraCsv(pasta)).executar(INICIO, FIM)


def test_mesma_semente_gera_arquivos_identicos_byte_a_byte(tmp_path: Path) -> None:
    _exportar(42, tmp_path / "a")
    _exportar(42, tmp_path / "b")
    assert set(_hashes(tmp_path / "a")) == ARQUIVOS
    assert _hashes(tmp_path / "a") == _hashes(tmp_path / "b")


def test_semente_diferente_muda_os_arquivos(tmp_path: Path) -> None:
    _exportar(1, tmp_path / "a")
    _exportar(2, tmp_path / "b")
    assert _hashes(tmp_path / "a") != _hashes(tmp_path / "b")


def test_cabecalho_e_decimal_com_ponto(tmp_path: Path) -> None:
    _exportar(3, tmp_path)
    linhas = (tmp_path / "honorarios.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "contrato_id,competencia,valor"
    assert all(len(linha.split(",")[2].split(".")[1]) == 2 for linha in linhas[1:])


def test_resumo_do_caso_de_uso(tmp_path: Path) -> None:
    fonte = GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=5, contratos=30))
    resumo = ExportarCarteira(fonte, EscritorDeCarteiraCsv(tmp_path)).executar(INICIO, FIM)
    assert resumo.contratos == 30
    assert resumo.empresas >= 30


def test_cli_lab_sintetico(tmp_path: Path) -> None:
    saida = tmp_path / "sintetico-42"
    argumentos = ["lab", "sintetico", "--semente", "42", "--contratos", "50"]
    resultado = CliRunner().invoke(app, [*argumentos, "--saida", str(saida)])
    assert resultado.exit_code == 0, resultado.output
    assert set(_hashes(saida)) == ARQUIVOS
    assert "50 contratos" in resultado.output
