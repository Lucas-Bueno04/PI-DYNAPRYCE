import createClient from "openapi-fetch";
import type { paths } from "./esquema";
import { definirAcesso, limparSessao, obterAcesso } from "./sessao";

const ROTA_DE_RENOVACAO = "/api/v1/auth/renovar";
const PREFIXO_DE_AUTH = "/api/v1/auth/";
const ESPERA_ENTRE_ABAS_MS = 300;

let renovacaoEmCurso: Promise<boolean> | null = null;

async function pedirRenovacao(): Promise<Response> {
  return globalThis.fetch(
    new Request(`${window.location.origin}${ROTA_DE_RENOVACAO}`, {
      method: "POST",
      credentials: "same-origin",
    }),
  );
}

async function renovarUmaVez(): Promise<boolean> {
  let resposta = await pedirRenovacao();
  if (resposta.status === 409) {
    // Outra aba acabou de renovar: o cookie novo já chegou.
    await new Promise((resolver) => setTimeout(resolver, ESPERA_ENTRE_ABAS_MS));
    resposta = await pedirRenovacao();
  }
  if (!resposta.ok) {
    limparSessao();
    return false;
  }
  const corpo = (await resposta.json()) as { acesso: string };
  definirAcesso(corpo.acesso);
  return true;
}

/** Várias chamadas com 401 compartilham uma única renovação. */
export function renovarSessao(): Promise<boolean> {
  renovacaoEmCurso ??= renovarUmaVez().finally(() => {
    renovacaoEmCurso = null;
  });
  return renovacaoEmCurso;
}

function comToken(pedido: Request): Request {
  const copia = new Request(pedido);
  const token = obterAcesso();
  if (token) copia.headers.set("Authorization", `Bearer ${token}`);
  return copia;
}

async function requisitar(pedido: Request): Promise<Response> {
  const reserva = pedido.clone();
  const tokenUsado = obterAcesso();
  const resposta = await globalThis.fetch(comToken(pedido));
  const caminho = new URL(pedido.url).pathname;
  if (resposta.status !== 401 || caminho.startsWith(PREFIXO_DE_AUTH)) return resposta;
  // Se outro pedido já renovou enquanto este voava, basta reenviar com o token novo.
  const renovado = obterAcesso() !== tokenUsado || (await renovarSessao());
  return renovado ? globalThis.fetch(comToken(reserva)) : resposta;
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: requisitar,
  credentials: "same-origin",
});
