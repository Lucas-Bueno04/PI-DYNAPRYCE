"""F1.23: conector do Domínio (ODBC) e simulação mw9kw9i514upw:11 (conector indisponível)."""

import re
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from dynaprice.adaptadores.entrada.worker import LacoDoWorker
from dynaprice.adaptadores.saida.conectores.dominio import CONSULTAS, ConectorDominio
from dynaprice.adaptadores.saida.planilha import Pseudonimizador
from dynaprice.adaptadores.saida.planilha.upload import LeitorDeArquivoEnviado, LimitesDeUpload
from dynaprice.adaptadores.saida.postgres import FabricaDeUnidadesPostgres, FilaPostgres
from dynaprice.adaptadores.saida.seguranca import CifradorAesGcm
from dynaprice.aplicacao.casos_de_uso.conectores import ConfigurarConector, ExtrairCompetencia
from dynaprice.aplicacao.casos_de_uso.importar import ImportarPlanilha
from dynaprice.aplicacao.portas import ConectorIndisponivel, CredencialInvalida
from dynaprice.dominio.modelos import Carteira, Competencia, Regime
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from dynaprice.dominio.modelos.fila import ParametrosDeFila
from tests.adaptadores.test_planilha import planilha
from tests.conftest import Banco
from tests.fakes import RelogioFixo

JAN = Competencia(2026, 1)
CHAVE = Pseudonimizador(b"chave-de-teste-com-16+")
# Colunas que identificam pessoa: nenhuma consulta pode selecioná-las.
PROIBIDAS = re.compile(r"\b(nome\w*|cpf\w*|salario\w*|i_empregados_nome|rg|pis)\b", re.I)


class ErroOdbc(Exception):
    """Mesma forma do pyodbc.Error: SQLSTATE no primeiro argumento."""


class Cursor:
    def __init__(self, respostas: dict[str, list[tuple[Any, ...]]]) -> None:
        self._respostas = respostas
        self._linhas: list[tuple[Any, ...]] = []

    def execute(self, sql: str, *parametros: Any) -> Cursor:
        chave = next(k for k, v in CONSULTAS.items() if v == sql)
        self._linhas = self._respostas[chave]
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._linhas


class Conexao:
    def __init__(self, respostas: dict[str, list[tuple[Any, ...]]]) -> None:
        self._respostas = respostas
        self.timeout = 0
        self.fechada = False

    def cursor(self) -> Cursor:
        return Cursor(self._respostas)

    def close(self) -> None:
        self.fechada = True


RESPOSTAS: dict[str, list[tuple[Any, ...]]] = {
    "empresas": [("12345678000195", "LP", "fiscal|contabil|folha")],
    "movimento": [("12345678000195", "2026-01", 30, 5, 40, 2, 2, 0, 0)],
    "horas": [("12345678000195", "2026-01", "fiscal", 3.5)],
}


def _conector(conexao: Conexao) -> ConectorDominio:
    return ConectorDominio(lambda: conexao, CHAVE, ErroOdbc, tempo_s=30)


def test_extrai_contagens_com_documento_pseudonimizado() -> None:
    conexao = Conexao(RESPOSTAS)
    carteira = _conector(conexao).extrair(JAN, JAN)
    assert carteira.empresas[0].regime is Regime.LP
    assert carteira.empresas[0].id != "12345678000195"
    assert carteira.direcionadores[0].valor("empregados") == 2
    assert conexao.timeout == 30
    assert conexao.fechada is True


@pytest.mark.parametrize("nome", sorted(CONSULTAS))
def test_consultas_nao_selecionam_dado_de_pessoa(nome: str) -> None:
    assert PROIBIDAS.search(CONSULTAS[nome]) is None


def test_folha_vem_so_como_contagem() -> None:
    assert "COUNT" in CONSULTAS["movimento"].upper()


def test_raw_nao_tem_campo_proibido() -> None:
    from dynaprice.aplicacao.casos_de_uso.importar import carteira_em_json

    texto = str(carteira_em_json(_conector(Conexao(RESPOSTAS)).extrair(JAN, JAN)))
    assert PROIBIDAS.search(texto) is None
    assert "12345678000195" not in texto


def test_tempo_esgotado_vira_conector_indisponivel() -> None:
    def falha() -> Conexao:
        raise ErroOdbc("HYT00", "timeout")

    with pytest.raises(ConectorIndisponivel):
        ConectorDominio(falha, CHAVE, ErroOdbc).extrair(JAN, JAN)


def test_credencial_recusada_vira_erro_permanente() -> None:
    def falha() -> Conexao:
        raise ErroOdbc("28000", "login failed")

    with pytest.raises(CredencialInvalida):
        ConectorDominio(falha, CHAVE, ErroOdbc).extrair(JAN, JAN)


class FonteDeTeste:
    def __init__(self) -> None:
        self.erro: Exception | None = ConectorIndisponivel("tempo esgotado")

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        assert self.erro is not None
        raise self.erro


PARAMETROS = ParametrosDeFila(max_tentativas=3, variacao=0.0)
CIFRADOR = CifradorAesGcm({"k1": bytes(range(32))})


class TestSimulacaoConectorIndisponivel:
    """Simulação mw9kw9i514upw:11, passo a passo."""

    def test_seis_passos(self, pool: ConnectionPool, novo_tenant: UUID, banco: Banco) -> None:
        with psycopg.connect(banco.superusuario, autocommit=True) as s:
            s.execute("DELETE FROM job.job")
        relogio = RelogioFixo()
        fabrica = FabricaDeUnidadesPostgres(pool, relogio)
        admin = Principal(UUID(int=1), novo_tenant, frozenset({Papel.ADMINISTRAR}), True)
        ConfigurarConector(fabrica, CIFRADOR).executar(admin, "dominio", {"senha": "x"}, {}, 5)
        fonte = FonteDeTeste()
        extrair = ExtrairCompetencia(
            fabrica, relogio, CIFRADOR, {"dominio": lambda _credencial, _parametros: fonte}
        )
        fila = FilaPostgres(pool, relogio, PARAMETROS, dono="w")
        laco = LacoDoWorker(fila, {"extrair": extrair.executar}, relogio)

        def linha(chave: str = "extrair:dominio:2026-01") -> tuple[Any, ...]:
            with psycopg.connect(banco.superusuario) as s:
                resultado = s.execute(
                    "SELECT estado, tentativas, proxima_tentativa_em, erro FROM job.job "
                    "WHERE tenant_id=%s AND chave_idempotencia=%s",
                    (novo_tenant, chave),
                ).fetchone()
            assert resultado is not None
            return resultado

        def extracoes() -> int:
            with psycopg.connect(banco.superusuario) as s:
                total = s.execute(
                    "SELECT count(*) FROM raw.extracao WHERE tenant_id=%s", (novo_tenant,)
                ).fetchone()
            assert total is not None
            return int(total[0])

        def enfileirar(chave: str) -> None:
            with fabrica.para_tenant(novo_tenant) as uow:
                uow.fila.enfileirar(
                    "extrair",
                    chave,
                    {"fonte": "dominio", "competencia": "2026-01"},
                    relogio.agora(),
                )

        # Passos 1 a 3: o job inicia, o ODBC não responde e ele volta com backoff de 60 s.
        enfileirar("extrair:dominio:2026-01")
        assert laco.executar_um() is True
        estado, tentativas, proxima, _ = linha()
        assert (estado, tentativas) == ("pendente", 1)
        assert (proxima - relogio.agora()).total_seconds() == 60
        assert extracoes() == 0
        # Passo 4: credencial recusada não repete.
        fonte.erro = CredencialInvalida("login recusado")
        enfileirar("extrair:dominio:cred")
        relogio.avancar(30)
        assert laco.executar_um() is True
        assert linha("extrair:dominio:cred")[:2] == ("falhou", 1)
        # Passo 5: tentativas esgotadas, falhou com alerta.
        fonte.erro = ConectorIndisponivel("tempo esgotado")
        for _ in range(2):
            relogio.avancar(3600)
            assert laco.executar_um() is True
        assert linha()[:2] == ("falhou", 3)
        with psycopg.connect(banco.superusuario) as s:
            alertas = s.execute(
                "SELECT count(*) FROM core.alerta WHERE tenant_id=%s AND tipo='job_falhou'",
                (novo_tenant,),
            ).fetchone()
        assert alertas == (2,)
        # Passo 6: planilha como plano B, versão 1, origem planilha.
        analista = Principal(UUID(int=2), novo_tenant, frozenset({Papel.ANALISAR}), False)
        leitor = LeitorDeArquivoEnviado(CHAVE, LimitesDeUpload())
        resultado = ImportarPlanilha(fabrica, relogio, leitor).executar(
            analista, "c.xlsx", planilha(), Competencia(2026, 1), Competencia(2026, 12)
        )
        assert resultado.versao == 1
        with psycopg.connect(banco.superusuario) as s:
            origem = s.execute(
                "SELECT origem FROM raw.extracao WHERE tenant_id=%s", (novo_tenant,)
            ).fetchall()
        assert origem == [("planilha",)]
