"""Adaptador do provedor OIDC."""

from dynaprice.adaptadores.saida.oidc.provedor import (
    ConfiguracaoOidc,
    ProvedorOidcHttp,
    descobrir_configuracao,
)

__all__ = ["ConfiguracaoOidc", "ProvedorOidcHttp", "descobrir_configuracao"]
