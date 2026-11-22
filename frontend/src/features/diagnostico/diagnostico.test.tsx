import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Diagnostico } from "./Diagnostico";

const RELATORIO = {
  titulo: "Relatório do laboratório",
  secoes: [
    {
      titulo: "Tarifa",
      itens: [{ rotulo: "τ̂", valor: "103,50", fonte: "Eq. 66" }],
      tabelas: [
        { titulo: "Pisos", colunas: ["Regime", "Piso"], linhas: [["LP", "235"]], fonte: "D2" },
      ],
    },
  ],
};

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
});

describe("diagnóstico", () => {
  it("mostra as seções com a fonte de cada número, iguais às da cli", async () => {
    const pedidos = simularApi({ "GET /api/v1/diagnostico": [200, RELATORIO] });
    renderizar(<Diagnostico referencia="2027-01" />);
    expect(await screen.findByText("Tarifa")).toBeInTheDocument();
    expect(screen.getByText("103,50")).toBeInTheDocument();
    expect(screen.getByText("Eq. 66")).toBeInTheDocument();
    expect(screen.getByText("235")).toBeInTheDocument();
    expect(pedidos[0]?.caminho).toBe("/api/v1/diagnostico");
  });

  it("avisa quando falha", async () => {
    simularApi({ "GET /api/v1/diagnostico": [500, { status: 500 }] });
    renderizar(<Diagnostico referencia="2027-01" />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
