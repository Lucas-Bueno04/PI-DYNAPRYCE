"""F1.14: envelope AES-256-GCM com id de chave (ADR-002, D-ROT-CHAVE)."""

import base64
import json
import os
from pathlib import Path

import pytest

from dynaprice.adaptadores.saida.seguranca import CifradorAesGcm, carregar_chaves_mestras
from dynaprice.aplicacao.portas import SegredoInvalido
from dynaprice.dominio.modelos import ValorInvalido

K1 = os.urandom(32)
K2 = os.urandom(32)
SEGREDO = b"app_secret_do_omie"


def _cifrador() -> CifradorAesGcm:
    return CifradorAesGcm({"k1": K1})


def test_ida_e_volta() -> None:
    cifrador = _cifrador()
    assert cifrador.decifrar(cifrador.cifrar(SEGREDO, "conector"), "conector") == SEGREDO


def test_texto_cifrado_nao_contem_o_segredo_e_nonce_varia() -> None:
    cifrador = _cifrador()
    a, b = cifrador.cifrar(SEGREDO, "c"), cifrador.cifrar(SEGREDO, "c")
    assert SEGREDO not in a
    assert a != b


@pytest.mark.parametrize("posicao", [0, 1, 3, 8, 20, -1])
def test_adulteracao_e_recusada(posicao: int) -> None:
    cifrador = _cifrador()
    cifrado = bytearray(cifrador.cifrar(SEGREDO, "c"))
    cifrado[posicao] ^= 0x01
    with pytest.raises(SegredoInvalido):
        cifrador.decifrar(bytes(cifrado), "c")


def test_contexto_diferente_e_recusado() -> None:
    cifrador = _cifrador()
    with pytest.raises(SegredoInvalido):
        cifrador.decifrar(cifrador.cifrar(SEGREDO, "tenant-a"), "tenant-b")


def test_truncado_e_recusado() -> None:
    with pytest.raises(SegredoInvalido):
        _cifrador().decifrar(b"\x01", "c")


def test_rotacao_decifra_o_antigo_e_cifra_com_a_nova() -> None:
    antigo = _cifrador().cifrar(SEGREDO, "c")
    novo = CifradorAesGcm({"k1": K1, "k2": K2})
    recifrado = novo.recifrar(antigo, "c")
    assert novo.decifrar(antigo, "c") == SEGREDO
    assert CifradorAesGcm({"k2": K2}).decifrar(recifrado, "c") == SEGREDO


def test_chave_de_tamanho_errado_e_recusada() -> None:
    with pytest.raises(ValorInvalido):
        CifradorAesGcm({"k1": b"curta"})


def test_sem_chave_e_recusado() -> None:
    with pytest.raises(ValorInvalido):
        CifradorAesGcm({})


def test_chave_nao_aparece_na_representacao_nem_no_erro() -> None:
    cifrador = _cifrador()
    assert K1.hex() not in repr(cifrador)
    assert str(K1) not in repr(cifrador)
    with pytest.raises(SegredoInvalido) as erro:
        cifrador.decifrar(b"\x01\x02kk" + bytes(40), "c")
    assert SEGREDO.decode() not in str(erro.value)


def test_carregar_chaves_do_arquivo_de_segredo(tmp_path: Path) -> None:
    arquivo = tmp_path / "chaves"
    arquivo.write_text(json.dumps({"k1": base64.b64encode(K1).decode()}))
    assert carregar_chaves_mestras(arquivo) == {"k1": K1}
