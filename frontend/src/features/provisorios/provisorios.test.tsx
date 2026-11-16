import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Provisorios } from "./Provisorios";

const ITEM = { contrato_id: "P1", preco_vigente: "437.00", esforco: "614.27", diferenca: "177.27", meses: 6 };
const texto = (t: string | null) => (t ?? "").replace(/ /g, " ");

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
});

describe("provisórios abaixo do esforço", () => {
  it("lista os contratos com a diferença e pede a competência de referência", async () => {
    const pedidos = simularApi({ "GET /api/v1/relatorios/provisorios": [200, [ITEM]] });
    renderizar(<Provisorios referencia="2027-01" />);
    const linha = await screen.findByRole("row", { name: /P1/ });
    expect(texto(linha.textContent)).toContain("R$ 437,00");
    expect(texto(linha.textContent)).toContain("R$ 614,27");
    expect(texto(linha.textContent)).toContain("R$ 177,27");
    expect(texto(screen.getByTestId("total").textContent)).toContain("R$ 177,27");
    expect(pedidos[0]?.caminho).toBe("/api/v1/relatorios/provisorios");
  });

  it("sem itens diz que nenhum provisório está abaixo do esforço", async () => {
    simularApi({ "GET /api/v1/relatorios/provisorios": [200, []] });
    renderizar(<Provisorios referencia="2027-01" />);
    expect(await screen.findByText("Nenhum provisório abaixo do esforço medido.")).toBeInTheDocument();
  });
});
