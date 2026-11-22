import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProvedorDeCompetencia } from "../../app/competencia";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Clientes } from "./Clientes";

const base = { empresas: 1, cobrado: "400.00", mes_reajuste: 3, provisorio: false, kappa: "1", recomendacao: null };
const LISTA = [
  { ...base, contrato_id: "C0001", regime: "SN", preco_vigente: "400.00", preco_alvo: "500.00", defasagem_pct: "-20.0" },
  { ...base, contrato_id: "C0002", regime: "LP", preco_vigente: "500.00", preco_alvo: "500.00", defasagem_pct: "0.0" },
  { ...base, contrato_id: "C0003", regime: "LP", preco_vigente: "300.00", preco_alvo: null, defasagem_pct: null },
];

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
});

describe("clientes", () => {
  it("lista os contratos com a situação frente ao alvo", async () => {
    simularApi({ "GET /api/v1/clientes": [200, LISTA] });
    renderizar(<ProvedorDeCompetencia><Clientes /></ProvedorDeCompetencia>);
    expect(await screen.findByText("C0001")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /C0001/ })).toHaveTextContent("Muito abaixo");
    expect(screen.getByRole("row", { name: /C0002/ })).toHaveTextContent("No alvo");
    expect(screen.getByRole("row", { name: /C0003/ })).toHaveTextContent("Sem alvo");
  });

  it("busca pelo código do contrato", async () => {
    simularApi({ "GET /api/v1/clientes": [200, LISTA] });
    renderizar(<ProvedorDeCompetencia><Clientes /></ProvedorDeCompetencia>);
    await screen.findByText("C0001");
    await userEvent.type(screen.getByLabelText("Buscar contrato"), "C0002");
    expect(screen.queryByText("C0001")).not.toBeInTheDocument();
    expect(screen.getByText("C0002")).toBeInTheDocument();
  });

  it("abre o detalhe do contrato ao clicar na linha", async () => {
    simularApi({ "GET /api/v1/clientes": [200, LISTA] });
    renderizar(<ProvedorDeCompetencia><Clientes /></ProvedorDeCompetencia>);
    await userEvent.click(await screen.findByText("C0001"));
    expect(await screen.findByText("Contrato C0001")).toBeInTheDocument();
    expect(screen.getByText(/não guarda nome nem CNPJ/)).toBeInTheDocument();
  });
});
