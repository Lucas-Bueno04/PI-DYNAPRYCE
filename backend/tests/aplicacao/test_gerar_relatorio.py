"""F0.19: caso de uso GerarRelatorioDoLaboratorio com fakes das portas (DIP)."""

from dynaprice.aplicacao.casos_de_uso import GerarRelatorioDoLaboratorio
from dynaprice.dominio.modelos import Carteira, Competencia, Item, Relatorio, Secao

VAZIA = Carteira((), (), (), (), (), ())


class FonteFalsa:
    def __init__(self) -> None:
        self.janelas: list[tuple[Competencia, Competencia]] = []

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        self.janelas.append((inicio, fim))
        return VAZIA


class AnalisadorFalso:
    def analisar(self, carteira: Carteira, referencia: Competencia) -> Relatorio:
        assert carteira is VAZIA
        return Relatorio("r", (Secao("s", (Item("x", "1", "teste"),)),), {"a.json": "{}"})


class EscritorFalso:
    def __init__(self) -> None:
        self.escritos: list[Relatorio] = []

    def escrever(self, relatorio: Relatorio) -> None:
        self.escritos.append(relatorio)


def test_extrai_analisa_e_escreve() -> None:
    fonte, escritor = FonteFalsa(), EscritorFalso()
    caso = GerarRelatorioDoLaboratorio(fonte, AnalisadorFalso(), escritor)
    relatorio = caso.executar(Competencia(2025, 1), Competencia(2025, 12))
    assert fonte.janelas == [(Competencia(2025, 1), Competencia(2025, 12))]
    assert escritor.escritos == [relatorio]
    assert relatorio.secao("s").itens[0].fonte == "teste"
