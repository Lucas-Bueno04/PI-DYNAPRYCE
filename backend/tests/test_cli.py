"""Testes de fumaça da CLI montada pelo Composition Root."""

from importlib.metadata import version

from typer.testing import CliRunner

from dynaprice.principal import app

runner = CliRunner()


def test_versao_imprime_a_versao_do_pacote() -> None:
    resultado = runner.invoke(app, ["versao"])

    assert resultado.exit_code == 0
    assert resultado.output.strip() == version("dynaprice")


def test_ajuda_lista_o_grupo_lab() -> None:
    resultado = runner.invoke(app, ["--help"])

    assert resultado.exit_code == 0
    assert "lab" in resultado.output
