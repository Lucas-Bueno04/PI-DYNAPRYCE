import { useSyncExternalStore } from "react";

// Token de acesso só em memória (ADR-002): nunca em localStorage ou sessionStorage.
let acesso: string | null = null;
const ouvintes = new Set<() => void>();

function avisar() {
  ouvintes.forEach((ouvinte) => ouvinte());
}

export function definirAcesso(token: string) {
  acesso = token;
  avisar();
}

export function obterAcesso() {
  return acesso;
}

export function limparSessao() {
  acesso = null;
  avisar();
}

export interface Claims {
  roles: string[];
  mfa: boolean;
}

/** Só para decidir o que mostrar: quem autoriza é o backend. */
export function lerClaims(token: string | null): Claims | null {
  const corpo = token?.split(".")[1];
  if (!corpo) return null;
  try {
    return JSON.parse(atob(corpo.replace(/-/g, "+").replace(/_/g, "/"))) as Claims;
  } catch {
    return null;
  }
}

export function useClaims(): Claims | null {
  const token = useSyncExternalStore(
    (ouvinte) => {
      ouvintes.add(ouvinte);
      return () => ouvintes.delete(ouvinte);
    },
    () => acesso,
  );
  return lerClaims(token);
}
