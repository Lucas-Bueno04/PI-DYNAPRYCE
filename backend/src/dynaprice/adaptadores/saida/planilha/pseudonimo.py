"""Pseudonimização do CPF/CNPJ na entrada (D8; plano §5): HMAC-SHA256 com chave fora do repositório.

O mesmo documento gera sempre o mesmo pseudônimo com a mesma chave (junção entre arquivos e
meses), e o documento não pode ser recuperado sem a chave.
"""

import hashlib
import hmac

from dynaprice.dominio.modelos import ValorInvalido

_TAMANHO_MINIMO_DA_CHAVE = 16
_CARACTERES = 20


class Pseudonimizador:
    def __init__(self, chave: bytes) -> None:
        if len(chave) < _TAMANHO_MINIMO_DA_CHAVE:
            raise ValorInvalido(
                f"chave de pseudonimização com menos de {_TAMANHO_MINIMO_DA_CHAVE} bytes"
            )
        self._chave = chave

    def pseudonimo(self, documento: str) -> str:
        digitos = "".join(c for c in documento if c.isdigit())
        if not digitos:
            raise ValorInvalido("documento sem dígitos")
        resumo = hmac.new(self._chave, digitos.encode(), hashlib.sha256).hexdigest()
        return f"P{resumo[:_CARACTERES]}"
