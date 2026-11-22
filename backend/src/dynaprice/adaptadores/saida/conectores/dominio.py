"""Conector do Domínio por ODBC: só leitura e só contagens de folha (F1.23, RNF05).

ATENÇÃO: o nome das tabelas e colunas é a confirmar em F0.21, com a TI do escritório.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from dynaprice.adaptadores.saida.planilha.leitor import DIRECIONADORES
from dynaprice.adaptadores.saida.planilha.pseudonimo import Pseudonimizador
from dynaprice.aplicacao.portas import ConectorIndisponivel, CredencialInvalida
from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Departamento,
    Direcionadores,
    Empresa,
    Horas,
    HorasRegistradas,
    Regime,
)

# Projeção mínima: documento só para gerar o pseudônimo; da folha, só contagens.
CONSULTAS = {
    "empresas": "SELECT documento, regime, departamentos FROM dynaprice_empresas",
    "movimento": (
        "SELECT documento, competencia, notas_entrada, notas_saida, lancamentos_manuais, "
        "lancamentos_automaticos, COUNT(empregado_id) AS empregados, admissoes, rescisoes "
        "FROM dynaprice_movimento WHERE competencia BETWEEN ? AND ? "
        "GROUP BY documento, competencia, notas_entrada, notas_saida, lancamentos_manuais, "
        "lancamentos_automaticos, admissoes, rescisoes"
    ),
    "horas": (
        "SELECT documento, competencia, departamento, SUM(horas) AS horas "
        "FROM dynaprice_horas WHERE competencia BETWEEN ? AND ? "
        "GROUP BY documento, competencia, departamento"
    ),
}
_SQLSTATE_DE_CREDENCIAL = ("28000", "28P01")


class ConectorDominio:
    def __init__(
        self,
        conectar: Callable[[], Any],
        pseudonimizador: Pseudonimizador,
        erro_do_driver: type[Exception],
        tempo_s: int = 60,
    ) -> None:
        # O erro vem injetado para não importar pyodbc aqui: ele exige libodbc (D-ODBC).
        self._conectar = conectar
        self._p = pseudonimizador
        self._erro_do_driver = erro_do_driver
        self._tempo_s = tempo_s

    def __repr__(self) -> str:
        return "ConectorDominio()"

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        try:
            return self._ler(inicio, fim)
        except self._erro_do_driver as erro:
            codigo = str(erro.args[0]) if erro.args else ""
            # Só o SQLSTATE: a mensagem do driver pode trazer usuário ou servidor.
            if codigo in _SQLSTATE_DE_CREDENCIAL:
                raise CredencialInvalida(f"Domínio recusou a credencial ({codigo})") from erro
            raise ConectorIndisponivel(f"Domínio indisponível ({codigo})") from erro

    def _ler(self, inicio: Competencia, fim: Competencia) -> Carteira:
        conexao = self._conectar()
        try:
            conexao.timeout = self._tempo_s
            janela = (str(inicio), str(fim))
            cursor = conexao.cursor()
            empresas = cursor.execute(CONSULTAS["empresas"]).fetchall()
            movimento = cursor.execute(CONSULTAS["movimento"], *janela).fetchall()
            horas = cursor.execute(CONSULTAS["horas"], *janela).fetchall()
        finally:
            conexao.close()
        return Carteira(
            empresas=tuple(self._empresa(linha) for linha in empresas),
            contratos=(),
            vinculos=(),
            direcionadores=tuple(self._movimento(linha) for linha in movimento),
            horas=tuple(self._horas(linha) for linha in horas),
            honorarios=(),
        )

    def _empresa(self, linha: Any) -> Empresa:
        departamentos = frozenset(Departamento(d) for d in str(linha[2]).split("|"))
        return Empresa(self._p.pseudonimo(str(linha[0])), Regime(linha[1]), departamentos)

    def _movimento(self, linha: Any) -> Direcionadores:
        valores = {nome: Decimal(str(linha[i + 2])) for i, nome in enumerate(DIRECIONADORES)}
        return Direcionadores(
            self._p.pseudonimo(str(linha[0])), Competencia.de_texto(str(linha[1])), valores
        )

    def _horas(self, linha: Any) -> HorasRegistradas:
        return HorasRegistradas(
            self._p.pseudonimo(str(linha[0])),
            Competencia.de_texto(str(linha[1])),
            Departamento(linha[2]),
            Horas(Decimal(str(linha[3]))),
        )
