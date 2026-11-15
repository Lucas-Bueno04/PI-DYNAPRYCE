"""F1.16: Argon2id para senha e TOTP com passo devolvido, contra reuso do código."""

from datetime import UTC, datetime

import pyotp
import pytest

from dynaprice.adaptadores.saida.seguranca import HashDeSenhaArgon2, VerificadorTotpPyotp

INSTANTE = datetime(2027, 2, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def hash_de_senha() -> HashDeSenhaArgon2:
    return HashDeSenhaArgon2(tempo=1, memoria_kib=1024, paralelismo=1)


def test_senha_certa_confere(hash_de_senha: HashDeSenhaArgon2) -> None:
    assert hash_de_senha.verificar(hash_de_senha.gerar("senha-longa-123"), "senha-longa-123")


def test_senha_errada_nao_confere(hash_de_senha: HashDeSenhaArgon2) -> None:
    assert not hash_de_senha.verificar(hash_de_senha.gerar("senha-longa-123"), "outra")


def test_hash_e_argon2id_com_sal(hash_de_senha: HashDeSenhaArgon2) -> None:
    a, b = hash_de_senha.gerar("x"), hash_de_senha.gerar("x")
    assert a.startswith("$argon2id$")
    assert a != b


def test_hash_invalido_nao_confere_e_nao_explode(hash_de_senha: HashDeSenhaArgon2) -> None:
    assert not hash_de_senha.verificar("lixo", "x")


def test_verificacao_simulada_nao_explode(hash_de_senha: HashDeSenhaArgon2) -> None:
    hash_de_senha.simular_verificacao("qualquer")


def test_parametros_antigos_pedem_novo_hash() -> None:
    antigo = HashDeSenhaArgon2(tempo=1, memoria_kib=1024, paralelismo=1).gerar("x")
    atual = HashDeSenhaArgon2(tempo=2, memoria_kib=2048, paralelismo=1)
    assert atual.precisa_refazer(antigo)


def test_totp_devolve_o_passo_do_codigo() -> None:
    totp = VerificadorTotpPyotp()
    segredo = totp.novo_segredo()
    codigo = pyotp.TOTP(segredo).at(INSTANTE)
    assert totp.passo_valido(segredo, codigo, INSTANTE) == int(INSTANTE.timestamp()) // 30


def test_totp_aceita_um_passo_de_tolerancia() -> None:
    totp = VerificadorTotpPyotp()
    segredo = totp.novo_segredo()
    codigo = pyotp.TOTP(segredo).at(int(INSTANTE.timestamp()) - 30)
    assert totp.passo_valido(segredo, codigo, INSTANTE) == int(INSTANTE.timestamp()) // 30 - 1


def test_totp_fora_da_janela_e_recusado() -> None:
    totp = VerificadorTotpPyotp()
    segredo = totp.novo_segredo()
    codigo = pyotp.TOTP(segredo).at(int(INSTANTE.timestamp()) - 300)
    assert totp.passo_valido(segredo, codigo, INSTANTE) is None


def test_uri_de_cadastro_identifica_o_produto() -> None:
    totp = VerificadorTotpPyotp()
    assert "issuer=DynaPrice" in totp.uri(totp.novo_segredo(), "conta")


def test_totp_com_caracteres_nao_ascii_e_recusado_sem_explodir() -> None:
    totp = VerificadorTotpPyotp()
    assert totp.passo_valido(totp.novo_segredo(), "12345é", INSTANTE) is None
