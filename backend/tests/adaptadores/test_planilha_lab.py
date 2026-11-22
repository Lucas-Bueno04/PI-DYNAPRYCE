"""F0.20: leitor da planilha do escritório com minimização e pseudonimização na entrada (D8)."""

from pathlib import Path

import pytest

from dynaprice.adaptadores.saida.planilha import LeitorDePlanilhaDoEscritorio, Pseudonimizador
from dynaprice.adaptadores.saida.sintetico import GeradorDeCarteiraSintetica, ParametrosSinteticos
from dynaprice.dominio.modelos import Carteira, Competencia, ValorInvalido
from tests.adaptadores.planilha_exemplo import documento_falso, escrever_planilha

INICIO, FIM = Competencia(2025, 1), Competencia(2025, 12)
CHAVE = b"chave-de-teste-nao-usar-em-producao"


@pytest.fixture
def original() -> Carteira:
    return GeradorDeCarteiraSintetica(ParametrosSinteticos(semente=4, contratos=30)).extrair(
        INICIO, FIM
    )


@pytest.fixture
def lida(original: Carteira, tmp_path: Path) -> Carteira:
    escrever_planilha(original, tmp_path)
    return LeitorDePlanilhaDoEscritorio(tmp_path, Pseudonimizador(CHAVE)).extrair(INICIO, FIM)


def test_pseudonimo_estavel_e_independente_da_mascara() -> None:
    p = Pseudonimizador(CHAVE)
    assert p.pseudonimo("12.345.678/0001-90") == p.pseudonimo("12345678000190")
    assert p.pseudonimo("12345678000190") != Pseudonimizador(
        b"outra-chave-qualquer-123"
    ).pseudonimo("12345678000190")
    assert p.pseudonimo("12345678000190").startswith("P")
    assert "12345678" not in p.pseudonimo("12345678000190")


def test_chave_curta_e_recusada() -> None:
    with pytest.raises(ValorInvalido):
        Pseudonimizador(b"curta")


def test_documento_nunca_chega_a_carteira(original: Carteira, lida: Carteira) -> None:
    documentos = {documento_falso(e.id) for e in original.empresas}
    digitos = {"".join(c for c in d if c.isdigit()) for d in documentos}
    texto = repr(lida)
    assert not any(d in texto for d in documentos | digitos)


def test_campos_proibidos_nunca_chegam(lida: Carteira) -> None:
    texto = repr(lida)
    assert "Fulano" not in texto and "Maria Souza" not in texto


def test_estrutura_preservada(original: Carteira, lida: Carteira) -> None:
    assert len(lida.empresas) == len(original.empresas)
    assert [c.id for c in lida.contratos] == [c.id for c in original.contratos]
    assert len(lida.vinculos) == len(original.vinculos)
    assert sum(h.horas.valor for h in lida.horas) == sum(h.horas.valor for h in original.horas)
    assert sum(h.valor.valor for h in lida.honorarios) == sum(
        h.valor.valor for h in original.honorarios
    )


def test_linhas_de_empregado_sao_recusadas(original: Carteira, tmp_path: Path) -> None:
    escrever_planilha(original, tmp_path)
    (tmp_path / "folha_empregados.csv").write_text(
        "documento;cpf_empregado;nome;salario\n", encoding="utf-8"
    )
    with pytest.raises(ValorInvalido, match="empregado"):
        LeitorDePlanilhaDoEscritorio(tmp_path, Pseudonimizador(CHAVE)).extrair(INICIO, FIM)


def test_movimento_com_coluna_de_pessoa_e_recusado(original: Carteira, tmp_path: Path) -> None:
    escrever_planilha(original, tmp_path)
    movimento = tmp_path / "movimento.csv"
    linhas = movimento.read_text(encoding="utf-8").splitlines()
    linhas[0] += ";cpf_empregado"
    movimento.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    with pytest.raises(ValorInvalido, match="cpf"):
        LeitorDePlanilhaDoEscritorio(tmp_path, Pseudonimizador(CHAVE)).extrair(INICIO, FIM)


def test_dados_reais_fora_do_repositorio() -> None:
    gitignore = (Path(__file__).resolve().parents[3] / ".gitignore").read_text(encoding="utf-8")
    assert "dados/" in gitignore.splitlines()


def test_cli_relatorio_pela_planilha(
    original: Carteira, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from dynaprice.principal import app

    escrever_planilha(original, tmp_path / "escritorio")
    argumentos = [
        "lab",
        "relatorio",
        "--fonte",
        "planilha",
        "--entrada",
        str(tmp_path / "escritorio"),
    ]
    sem_chave = CliRunner().invoke(app, [*argumentos, "--saida", str(tmp_path / "r")])
    assert sem_chave.exit_code != 0
    monkeypatch.setenv("DYNAPRICE_CHAVE_PSEUDONIMO", CHAVE.decode())
    resultado = CliRunner().invoke(app, [*argumentos, "--saida", str(tmp_path / "r")])
    assert resultado.exit_code == 0, resultado.output
    texto = (tmp_path / "r" / "relatorio.md").read_text(encoding="utf-8")
    assert "Fulano" not in texto and documento_falso(original.empresas[0].id) not in texto
