import { describe, expect, it } from "vitest";
import { moeda, percentual } from "./formato";

const normalizar = (texto: string) => texto.replace(/ /g, " ");

describe("formato pt-BR", () => {
  it("formata moeda a partir do texto decimal da API", () => {
    expect(normalizar(moeda("1502.55"))).toBe("R$ 1.502,55");
  });

  it("formata percentual", () => {
    expect(normalizar(percentual("0.125"))).toBe("12,5%");
  });

  it("não formata valor ausente como zero", () => {
    expect(moeda(null)).toBe("—");
    expect(percentual(undefined)).toBe("—");
  });
});
