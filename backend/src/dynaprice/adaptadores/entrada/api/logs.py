"""Logs estruturados sem dado pessoal nem segredo (S7, D8)."""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_CHAVES_PROIBIDAS = {
    "email",
    "e_mail",
    "senha",
    "password",
    "token",
    "refresh",
    "acesso",
    "authorization",
    "cookie",
    "cpf",
    "cnpj",
    "documento",
    "totp",
    "codigo",
    "segredo",
    "credencial",
}
_PADROES = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+\b"),
)
_MASCARA = "***"
_LOGGERS_DO_UVICORN = ("uvicorn", "uvicorn.error")  # o de acesso fica desligado: tem IP


def _limpar_texto(valor: str) -> str:
    for padrao in _PADROES:
        valor = padrao.sub(_MASCARA, valor)
    return valor


def _limpar(valor: Any) -> Any:
    if isinstance(valor, str):
        return _limpar_texto(valor)
    if isinstance(valor, dict):
        return {
            chave: _MASCARA if str(chave).lower() in _CHAVES_PROIBIDAS else _limpar(item)
            for chave, item in valor.items()
        }
    if isinstance(valor, list | tuple):
        return [_limpar(item) for item in valor]
    return valor


def limpar_evento(
    _logger: Any, _metodo: str, evento: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Processador do structlog: última barreira, depois de todo enriquecimento."""
    limpo: dict[str, Any] = _limpar(dict(evento))
    return limpo


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Saída JSON em stderr, inclusive dos logs da biblioteca padrão (uvicorn, psycopg)."""
    formatador = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[structlog.stdlib.add_log_level, structlog.processors.TimeStamper()],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,  # o traceback vira texto e passa pela limpeza
            limpar_evento,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )
    saida = logging.StreamHandler(sys.stderr)
    saida.setFormatter(formatador)
    raiz = logging.getLogger()
    raiz.handlers[:] = [saida]
    raiz.setLevel(nivel)
    for nome in _LOGGERS_DO_UVICORN:  # por padrão não propagam e escapariam da limpeza
        logger = logging.getLogger(nome)
        logger.handlers.clear()
        logger.propagate = True
