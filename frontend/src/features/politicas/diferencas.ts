export interface Diferenca {
  campo: string;
  antes: string;
  depois: string;
}

const AUSENTE = "—";

function achatar(valor: unknown, prefixo = ""): Map<string, string> {
  const saida = new Map<string, string>();
  if (typeof valor === "object" && valor !== null) {
    for (const [chave, item] of Object.entries(valor)) {
      const caminho = prefixo ? `${prefixo}.${chave}` : chave;
      achatar(item, caminho).forEach((v, k) => saida.set(k, v));
    }
  } else {
    saida.set(prefixo, String(valor));
  }
  return saida;
}

export function diferencas(antes: unknown, depois: unknown): Diferenca[] {
  const a = achatar(antes);
  const b = achatar(depois);
  return [...new Set([...a.keys(), ...b.keys()])]
    .sort()
    .filter((campo) => a.get(campo) !== b.get(campo))
    .map((campo) => ({
      campo,
      antes: a.get(campo) ?? AUSENTE,
      depois: b.get(campo) ?? AUSENTE,
    }));
}
