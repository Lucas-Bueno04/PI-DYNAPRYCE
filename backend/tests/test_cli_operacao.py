"""F1.19 e F1.31: comandos de operação da cli, montados pelo Composition Root."""

import base64
import json
from decimal import Decimal
from pathlib import Path
from typing import NoReturn
from uuid import uuid4

import psycopg
import pytest
import typer
from typer.testing import CliRunner

from dynaprice.adaptadores.entrada.cli.operacao import FabricasDeOperacao, registrar_operacao
from dynaprice.aplicacao.casos_de_uso.ancora import DivergenciaDeAncora, ResultadoDaVerificacao
from dynaprice.aplicacao.casos_de_uso.indices import ResumoDaCargaDoIndice
from dynaprice.aplicacao.portas.inflacao import Divergencia
from dynaprice.dominio.modelos import Competencia
from dynaprice.principal import app
from tests.api.conftest import chaves_de_teste
from tests.conftest import Banco

SENHA = "senha-bem-longa-123"


@pytest.fixture
def ambiente(banco: Banco, tmp_path: Path) -> dict[str, str]:
    url = tmp_path / "url"
    url.write_text(banco.app)
    migrador = tmp_path / "url_migrador"
    migrador.write_text(banco.migrador)
    mestras = tmp_path / "mestras"
    mestras.write_text(json.dumps({"k1": base64.b64encode(bytes(32)).decode()}))
    chave = tmp_path / "es256"
    chaves = chaves_de_teste()
    chave.write_text(json.dumps({"kid": chaves.kid, "privada": chaves.privada_pem}))
    return {
        "DYNAPRICE_DB_URL_FILE": str(url),
        "DYNAPRICE_DB_URL_MIGRADOR_FILE": str(migrador),
        "DYNAPRICE_CHAVES_MESTRAS_FILE": str(mestras),
        "DYNAPRICE_CHAVE_ES256_FILE": str(chave),
        "DYNAPRICE_ORIGEM": "https://teste",
        "DYNAPRICE_CHAVE_PSEUDONIMO_FILE": str(mestras),
        "DYNAPRICE_SENHA_ADMIN": SENHA,
    }


def test_banco_migrar(ambiente: dict[str, str]) -> None:
    resultado = CliRunner().invoke(
        app,
        ["banco", "migrar"],
        env={**ambiente, "DYNAPRICE_DB_URL_FILE": ambiente["DYNAPRICE_DB_URL_MIGRADOR_FILE"]},
    )
    assert resultado.exit_code == 0, resultado.output


def test_criar_admin_so_sem_administrador(ambiente: dict[str, str], banco: Banco) -> None:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute("DELETE FROM auth.usuario_papel WHERE papel = 'administrar'")
    argumentos = ["criar-admin", "--inquilino", "Escritório", "--email"]
    primeiro = CliRunner().invoke(app, [*argumentos, f"{uuid4()}@t.com"], env=ambiente)
    assert primeiro.exit_code == 0, primeiro.output
    segundo = CliRunner().invoke(app, [*argumentos, f"{uuid4()}@t.com"], env=ambiente)
    assert segundo.exit_code == 1
    assert "já existe administrador" in segundo.output


def test_worker_uma_vez_sem_jobs(ambiente: dict[str, str], banco: Banco) -> None:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        s.execute("DELETE FROM job.job")
    resultado = CliRunner().invoke(app, ["worker", "--uma-vez"], env=ambiente)
    assert resultado.exit_code == 0, resultado.output


def _app_com_indice(
    resumo: ResumoDaCargaDoIndice,
    resultados: tuple[ResultadoDaVerificacao, ...] = (),
) -> tuple[typer.Typer, list[tuple[Competencia, Competencia]]]:
    chamadas: list[tuple[Competencia, Competencia]] = []

    def atualizar(inicio: Competencia, fim: Competencia) -> ResumoDaCargaDoIndice:
        chamadas.append((inicio, fim))
        return resumo

    def proibido(*_: object) -> NoReturn:
        raise AssertionError("não deveria ser chamado")

    cli = typer.Typer()
    registrar_operacao(
        cli,
        FabricasDeOperacao(
            migrar=proibido,
            criar_admin=proibido,
            recalcular=proibido,
            worker=proibido,
            rotacionar_chave=proibido,
            exportar_openapi=proibido,
            atualizar_indice=atualizar,
            ancorar_auditoria=lambda: 2,
            verificar_auditoria=lambda: resultados,
        ),
    )
    return cli, chamadas


def test_indice_atualizar_mostra_o_resumo() -> None:
    cli, chamadas = _app_com_indice(ResumoDaCargaDoIndice(3, 1, ()))
    resultado = CliRunner().invoke(
        cli, ["indice", "atualizar", "--inicio", "2026-01", "--fim", "2026-04"]
    )
    assert resultado.exit_code == 0, resultado.output
    assert "3 gravados, 1 já existiam, 0 divergentes" in resultado.output
    assert [(str(i), str(f)) for i, f in chamadas] == [("2026-01", "2026-04")]


def test_indice_divergente_sai_com_codigo_1_e_lista_os_meses() -> None:
    divergencia = Divergencia(Competencia(2026, 2), Decimal("0.004"), Decimal("0.005"))
    cli, _ = _app_com_indice(ResumoDaCargaDoIndice(0, 0, (divergencia,)))
    resultado = CliRunner().invoke(
        cli, ["indice", "atualizar", "--inicio", "2026-02", "--fim", "2026-02"]
    )
    assert resultado.exit_code == 1
    assert "2026-02" in resultado.output and "0.004" in resultado.output


def test_indice_recusa_competencia_invalida_e_intervalo_invertido() -> None:
    cli, chamadas = _app_com_indice(ResumoDaCargaDoIndice(0, 0, ()))
    for inicio, fim in (("2026-13", "2026-12"), ("2026-05", "2026-01")):
        resultado = CliRunner().invoke(
            cli, ["indice", "atualizar", "--inicio", inicio, "--fim", fim]
        )
        assert resultado.exit_code != 0
    assert chamadas == []


def test_auditoria_ancorar_informa_quantas_ancoras_gravou() -> None:
    cli, _ = _app_com_indice(ResumoDaCargaDoIndice(0, 0, ()))
    resultado = CliRunner().invoke(cli, ["auditoria", "ancorar"])
    assert resultado.exit_code == 0 and "2 âncoras gravadas" in resultado.output


def test_auditoria_verificar_integra_sai_com_zero() -> None:
    ok = ResultadoDaVerificacao(uuid4(), None, ())
    cli, _ = _app_com_indice(ResumoDaCargaDoIndice(0, 0, ()), (ok,))
    resultado = CliRunner().invoke(cli, ["auditoria", "verificar"])
    assert resultado.exit_code == 0 and "1 inquilino(s) íntegro(s)" in resultado.output


def test_auditoria_verificar_adulterada_sai_com_um_e_diz_onde() -> None:
    inquilino = uuid4()
    ruim = ResultadoDaVerificacao(inquilino, 2, (DivergenciaDeAncora(4, "aa", None),))
    cli, _ = _app_com_indice(ResumoDaCargaDoIndice(0, 0, ()), (ruim,))
    resultado = CliRunner().invoke(cli, ["auditoria", "verificar"])
    assert resultado.exit_code == 1
    assert str(inquilino) in resultado.output
    assert "cadeia quebrada no evento 2" in resultado.output
    assert "âncora do evento 4 não confere (evento ausente)" in resultado.output
