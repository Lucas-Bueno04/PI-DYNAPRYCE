"""F1.22: validação do arquivo enviado (fronteira de confiança da seção 9)."""

import io
import zipfile

import openpyxl
import pytest

from dynaprice.adaptadores.saida.planilha import Pseudonimizador
from dynaprice.adaptadores.saida.planilha.upload import (
    LeitorDeArquivoEnviado,
    LimitesDeUpload,
)
from dynaprice.dominio.modelos import Competencia, ValorInvalido

INICIO, FIM = Competencia(2026, 1), Competencia(2026, 12)
CHAVE = Pseudonimizador(b"chave-de-teste-com-16+")

ABAS: dict[str, list[list[object]]] = {
    "empresas": [["documento", "regime", "departamentos"], ["11", "LP", "fiscal|contabil|folha"]],
    "contratos": [
        ["contrato", "honorario_vigente", "mes_reajuste", "provisorio", "kappa"],
        ["C1", "437,00", 3, "N", ""],
    ],
    "vinculos": [
        ["documento", "contrato", "desde", "ate", "principal"],
        ["11", "C1", "2025-01", "", "S"],
    ],
    "movimento": [
        [
            "documento",
            "competencia",
            "notas_entrada",
            "notas_saida",
            "lancamentos_manuais",
            "lancamentos_automaticos",
            "empregados",
            "admissoes",
            "rescisoes",
        ],
        ["11", "2026-01", 30, 5, 40, 2, 2, 0, 0],
    ],
    "horas": [
        ["documento", "competencia", "departamento", "horas"],
        ["11", "2026-01", "fiscal", "3,5"],
    ],
    "honorarios": [["contrato", "competencia", "valor"], ["C1", "2026-01", "437,00"]],
}


def planilha(mudancas: dict[str, list[list[object]]] | None = None) -> bytes:
    livro = openpyxl.Workbook()
    livro.remove(livro.worksheets[0])
    for nome, linhas in {**ABAS, **(mudancas or {})}.items():
        aba = livro.create_sheet(nome)
        for linha in linhas:
            aba.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def _leitor(limites: LimitesDeUpload | None = None) -> LeitorDeArquivoEnviado:
    return LeitorDeArquivoEnviado(CHAVE, limites or LimitesDeUpload())


def test_planilha_valida_vira_carteira_com_pseudonimo() -> None:
    leitura = _leitor().ler("carga.xlsx", planilha(), INICIO, FIM)
    assert len(leitura.carteira.contratos) == 1
    assert leitura.carteira.empresas[0].id != "11"
    assert len(leitura.hash_conteudo) == 64


def test_acima_do_limite_de_tamanho_e_recusado() -> None:
    with pytest.raises(ValorInvalido, match="limite"):
        _leitor(LimitesDeUpload(tamanho_maximo=100)).ler("carga.xlsx", planilha(), INICIO, FIM)


def test_extensao_nao_permitida_e_recusada() -> None:
    with pytest.raises(ValorInvalido, match="xlsx"):
        _leitor().ler("carga.xlsm", planilha(), INICIO, FIM)


def test_arquivo_que_nao_e_zip_e_recusado() -> None:
    with pytest.raises(ValorInvalido):
        _leitor().ler("carga.xlsx", b"nao sou um xlsx", INICIO, FIM)


def test_macro_e_recusada() -> None:
    original = io.BytesIO(planilha())
    saida = io.BytesIO()
    with zipfile.ZipFile(original) as entrada, zipfile.ZipFile(saida, "w") as destino:
        for nome in entrada.namelist():
            destino.writestr(nome, entrada.read(nome))
        destino.writestr("xl/vbaProject.bin", b"macro")
    with pytest.raises(ValorInvalido, match="macro"):
        _leitor().ler("carga.xlsx", saida.getvalue(), INICIO, FIM)


def test_formula_e_recusada() -> None:
    com_formula = planilha(
        {"honorarios": [["contrato", "competencia", "valor"], ["C1", "2026-01", "=1+1"]]}
    )
    with pytest.raises(ValorInvalido, match="fórmula"):
        _leitor().ler("carga.xlsx", com_formula, INICIO, FIM)


def test_bomba_de_compressao_e_recusada() -> None:
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as destino:
        destino.writestr("xl/worksheets/sheet1.xml", b"0" * 2_000_000)
    with pytest.raises(ValorInvalido, match="descomprimido"):
        _leitor(LimitesDeUpload(descomprimido_maximo=1_000_000)).ler(
            "carga.xlsx", saida.getvalue(), INICIO, FIM
        )


def test_linhas_demais_sao_recusadas() -> None:
    with pytest.raises(ValorInvalido, match="linhas"):
        _leitor(LimitesDeUpload(linhas_maximas=2)).ler("carga.xlsx", planilha(), INICIO, FIM)


def test_coluna_com_dado_de_pessoa_e_recusada() -> None:
    com_cpf = planilha(
        {"empresas": [["documento", "regime", "departamentos", "cpf"], ["1", "LP", "folha", "9"]]}
    )
    with pytest.raises(ValorInvalido, match="pessoa"):
        _leitor().ler("carga.xlsx", com_cpf, INICIO, FIM)


def test_aba_faltando_e_recusada() -> None:
    livro = openpyxl.Workbook()
    saida = io.BytesIO()
    livro.save(saida)
    with pytest.raises(ValorInvalido, match="aba"):
        _leitor().ler("carga.xlsx", saida.getvalue(), INICIO, FIM)


def test_linha_invalida_vai_para_rejeicoes_sem_o_conteudo() -> None:
    ruim = planilha(
        {
            "contratos": [
                ABAS["contratos"][0],
                ABAS["contratos"][1],
                ["C2", "nao-numero-sigiloso", 3, "N", ""],
            ]
        }
    )
    leitura = _leitor().ler("carga.xlsx", ruim, INICIO, FIM)
    assert len(leitura.carteira.contratos) == 1
    (rejeicao,) = leitura.rejeicoes
    assert (rejeicao.arquivo, rejeicao.linha) == ("contratos.csv", 2)
    assert "sigiloso" not in rejeicao.motivo


def test_mesmo_arquivo_tem_o_mesmo_hash() -> None:
    conteudo = planilha()
    leitor = _leitor()
    assert leitor.ler("a.xlsx", conteudo, INICIO, FIM).hash_conteudo == (
        leitor.ler("b.xlsx", conteudo, INICIO, FIM).hash_conteudo
    )
