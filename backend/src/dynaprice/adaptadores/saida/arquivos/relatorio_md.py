"""Adapter: grava o Relatorio em Markdown (relatorio.md) e os anexos ao lado."""

from pathlib import Path

from dynaprice.dominio.modelos import Relatorio, Secao, Tabela


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|")


def _linha(celulas: tuple[str, ...]) -> str:
    return "| " + " | ".join(map(_celula, celulas)) + " |"


def _tabela(tabela: Tabela) -> list[str]:
    return [
        f"**{tabela.titulo}**",
        "",
        _linha(tabela.colunas),
        _linha(tuple("---" for _ in tabela.colunas)),
        *map(_linha, tabela.linhas),
        "",
        f"Fonte: {tabela.fonte}",
        "",
    ]


def _secao(secao: Secao) -> list[str]:
    linhas = [f"## {secao.titulo}", ""]
    if secao.itens:
        linhas += [_linha(("Grandeza", "Valor", "Fonte")), _linha(("---", "---", "---"))]
        linhas += [_linha((i.rotulo, i.valor, i.fonte)) for i in secao.itens] + [""]
    for tabela in secao.tabelas:
        linhas += _tabela(tabela)
    return linhas


class EscritorDeRelatorioMarkdown:
    def __init__(self, pasta: Path) -> None:
        self._pasta = pasta

    def escrever(self, relatorio: Relatorio) -> None:
        self._pasta.mkdir(parents=True, exist_ok=True)
        linhas = [f"# {relatorio.titulo}", ""]
        for secao in relatorio.secoes:
            linhas += _secao(secao)
        (self._pasta / "relatorio.md").write_text("\n".join(linhas), encoding="utf-8")
        for nome, conteudo in relatorio.anexos.items():
            (self._pasta / nome).write_text(conteudo, encoding="utf-8")
