"""Arquivo XLSX enviado pela interface: fronteira de confiança da importação (D-UPLOAD).

Validar antes de abrir: tamanho, extensão, macro e tamanho descomprimido. Só depois o openpyxl
lê o conteúdo; cada aba vira o CSV do layout e passa pelo mesmo leitor do laboratório.
"""

import csv
import hashlib
import io
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from dynaprice.adaptadores.saida.planilha.leitor import LeitorDePlanilhaDoEscritorio
from dynaprice.adaptadores.saida.planilha.pseudonimo import Pseudonimizador
from dynaprice.aplicacao.portas import LeituraDeArquivo, Rejeitada
from dynaprice.dominio.modelos import Competencia, ValorInvalido

ABAS = ("empresas", "contratos", "vinculos", "movimento", "horas", "honorarios")
_ERROS_DE_ABERTURA = (zipfile.BadZipFile, KeyError, OSError, ValueError, InvalidFileException)


@dataclass(frozen=True, slots=True)
class LimitesDeUpload:
    tamanho_maximo: int = 10 * 1024 * 1024
    linhas_maximas: int = 50_000
    descomprimido_maximo: int = 100 * 1024 * 1024


def _texto_da_celula(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime | date):
        return valor.strftime("%Y-%m")
    return str(valor)


class LeitorDeArquivoEnviado:
    def __init__(self, pseudonimizador: Pseudonimizador, limites: LimitesDeUpload) -> None:
        self._pseudonimizador = pseudonimizador
        self._limites = limites

    def ler(
        self, nome: str, conteudo: bytes, inicio: Competencia, fim: Competencia
    ) -> LeituraDeArquivo:
        self._validar_embalagem(nome, conteudo)
        with tempfile.TemporaryDirectory() as temporaria:
            pasta = Path(temporaria)
            self._converter(conteudo, pasta)
            leitor = LeitorDePlanilhaDoEscritorio(pasta, self._pseudonimizador, tolerante=True)
            carteira = leitor.extrair(inicio, fim)
        rejeicoes = tuple(Rejeitada(r.arquivo, r.linha, r.motivo) for r in leitor.rejeicoes)
        return LeituraDeArquivo(carteira, rejeicoes, hashlib.sha256(conteudo).hexdigest())

    def _validar_embalagem(self, nome: str, conteudo: bytes) -> None:
        if len(conteudo) > self._limites.tamanho_maximo:
            raise ValorInvalido("arquivo acima do limite de tamanho")
        if not nome.lower().endswith(".xlsx"):
            raise ValorInvalido("só arquivos .xlsx são aceitos")
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
                entradas = pacote.infolist()
        except zipfile.BadZipFile as erro:
            raise ValorInvalido("o arquivo não é um .xlsx válido") from erro
        if any(e.filename.lower().endswith("vbaproject.bin") for e in entradas):
            raise ValorInvalido("arquivo com macro não é aceito")
        if sum(e.file_size for e in entradas) > self._limites.descomprimido_maximo:
            raise ValorInvalido("conteúdo descomprimido acima do limite")

    def _converter(self, conteudo: bytes, pasta: Path) -> None:
        try:
            livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=False)
        except _ERROS_DE_ABERTURA as erro:
            raise ValorInvalido("o arquivo não é um .xlsx válido") from erro
        try:
            faltando = [aba for aba in ABAS if aba not in livro.sheetnames]
            if faltando:
                raise ValorInvalido(f"aba ausente: {faltando}")
            restantes = self._limites.linhas_maximas
            for aba in ABAS:
                restantes = self._escrever_aba(livro[aba], pasta / f"{aba}.csv", restantes)
        finally:
            livro.close()

    @staticmethod
    def _escrever_aba(aba: Any, destino: Path, restantes: int) -> int:
        with destino.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            for linha in aba.iter_rows():
                restantes -= 1
                if restantes < 0:
                    raise ValorInvalido("arquivo com linhas demais")
                if any(celula.data_type == "f" for celula in linha):
                    raise ValorInvalido("célula com fórmula não é aceita")
                escritor.writerow([_texto_da_celula(celula.value) for celula in linha])
        return restantes
