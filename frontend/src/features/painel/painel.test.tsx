import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProvedorDeCompetencia } from "../../app/competencia";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Painel } from "./Painel";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="grafico" /> }));

const CLIENTE = {
  contrato_id: "C0007", regime: "LP", empresas: 1, preco_vigente: "400.00", preco_alvo: "500.00", defasagem_pct: "-20.0",
  cobrado: "400.00", mes_reajuste: 3, provisorio: false, kappa: "1", recomendacao: null,
};
const PAINEL = {
  competencia: "2025-12", empresas: 10, contratos: 8, provisorios: 2, receita_mensal: "4000.00", receita_alvo: "5000.00",
  potencial_de_reajuste: "1000.00", alertas: 1, competencias_com_dados: ["2025-12"],
  por_regime: [{ regime: "LP", empresas: 10, contratos: 8, receita: "4000.00" }],
  serie_receita: [{ competencia: "2025-12", valor: "4000.00" }],
  faixas: [{ rotulo: "Muito abaixo do alvo (< -15%)", contratos: 1 }],
  recomendacoes: { pendente: 3 }, divergencias: { aberta: 1 }, maiores_defasagens: [CLIENTE],
};

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
});

describe("painel", () => {
  it("mostra os indicadores, os gráficos e as maiores defasagens", async () => {
    const pedidos = simularApi({ "GET /api/v1/painel": [200, PAINEL] });
    renderizar(<ProvedorDeCompetencia><Painel /></ProvedorDeCompetencia>);
    expect(await screen.findByText("Receita mensal")).toBeInTheDocument();
    expect(screen.getByText(/R\$\s*4\.000,00/)).toBeInTheDocument();
    expect(screen.getByText("Potencial de reajuste")).toBeInTheDocument();
    expect(screen.getAllByTestId("grafico")).toHaveLength(4);
    expect(screen.getByText("C0007")).toBeInTheDocument();
    expect(pedidos[0]?.caminho).toBe("/api/v1/painel");
  });

  it("avisa quando o painel não carrega", async () => {
    simularApi({ "GET /api/v1/painel": [500] });
    renderizar(<ProvedorDeCompetencia><Painel /></ProvedorDeCompetencia>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o painel.");
  });
});
