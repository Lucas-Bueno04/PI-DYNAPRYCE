"""F0.19: escritor Markdown do relatório e anexos."""

from pathlib import Path

from dynaprice.adaptadores.saida.arquivos import EscritorDeRelatorioMarkdown
from dynaprice.dominio.modelos import Item, Relatorio, Secao, Tabela


def test_markdown_com_fonte_de_cada_numero(tmp_path: Path) -> None:
    relatorio = Relatorio(
        "Relatório",
        (
            Secao(
                "Tarifa",
                (Item("τ̂", "103,50", "Eq. (65)"),),
                (Tabela("Pisos", ("regime", "π"), (("LP", "235,00"),), "D2"),),
            ),
        ),
        {"politica_rascunho.json": '{"versao": 1}'},
    )
    EscritorDeRelatorioMarkdown(tmp_path).escrever(relatorio)
    texto = (tmp_path / "relatorio.md").read_text(encoding="utf-8")
    assert texto.startswith("# Relatório")
    assert "## Tarifa" in texto
    assert "| τ̂ | 103,50 | Eq. (65) |" in texto
    assert "| LP | 235,00 |" in texto and "Fonte: D2" in texto
    assert (tmp_path / "politica_rascunho.json").read_text(encoding="utf-8") == '{"versao": 1}'
