import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

export interface PedidoRecebido {
  metodo: string;
  caminho: string;
  corpo: unknown;
  cabecalhos: Headers;
}

type Resposta = readonly [number, unknown?];
type Rota = Resposta | ((pedido: PedidoRecebido) => Resposta);

/** Substitui o fetch: cada chave é "MÉTODO /api/v1/caminho". */
export function simularApi(rotas: Record<string, Rota>): PedidoRecebido[] {
  const pedidos: PedidoRecebido[] = [];
  vi.stubGlobal("fetch", async (entrada: Request) => {
    const url = new URL(entrada.url);
    const texto = await entrada.clone().text();
    const pedido: PedidoRecebido = {
      metodo: entrada.method,
      caminho: url.pathname,
      corpo: texto ? tentarJson(texto) : undefined,
      cabecalhos: entrada.headers,
    };
    pedidos.push(pedido);
    const rota = rotas[`${entrada.method} ${url.pathname}`];
    if (rota === undefined) return new Response(null, { status: 404 });
    const [status, corpo] = typeof rota === "function" ? rota(pedido) : rota;
    return new Response(corpo === undefined ? null : JSON.stringify(corpo), {
      status,
      headers: { "content-type": "application/json" },
    });
  });
  return pedidos;
}

function tentarJson(texto: string): unknown {
  try {
    return JSON.parse(texto);
  } catch {
    return texto;
  }
}

/** Token sem assinatura válida: a interface só lê as claims para exibir. */
export function tokenFalso(claims: { roles: string[]; mfa: boolean }): string {
  const corpo = btoa(JSON.stringify({ sub: "u1", tid: "t1", ...claims }));
  return `h.${corpo}.a`;
}

export function renderizar(ui: ReactNode, rota = "/") {
  const consultas = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider env="test">
      <QueryClientProvider client={consultas}>
        <MemoryRouter initialEntries={[rota]}>{ui}</MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}
