"""Erros dos casos de uso; a borda HTTP os traduz em Problem Details."""


class ErroDeAplicacao(Exception):
    """Raiz dos erros esperados dos casos de uso."""


class NaoAutenticado(ErroDeAplicacao):
    """Credencial ou sessão inválida. A mensagem pública não diz qual."""


class AcessoNegado(ErroDeAplicacao):
    """Autenticado, mas sem permissão para a ação."""


class NaoEncontrado(ErroDeAplicacao):
    """Recurso inexistente (ou de outro inquilino, o que dá no mesmo)."""


class Conflito(ErroDeAplicacao):
    """A requisição não vale no estado atual (ex.: versão desatualizada)."""


class RenovacaoConcorrente(Conflito):
    """Duas abas renovaram juntas: esta reapresentou um token rotacionado há poucos segundos."""


class MuitasTentativas(ErroDeAplicacao):
    """Bloqueio progressivo por força bruta."""

    def __init__(self, espera_s: int) -> None:
        super().__init__("muitas tentativas")
        self.espera_s = espera_s
