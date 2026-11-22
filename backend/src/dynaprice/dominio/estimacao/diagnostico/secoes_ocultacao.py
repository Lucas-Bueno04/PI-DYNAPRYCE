"""Seção de validação por ocultação (artigo 5.15 e 10.5): EPAM sob informação incompleta."""

from dynaprice.dominio.estimacao.diagnostico.calibracao import Calibracao
from dynaprice.dominio.estimacao.diagnostico.contexto import Contexto
from dynaprice.dominio.estimacao.diagnostico.formato import pct
from dynaprice.dominio.estimacao.entrada_simulacao import contratos_conhecidos
from dynaprice.dominio.estimacao.ocultacao import ResultadoDaOcultacao, executar_ocultacao
from dynaprice.dominio.modelos import Item, Secao, Tabela
from dynaprice.dominio.precificacao import EquacoesDeTempo

TITULO = "Validação por ocultação (EPAM)"
MESES = (0, 1, 3, 6, 9)
KS = (3, 5, 10)
FONTE = "protocolo de ocultação em K dobras sobre contratos com 12 meses (artigo 5.15 e 10.5)"
MINIMO_POR_DOBRA = 2


def _tabela(resultado: ResultadoDaOcultacao) -> Tabela:
    nomes = sorted({x.estimador for x in resultado.linhas})
    por_chave = {(x.estimador, x.meses): x for x in resultado.linhas}
    linhas = tuple((nome, *(pct(por_chave[(nome, m)].epam) for m in MESES)) for nome in nomes)
    colunas = ("Estimador", *(f"{m} meses vistos" for m in MESES))
    return Tabela("EPAM do preço por estimador e meses vistos", colunas, linhas, FONTE)


def secao_ocultacao(contexto: Contexto, cal: Calibracao) -> Secao:
    equacoes = EquacoesDeTempo(cal.politica)
    contratos = contratos_conhecidos(contexto.carteira, contexto.agregacao.contratos, equacoes)
    dobras = min(5, len(contratos) // MINIMO_POR_DOBRA)
    if dobras < 2:
        motivo = f"{len(contratos)} contratos com 12 meses; são necessários ao menos 4"
        return Secao(TITULO, (Item("EPAM", "não calculado", motivo),))
    resultado = executar_ocultacao(contratos, cal.politica, MESES, KS, dobras)
    itens = (
        Item("Contratos avaliados", str(len(contratos)), FONTE),
        Item("Dobras", str(dobras), FONTE),
        *(
            Item(f"Melhor estimador com {m} meses vistos", resultado.melhor(m), FONTE)
            for m in MESES
        ),
        Item(
            "Uso na cotação",
            "piso do regime (ADR-004)",
            "vizinhança só offline; a política escolhe com `sem_historico`",
        ),
    )
    return Secao(TITULO, itens, (_tabela(resultado),))
