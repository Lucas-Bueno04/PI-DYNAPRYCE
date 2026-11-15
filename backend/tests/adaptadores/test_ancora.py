"""F3.5: âncora externa em arquivo só de acréscimo, com elos próprios."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from dynaprice.adaptadores.saida.arquivos.ancora import AncoraEmArquivo
from dynaprice.aplicacao.portas.ancora import Ancora, ErroDeAncora

T1, T2 = uuid4(), uuid4()


def _a(tenant: UUID, seq: int, hash_: str = "ab" * 32) -> Ancora:
    return Ancora(tenant, seq, hash_, datetime(2027, 1, 5, 12, 0, tzinfo=UTC))


def test_registra_e_lista_por_inquilino_em_ordem(tmp_path: Path) -> None:
    ancora = AncoraEmArquivo(tmp_path / "ancoras.jsonl")
    ancora.registrar(_a(T1, 3))
    ancora.registrar(_a(T2, 1, "cd" * 32))
    ancora.registrar(_a(T1, 7))
    assert [a.seq for a in ancora.listar(T1)] == [3, 7]
    assert [(a.seq, a.hash_hex) for a in ancora.listar(T2)] == [(1, "cd" * 32)]
    assert AncoraEmArquivo(tmp_path / "ancoras.jsonl").listar(T1) == ancora.listar(T1)


def test_sem_arquivo_nao_ha_ancoras(tmp_path: Path) -> None:
    assert AncoraEmArquivo(tmp_path / "nada.jsonl").listar(T1) == []


def test_arquivo_so_cresce(tmp_path: Path) -> None:
    caminho = tmp_path / "a.jsonl"
    ancora = AncoraEmArquivo(caminho)
    ancora.registrar(_a(T1, 1))
    antes = caminho.read_bytes()
    ancora.registrar(_a(T1, 2))
    assert caminho.read_bytes().startswith(antes)


def test_alterar_uma_linha_do_meio_e_detectado(tmp_path: Path) -> None:
    caminho = tmp_path / "a.jsonl"
    ancora = AncoraEmArquivo(caminho)
    for seq in (1, 2, 3):
        ancora.registrar(_a(T1, seq))
    linhas = caminho.read_text().splitlines()
    registro = json.loads(linhas[1])
    registro["hash"] = "00" * 32
    linhas[1] = json.dumps(registro, sort_keys=True)
    caminho.write_text("\n".join(linhas) + "\n")
    with pytest.raises(ErroDeAncora):
        ancora.listar(T1)


def test_remover_uma_linha_do_meio_e_detectado(tmp_path: Path) -> None:
    caminho = tmp_path / "a.jsonl"
    ancora = AncoraEmArquivo(caminho)
    for seq in (1, 2, 3):
        ancora.registrar(_a(T1, seq))
    linhas = caminho.read_text().splitlines()
    caminho.write_text("\n".join([linhas[0], linhas[2]]) + "\n")
    with pytest.raises(ErroDeAncora):
        ancora.listar(T1)


def test_linha_ilegivel_e_erro_de_ancora(tmp_path: Path) -> None:
    caminho = tmp_path / "a.jsonl"
    caminho.write_text("lixo\n")
    with pytest.raises(ErroDeAncora):
        AncoraEmArquivo(caminho).listar(T1)
