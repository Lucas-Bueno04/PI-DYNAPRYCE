import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { diferencas } from "./diferencas";
import { Politicas } from "./Politicas";

const V2 = {
  versao: 2,
  estado: "rascunho",
  documento: { gatilho_revisao: "0.10", reajuste: { teto_real_por_ciclo: "0.15" } },
  portao_aceite: true,
  relatorio: null,
};
const V1 = {
  versao: 1,
  estado: "publicada",
  documento: { gatilho_revisao: "0.15", reajuste: { teto_real_por_ciclo: "0.15" } },
  portao_aceite: null,
  relatorio: null,
};

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["aprovar"], mfa: true }));
});

describe("diferenças entre versões", () => {
  it("lista só o que mudou, com o caminho do campo", () => {
    expect(diferencas(V1.documento, V2.documento)).toEqual([
      { campo: "gatilho_revisao", antes: "0.15", depois: "0.10" },
    ]);
  });

  it("mostra campo incluído e removido", () => {
    expect(diferencas({ a: 1 }, { b: 2 })).toEqual([
      { campo: "a", antes: "1", depois: "—" },
      { campo: "b", antes: "—", depois: "2" },
    ]);
  });
});

describe("tela de políticas", () => {
  it("mostra o diff do rascunho contra a publicada", async () => {
    simularApi({ "GET /api/v1/politicas": [200, [V2, V1]] });
    renderizar(<Politicas />);
    expect(await screen.findByText("gatilho_revisao")).toBeInTheDocument();
    expect(screen.getByText("0.10")).toBeInTheDocument();
  });

  it("publica o rascunho", async () => {
    const pedidos = simularApi({
      "GET /api/v1/politicas": [200, [V2, V1]],
      "POST /api/v1/politicas/2/publicar": [204],
    });
    renderizar(<Politicas />);
    await userEvent.click(await screen.findByRole("button", { name: "Publicar v2" }));
    await waitFor(() => expect(pedidos.some((p) => p.caminho.endsWith("/publicar"))).toBe(true));
  });

  it("portão reprovado não oferece publicar", async () => {
    simularApi({
      "GET /api/v1/politicas": [200, [{ ...V2, portao_aceite: false }, V1]],
    });
    renderizar(<Politicas />);
    expect(await screen.findByText(/Portão de aceite reprovado/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publicar v2" })).not.toBeInTheDocument();
  });

  it("analista não vê o botão de publicar", async () => {
    definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
    simularApi({ "GET /api/v1/politicas": [200, [V2, V1]] });
    renderizar(<Politicas />);
    await screen.findByText("gatilho_revisao");
    expect(screen.queryByRole("button", { name: "Publicar v2" })).not.toBeInTheDocument();
  });
});
