"""D-ROT-CHAVE: recifra credenciais de conector e TOTP com a chave nova."""

from uuid import uuid4

from dynaprice.adaptadores.saida.seguranca import CifradorAesGcm
from dynaprice.aplicacao.casos_de_uso.autenticacao.base import contexto_totp
from dynaprice.aplicacao.casos_de_uso.conectores import ConfigurarConector
from dynaprice.aplicacao.casos_de_uso.rotacionar_chave import RotacionarChaveMestra
from dynaprice.dominio.modelos.autenticacao import Papel, Principal, Usuario
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.aplicacao.preco_apoio import preco as preco

K1, K2 = bytes(range(32)), bytes(32)  # K1 é a chave dos demais testes no mesmo banco


def test_rotacao_recifra_e_a_chave_antiga_sai(preco: CenarioDePreco) -> None:
    antigo = CifradorAesGcm({"k1": K1})
    admin = Principal(uuid4(), preco.tenant, frozenset({Papel.ADMINISTRAR}), True)
    ConfigurarConector(preco.fabrica, antigo).executar(admin, "omie", {"s": "x"}, {}, 5)
    usuario = Usuario(uuid4(), f"{uuid4()}@t.com", "h")
    usuario_com_totp = Usuario(
        usuario.id,
        usuario.email,
        "h",
        totp_cifrado=antigo.cifrar(b"segredo", contexto_totp(usuario.id)),
        mfa_ativo=True,
    )
    with preco.fabrica.sem_tenant() as uow:
        uow.usuarios.criar(usuario_com_totp)
    novo = CifradorAesGcm({"k1": K1, "k2": K2})
    assert RotacionarChaveMestra(preco.fabrica, novo).executar() >= 2
    somente_nova = CifradorAesGcm({"k2": K2})
    with preco.fabrica.sem_tenant() as uow:
        lido = uow.usuarios.obter(usuario.id)
    assert lido is not None and lido.totp_cifrado is not None
    assert somente_nova.decifrar(lido.totp_cifrado, contexto_totp(usuario.id)) == b"segredo"
    with preco.fabrica.para_tenant(preco.tenant) as uow:
        conector = uow.conectores.obter("omie")
    assert conector is not None and conector.credencial_cifrada is not None
    assert (
        somente_nova.decifrar(conector.credencial_cifrada, f"conector:{preco.tenant}:omie")
        == b'{"s": "x"}'
    )
