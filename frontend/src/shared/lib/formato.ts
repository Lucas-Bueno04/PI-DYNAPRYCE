const MOEDA = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const PERCENTUAL = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 2 });
const NUMERO = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 });
const AUSENTE = "—";

type Valor = string | number | null | undefined;

function formatar(valor: Valor, formato: Intl.NumberFormat): string {
  return valor === null || valor === undefined ? AUSENTE : formato.format(Number(valor));
}

export const moeda = (valor: Valor) => formatar(valor, MOEDA);
export const percentual = (valor: Valor) => formatar(valor, PERCENTUAL);
export const numero = (valor: Valor) => formatar(valor, NUMERO);
