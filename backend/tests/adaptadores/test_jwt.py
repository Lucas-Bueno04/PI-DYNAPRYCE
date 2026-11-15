"""F1.16: JWT ES256 com kid, JWKS e rotação (ADR-002)."""

from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from dynaprice.adaptadores.saida.seguranca import ChavesEs256, EmissorJwtEs256
from dynaprice.aplicacao.portas import TokenInvalido
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.fakes import RelogioFixo

ISS, AUD = "dynaprice", "dynaprice-api"
PRINCIPAL = Principal(uuid4(), uuid4(), frozenset({Papel.APROVAR}), mfa_verificado=True)


def _par() -> tuple[str, str]:
    privada = ec.generate_private_key(ec.SECP256R1())
    return (
        privada.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        privada.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode(),
    )


PRIV1, PUB1 = _par()
PRIV2, PUB2 = _par()


def _emissor(relogio: RelogioFixo, chaves: ChavesEs256 | None = None) -> EmissorJwtEs256:
    return EmissorJwtEs256(chaves or ChavesEs256("k1", PRIV1), relogio, ISS, AUD)


def _forjar(relogio: RelogioFixo, chave: str, algoritmo: str, **mudancas: object) -> str:
    agora = int(relogio.agora().timestamp())
    corpo = {
        "iss": ISS,
        "aud": AUD,
        "sub": str(PRINCIPAL.usuario_id),
        "tid": str(PRINCIPAL.tenant_id),
        "roles": ["aprovar"],
        "mfa": True,
        "iat": agora,
        "exp": agora + 900,
        "jti": "j",
    } | mudancas
    return jwt.encode(corpo, chave, algorithm=algoritmo, headers={"kid": "k1"})


def test_ida_e_volta_preserva_o_principal() -> None:
    emissor = _emissor(RelogioFixo())
    assert emissor.verificar(emissor.emitir(PRINCIPAL)) == PRINCIPAL


def test_validade_de_quinze_minutos() -> None:
    relogio = RelogioFixo()
    emissor = _emissor(relogio)
    token = emissor.emitir(PRINCIPAL)
    relogio.avancar(15 * 60 + 29)
    assert emissor.verificar(token) == PRINCIPAL
    relogio.avancar(2)
    with pytest.raises(TokenInvalido):
        emissor.verificar(token)


def test_cabecalho_tem_es256_e_kid() -> None:
    cabecalho = jwt.get_unverified_header(_emissor(RelogioFixo()).emitir(PRINCIPAL))
    assert (cabecalho["alg"], cabecalho["kid"]) == ("ES256", "k1")


def test_alg_diferente_de_es256_e_recusado() -> None:
    relogio = RelogioFixo()
    emissor = _emissor(relogio)
    corpo = jwt.decode(emissor.emitir(PRINCIPAL), options={"verify_signature": False})
    for chave, alg in [("x" * 32, "HS256"), (PUB1 * 2, "HS512")]:
        with pytest.raises(TokenInvalido):
            emissor.verificar(_forjar_seguro(chave, alg, corpo))


def _forjar_seguro(chave: str, alg: str, corpo: dict[str, object]) -> str:
    import base64
    import hashlib
    import hmac
    import json

    def b64(dados: bytes) -> str:
        return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()

    topo = b64(json.dumps({"alg": alg, "kid": "k1"}).encode())
    meio = b64(json.dumps(corpo).encode())
    funcao = hashlib.sha256 if alg == "HS256" else hashlib.sha512
    assinatura = hmac.new(chave.encode(), f"{topo}.{meio}".encode(), funcao).digest()
    return f"{topo}.{meio}.{b64(assinatura)}"


def test_alg_none_e_recusado() -> None:
    relogio = RelogioFixo()
    emissor = _emissor(relogio)
    corpo = jwt.decode(emissor.emitir(PRINCIPAL), options={"verify_signature": False})
    import base64
    import json

    def b64(dados: bytes) -> str:
        return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()

    topo = b64(json.dumps({"alg": "none", "kid": "k1"}).encode())
    token = f"{topo}.{b64(json.dumps(corpo).encode())}."
    with pytest.raises(TokenInvalido):
        emissor.verificar(token)


def test_kid_desconhecido_e_recusado() -> None:
    relogio = RelogioFixo()
    outro = EmissorJwtEs256(ChavesEs256("k9", PRIV2), relogio, ISS, AUD)
    with pytest.raises(TokenInvalido):
        _emissor(relogio).verificar(outro.emitir(PRINCIPAL))


def test_assinatura_de_outra_chave_com_o_mesmo_kid_e_recusada() -> None:
    relogio = RelogioFixo()
    with pytest.raises(TokenInvalido):
        _emissor(relogio).verificar(_forjar(relogio, PRIV2, "ES256"))


@pytest.mark.parametrize("campo", ["iss", "aud"])
def test_iss_ou_aud_errados_sao_recusados(campo: str) -> None:
    relogio = RelogioFixo()
    with pytest.raises(TokenInvalido):
        _emissor(relogio).verificar(_forjar(relogio, PRIV1, "ES256", **{campo: "outro"}))


@pytest.mark.parametrize("claim", ["tid", "roles", "mfa", "sub", "exp", "jti"])
def test_claim_ausente_e_recusada(claim: str) -> None:
    relogio = RelogioFixo()
    agora = int(relogio.agora().timestamp())
    corpo = {
        "iss": ISS,
        "aud": AUD,
        "sub": str(PRINCIPAL.usuario_id),
        "tid": str(PRINCIPAL.tenant_id),
        "roles": ["aprovar"],
        "mfa": True,
        "iat": agora,
        "exp": agora + 900,
        "jti": "j",
    }
    del corpo[claim]
    with pytest.raises(TokenInvalido):
        _emissor(relogio).verificar(
            jwt.encode(corpo, PRIV1, algorithm="ES256", headers={"kid": "k1"})
        )


def test_papel_desconhecido_e_recusado() -> None:
    relogio = RelogioFixo()
    with pytest.raises(TokenInvalido):
        _emissor(relogio).verificar(_forjar(relogio, PRIV1, "ES256", roles=["superusuario"]))


def test_lixo_e_recusado() -> None:
    with pytest.raises(TokenInvalido):
        _emissor(RelogioFixo()).verificar("nao-e-jwt")


def test_rotacao_aceita_o_kid_anterior_ate_expirar() -> None:
    relogio = RelogioFixo()
    antigo = _emissor(relogio).emitir(PRINCIPAL)
    novas = ChavesEs256("k2", PRIV2, publicas_anteriores={"k1": PUB1})
    rotacionado = _emissor(relogio, novas)
    assert jwt.get_unverified_header(rotacionado.emitir(PRINCIPAL))["kid"] == "k2"
    assert rotacionado.verificar(antigo) == PRINCIPAL
    relogio.avancar(timedelta(minutes=16).total_seconds())
    with pytest.raises(TokenInvalido):
        rotacionado.verificar(antigo)


def test_jwks_publica_as_chaves_sem_parte_privada() -> None:
    novas = ChavesEs256("k2", PRIV2, publicas_anteriores={"k1": PUB1})
    jwks = _emissor(RelogioFixo(), novas).jwks()
    assert sorted(k["kid"] for k in jwks["keys"]) == ["k1", "k2"]
    assert all("d" not in k and k["alg"] == "ES256" for k in jwks["keys"])


def test_desafio_de_mfa_nao_serve_como_token_de_acesso() -> None:
    relogio = RelogioFixo()
    emissor = _emissor(relogio)
    desafio = emissor.emitir_desafio(PRINCIPAL.usuario_id)
    assert emissor.verificar_desafio(desafio) == PRINCIPAL.usuario_id
    with pytest.raises(TokenInvalido):
        emissor.verificar(desafio)
    with pytest.raises(TokenInvalido):
        emissor.verificar_desafio(emissor.emitir(PRINCIPAL))


def test_desafio_vale_cinco_minutos() -> None:
    relogio = RelogioFixo()
    emissor = _emissor(relogio)
    desafio = emissor.emitir_desafio(PRINCIPAL.usuario_id)
    relogio.avancar(5 * 60 + 31)
    with pytest.raises(TokenInvalido):
        emissor.verificar_desafio(desafio)


def test_estado_de_federacao_faz_ida_e_volta_e_nao_serve_para_outro_fim() -> None:
    from dynaprice.aplicacao.portas.oidc import EstadoDeFederacao

    emissor = _emissor(RelogioFixo())
    estado = EstadoDeFederacao("st", "no", "v" * 43)
    token = emissor.emitir_estado_de_federacao(estado)
    assert emissor.verificar_estado_de_federacao(token) == estado
    for outro in (emissor.emitir(PRINCIPAL), emissor.emitir_desafio(PRINCIPAL.usuario_id)):
        with pytest.raises(TokenInvalido):
            emissor.verificar_estado_de_federacao(outro)
    with pytest.raises(TokenInvalido):
        emissor.verificar(token)
    with pytest.raises(TokenInvalido):
        emissor.verificar_desafio(token)


def test_estado_de_federacao_vale_dez_minutos() -> None:
    from dynaprice.aplicacao.portas.oidc import EstadoDeFederacao

    relogio = RelogioFixo()
    emissor = _emissor(relogio)
    token = emissor.emitir_estado_de_federacao(EstadoDeFederacao("a", "b", "c"))
    relogio.avancar(10 * 60 + 31)
    with pytest.raises(TokenInvalido):
        emissor.verificar_estado_de_federacao(token)
