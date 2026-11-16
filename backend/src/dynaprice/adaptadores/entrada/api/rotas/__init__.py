"""Roteadores da API v1, na ordem em que entram na aplicação (um lugar só para registrar)."""

from fastapi import APIRouter

from dynaprice.adaptadores.entrada.api.rotas import (
    auth,
    cotacoes,
    federacao,
    operacao,
    precificacao,
    saude,
    usuarios,
)

ROTEADORES: tuple[APIRouter, ...] = (
    saude.roteador,
    auth.roteador,
    federacao.roteador,
    usuarios.roteador,
    precificacao.roteador,
    cotacoes.roteador,
    operacao.roteador,
)
