import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Laboratorio } from "./Laboratorio";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="grafico" /> }));

const POLITICA = {
  versao: 1,
  estado: "publicada",
  documento: { tarifa_hora_padrao: { valor: "103.5" } },
  portao_aceite: null,
  relatorio: null,
};
const RESULTADO = {
  contratos: 500,
  receita_vigente: "100000.00",
  receita_alvo: "120000.00",
  receita_ciclo_1: "110000.00",
  fracao_no_piso: "0.25",
  fracao_no_teto: "0.5",
  fracao_congelados: "0.1",
  fracao_gatilho: "0.6",
  ciclos_mediana: 3,
  ciclos_maximo: 7,
};

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
});

const texto = (t: string | null) => (t ?? "").replace(/ /g, " ");

describe("laboratório", () => {
  it("edita o rascunho, simula e mostra os números da API", async () => {
    const pedidos = simularApi({
      "GET /api/v1/politicas": [200, [POLITICA]],
      "POST /api/v1/laboratorio/simulacoes": [200, RESULTADO],
    });
    renderizar(<Laboratorio referencia="2027-01" />);
    const campo = (await screen.findByLabelText("Documento da política")) as HTMLTextAreaElement;
    await waitFor(() => expect(campo.value).toContain("103.5"));
    fireEvent.change(campo, {
      target: { value: JSON.stringify({ tarifa_hora_padrao: { valor: "110" } }) },
    });
    await userEvent.click(screen.getByRole("button", { name: "Simular" }));
    const painel = await screen.findByTestId("resultado");
    expect(texto(painel.textContent)).toContain("R$ 100.000,00");
    expect(texto(painel.textContent)).toContain("R$ 120.000,00");
    expect(texto(painel.textContent)).toContain("25%");
    expect(texto(painel.textContent)).toContain("110");
    const pedido = pedidos.find((p) => p.caminho.endsWith("/simulacoes"));
    expect(pedido?.corpo).toEqual({
      documento: { tarifa_hora_padrao: { valor: "110" } },
      referencia: "2027-01",
    });
  });

  it("JSON inválido não chama a API", async () => {
    const pedidos = simularApi({ "GET /api/v1/politicas": [200, [POLITICA]] });
    renderizar(<Laboratorio referencia="2027-01" />);
    const campo = await screen.findByLabelText("Documento da política");
    fireEvent.change(campo, { target: { value: "{quebrado" } });
    await userEvent.click(screen.getByRole("button", { name: "Simular" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("JSON");
    expect(pedidos.some((p) => p.caminho.endsWith("/simulacoes"))).toBe(false);
  });

  it("guarda o rascunho", async () => {
    const pedidos = simularApi({
      "GET /api/v1/politicas": [200, [POLITICA]],
      "POST /api/v1/politicas": [201, { versao: 2 }],
    });
    renderizar(<Laboratorio referencia="2027-01" />);
    await screen.findByLabelText("Documento da política");
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Documento da política") as HTMLTextAreaElement).value,
      ).toContain("103.5"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Guardar rascunho" }));
    expect(await screen.findByText("Rascunho v2 guardado")).toBeInTheDocument();
    expect(pedidos.at(-1)?.caminho).toBe("/api/v1/politicas");
  });
});
