import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Cotacao } from "./Cotacao";

const SEM_HISTORICO = {
  id: "c1",
  preco: "235.00",
  politica_versao: 3,
  provisorio: true,
  decomposicao: {
    nivel_informacao: 0,
    regime: "LP",
    meses: 0,
    piso: "235.00",
    tarifa: "103.5",
    horas_padrao: null,
    base_propria: null,
    piso_vinculante: null,
    credibilidade_z: "0",
    kappa: "1",
    preco_exato: "235",
    preco: "235.00",
    provisorio: true,
    motivo: "sem histórico: preço provisório igual ao piso do regime",
  },
};
const PARCIAL = {
  ...SEM_HISTORICO,
  preco: "285.33",
  decomposicao: {
    ...SEM_HISTORICO.decomposicao,
    nivel_informacao: 1,
    meses: 4,
    horas_padrao: "3",
    base_propria: "310.50",
    piso_vinculante: false,
    credibilidade_z: "0.6666666666666666666666666667",
    motivo: "histórico parcial: mistura do esforço medido e do piso do regime",
  },
};

const texto = (t: string | null) => (t ?? "").replace(/\u00a0/g, " ");

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
});

describe("cotação", () => {
  it("sem histórico cota o piso do regime e marca como provisório", async () => {
    const pedidos = simularApi({ "POST /api/v1/cotacoes": [201, SEM_HISTORICO] });
    renderizar(<Cotacao />);
    await userEvent.selectOptions(screen.getByLabelText("Regime tributário"), "LP");
    await userEvent.click(screen.getByRole("button", { name: "Cotar" }));
    const painel = await screen.findByTestId("cotacao");
    expect(texto(painel.textContent)).toContain("R$ 235,00");
    expect(painel).toHaveTextContent("Provisório");
    expect(painel).toHaveTextContent("piso do regime");
    expect(painel).toHaveTextContent("política v3");
    expect(pedidos[0]?.corpo).toEqual({ regime: "LP", meses: 0 });
  });

  it("o regime é obrigatório e nada é enviado sem ele", async () => {
    const pedidos = simularApi({});
    renderizar(<Cotacao />);
    await userEvent.click(screen.getByRole("button", { name: "Cotar" }));
    expect(await screen.findByText("Informe o regime tributário")).toBeInTheDocument();
    expect(pedidos).toHaveLength(0);
  });

  it("com histórico, exige as horas-padrão", async () => {
    const pedidos = simularApi({});
    renderizar(<Cotacao />);
    await userEvent.selectOptions(screen.getByLabelText("Regime tributário"), "LP");
    await userEvent.clear(screen.getByLabelText("Meses de histórico"));
    await userEvent.type(screen.getByLabelText("Meses de histórico"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Cotar" }));
    expect(await screen.findByText("Informe as horas-padrão mensais")).toBeInTheDocument();
    expect(pedidos).toHaveLength(0);
  });

  it("histórico parcial mostra credibilidade, base própria e piso", async () => {
    const pedidos = simularApi({ "POST /api/v1/cotacoes": [201, PARCIAL] });
    renderizar(<Cotacao />);
    await userEvent.selectOptions(screen.getByLabelText("Regime tributário"), "LP");
    await userEvent.clear(screen.getByLabelText("Meses de histórico"));
    await userEvent.type(screen.getByLabelText("Meses de histórico"), "4");
    await userEvent.type(screen.getByLabelText("Horas-padrão mensais"), "3");
    await userEvent.click(screen.getByRole("button", { name: "Cotar" }));
    const painel = await screen.findByTestId("cotacao");
    expect(texto(painel.textContent)).toContain("R$ 285,33");
    expect(texto(painel.textContent)).toContain("66,67%");
    expect(texto(painel.textContent)).toContain("R$ 310,50");
    expect(pedidos[0]?.corpo).toEqual({ regime: "LP", meses: 4, horas_padrao: "3" });
  });

  it("envia κ quando informado", async () => {
    const pedidos = simularApi({ "POST /api/v1/cotacoes": [201, PARCIAL] });
    renderizar(<Cotacao />);
    await userEvent.selectOptions(screen.getByLabelText("Regime tributário"), "SN");
    await userEvent.type(screen.getByLabelText("κ (opcional)"), "1.1");
    await userEvent.click(screen.getByRole("button", { name: "Cotar" }));
    await screen.findByTestId("cotacao");
    expect(pedidos[0]?.corpo).toEqual({ regime: "SN", meses: 0, kappa: "1.1" });
  });

  it("sem política publicada avisa em vez de mostrar preço", async () => {
    simularApi({ "POST /api/v1/cotacoes": [409, { status: 409, title: "conflito" }] });
    renderizar(<Cotacao />);
    await userEvent.selectOptions(screen.getByLabelText("Regime tributário"), "LP");
    await userEvent.click(screen.getByRole("button", { name: "Cotar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("política");
    expect(screen.queryByTestId("cotacao")).toBeNull();
  });
});
