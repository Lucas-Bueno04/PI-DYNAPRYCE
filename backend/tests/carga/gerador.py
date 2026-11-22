"""Gerador de carga da cotação (F2.6, RNF02): taxa fixa (open-loop), p95 e taxa de erro.

Uso: `python -m tests.carga.gerador --url https://localhost:8443 --tenant <uuid>
--chave deploy/compose/segredos/chave_es256` contra o compose em pé.
"""

import argparse
import asyncio
import math
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

P95_MAXIMO_MS = 300.0
ERRO_MAXIMO = 0.005
ROTA = "/api/v1/cotacoes"

CORPOS: tuple[dict[str, Any], ...] = (
    {"regime": "LP"},
    {"regime": "SN", "meses": 4, "horas_padrao": "3"},
    {"regime": "LR", "meses": 8, "horas_padrao": "6.5", "kappa": "1.1"},
    {"regime": "MEI", "meses": 12, "horas_padrao": "1"},
)


@dataclass(slots=True)
class Medida:
    latencias_ms: list[float] = field(default_factory=list)
    erros: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class Veredito:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    taxa_de_erro: float
    aprovado: bool


def percentil(valores: Sequence[float], p: float) -> float:
    """Posto mais próximo: o menor valor com ao menos p% das amostras abaixo ou iguais."""
    if not valores:
        raise ValueError("sem amostras")
    ordem = sorted(valores)
    return ordem[max(0, math.ceil(p / 100 * len(ordem)) - 1)]


def veredito(medida: Medida) -> Veredito:
    taxa = medida.erros / medida.total if medida.total else 1.0
    lat = medida.latencias_ms or [math.inf]
    p95 = percentil(lat, 95)
    return Veredito(
        percentil(lat, 50),
        p95,
        percentil(lat, 99),
        taxa,
        p95 < P95_MAXIMO_MS and taxa < ERRO_MAXIMO,
    )


async def _um_pedido(
    http: httpx.AsyncClient, token: str, corpo: dict[str, Any], medida: Medida
) -> None:
    inicio = time.perf_counter()
    try:
        resposta = await http.post(ROTA, json=corpo, headers={"Authorization": f"Bearer {token}"})
        ok = resposta.status_code == 201
    except httpx.HTTPError:
        ok = False
    if ok:
        medida.latencias_ms.append((time.perf_counter() - inicio) * 1000)
    else:
        medida.erros += 1


async def rodar(
    http: httpx.AsyncClient,
    token: str,
    taxa: float,
    duracao_s: float,
    corpos: Sequence[dict[str, Any]] = CORPOS,
) -> Medida:
    """Open-loop: o pedido i sai em i/taxa, mesmo que os anteriores ainda não tenham voltado."""
    medida = Medida()
    pedidos = round(taxa * duracao_s)
    inicio = time.perf_counter()
    tarefas = []
    for i in range(pedidos):
        await asyncio.sleep(max(0.0, inicio + i / taxa - time.perf_counter()))
        tarefas.append(
            asyncio.create_task(_um_pedido(http, token, corpos[i % len(corpos)], medida))
        )
    await asyncio.gather(*tarefas)
    medida.total = pedidos
    return medida


def _token(chave: Path, tenant: UUID) -> str:
    from dynaprice.adaptadores.saida.relogio import RelogioDoSistema
    from dynaprice.adaptadores.saida.seguranca import EmissorJwtEs256, carregar_chaves_es256
    from dynaprice.dominio.modelos.autenticacao import Papel, Principal
    from dynaprice.principal.api import AUDIENCIA_JWT, EMISSOR_JWT

    emissor = EmissorJwtEs256(
        carregar_chaves_es256(chave), RelogioDoSistema(), EMISSOR_JWT, AUDIENCIA_JWT
    )
    return emissor.emitir(Principal(uuid4(), tenant, frozenset({Papel.APROVAR}), True))


async def _publicar_politica(http: httpx.AsyncClient, token: str) -> None:
    from tests.dominio.modelos.documentos import documento_tabela_7

    cabecalho = {"Authorization": f"Bearer {token}"}
    criada = await http.post(
        "/api/v1/politicas", json={"documento": documento_tabela_7()}, headers=cabecalho
    )
    criada.raise_for_status()
    versao = criada.json()["versao"]
    (await http.post(f"/api/v1/politicas/{versao}/publicar", headers=cabecalho)).raise_for_status()


async def _principal(argumentos: argparse.Namespace) -> int:
    token = _token(argumentos.chave, UUID(argumentos.tenant))
    async with httpx.AsyncClient(
        base_url=argumentos.url, verify=not argumentos.sem_verificar_tls, timeout=10
    ) as http:
        if argumentos.publicar_politica:
            await _publicar_politica(http, token)
        await rodar(http, token, 5, 2)  # aquecimento: conexões e política em memória
        medida = await rodar(http, token, argumentos.taxa, argumentos.duracao)
    v = veredito(medida)
    print(
        f"pedidos={medida.total} erros={medida.erros} ({v.taxa_de_erro:.2%}) "
        f"p50={v.p50_ms:.1f}ms p95={v.p95_ms:.1f}ms p99={v.p99_ms:.1f}ms "
        f"=> {'APROVADO' if v.aprovado else 'REPROVADO'} "
        f"(p95 < {P95_MAXIMO_MS:.0f} ms, erro < 0,5%)"
    )
    return 0 if v.aprovado else 1


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--url", default="https://localhost:8443")
    analisador.add_argument("--tenant", required=True)
    analisador.add_argument("--chave", type=Path, required=True)
    analisador.add_argument("--taxa", type=float, default=20.0)
    analisador.add_argument("--duracao", type=float, default=60.0)
    analisador.add_argument("--publicar-politica", action="store_true")
    analisador.add_argument("--sem-verificar-tls", action="store_true")
    return asyncio.run(_principal(analisador.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
