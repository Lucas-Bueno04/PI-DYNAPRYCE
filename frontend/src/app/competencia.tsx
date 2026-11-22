import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

interface Valor {
  competencia: string;
  definir: (competencia: string) => void;
  opcoes: string[];
}

const CHAVE = "dynaprice.competencia";
const Contexto = createContext<Valor | null>(null);

function partes(competencia: string): [number, number] {
  const [ano = 0, mes = 1] = competencia.split("-").map(Number);
  return [ano, mes];
}

function texto(data: Date): string {
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, "0")}`;
}

/** Mês anterior ao atual: a competência fechada mais recente. */
export function competenciaAnterior(hoje = new Date()): string {
  return texto(new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1));
}

export function listarCompetencias(base: string, quantidade = 36): string[] {
  const [ano, mes] = partes(base);
  return Array.from({ length: quantidade }, (_, i) => texto(new Date(ano, mes - 1 - i, 1)));
}

function lembrada(): string | null {
  try {
    const valor = window.localStorage.getItem(CHAVE);
    return valor && /^\d{4}-\d{2}$/.test(valor) ? valor : null;
  } catch {
    return null;
  }
}

export function ProvedorDeCompetencia({ children }: { children: ReactNode }) {
  const [competencia, setCompetencia] = useState(() => lembrada() ?? competenciaAnterior());
  const opcoes = useMemo(() => {
    const base = listarCompetencias(competenciaAnterior());
    return base.includes(competencia) ? base : [competencia, ...base];
  }, [competencia]);
  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE, competencia);
    } catch {
      /* sem armazenamento: a escolha vale só nesta sessão */
    }
  }, [competencia]);
  return <Contexto.Provider value={{ competencia, definir: setCompetencia, opcoes }}>{children}</Contexto.Provider>;
}

export function useCompetencia(): Valor {
  const valor = useContext(Contexto);
  if (!valor) throw new Error("useCompetencia fora do ProvedorDeCompetencia");
  return valor;
}

export function rotuloDaCompetencia(competencia: string): string {
  const [ano, mes] = partes(competencia);
  return new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", { month: "short", year: "numeric" }).replace(".", "");
}
