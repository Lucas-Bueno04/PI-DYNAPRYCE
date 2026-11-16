import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Recomendacoes } from "./Recomendacoes";

const ITEM = {
  id: "r1",
  contrato_id: "C1",
  competencia: "2027-01",
  efeito: "2027-03",
  estado: "pendente",
  versao: 1,
  preco_vigente: "437.00",
  preco_proposto: "502.55",
  trajetoria: ["502.55", "577.93", "614.27"],
  decomposicao: {
    preco_alvo: "614.27",
    nivel_informacao: 2,
    horas_padrao: "5.9350",
    horas_por_departamento: { fiscal: "2.785", contabil: "2.483", folha: "0.667" },
    regime: "LP",
    tarifa: "103.5",
    piso: "235.00",
    kappa: "1",
  },
};

const APROVADOR = tokenFalso({ roles: ["aprovar"], mfa: true });

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(APROVADOR);
});

const texto = (t: string) => t.replace(/ /g, " ");

async function abrirDetalhe() {
  renderizar(<Recomendacoes />);
  await userEvent.click(await screen.findByRole("button", { name: "Ver C1" }));
  return screen.findByRole("dialog");
}

describe("fila de recomendações", () => {
  it("lista os valores em pt-BR", async () => {
    simularApi({ "GET /api/v1/recomendacoes": [200, [ITEM]] });
    renderizar(<Recomendacoes />);
    const linha = (await screen.findByText("C1")).closest("tr") as HTMLElement;
    expect(texto(linha.textContent ?? "")).toContain("R$ 437,00");
    expect(texto(linha.textContent ?? "")).toContain("R$ 502,55");
  });

  it("pede só as pendentes por padrão", async () => {
    const pedidos = simularApi({ "GET /api/v1/recomendacoes": [200, []] });
    renderizar(<Recomendacoes />);
    await waitFor(() => expect(pedidos).toHaveLength(1));
    expect(pedidos[0]?.caminho).toBe("/api/v1/recomendacoes");
  });

  it("mostra a decomposição: piso, horas por departamento, τ, κ e nível", async () => {
    simularApi({ "GET /api/v1/recomendacoes": [200, [ITEM]] });
    const dialogo = await abrirDetalhe();
    const conteudo = texto(dialogo.textContent ?? "");
    expect(conteudo).toContain("R$ 235,00");
    expect(conteudo).toContain("fiscal");
    expect(conteudo).toContain("2,785");
    expect(conteudo).toContain("103,5");
    expect(conteudo).toMatch(/κ.*1/);
    expect(conteudo).toContain("Nível 2");
    expect(conteudo).toContain("R$ 614,27");
    expect(conteudo).toContain("R$ 577,93");
  });

  it("aprova enviando a versão lida", async () => {
    const pedidos = simularApi({
      "GET /api/v1/recomendacoes": [200, [ITEM]],
      "POST /api/v1/recomendacoes/r1/decisao": [204],
    });
    const dialogo = await abrirDetalhe();
    await userEvent.click(within(dialogo).getByRole("button", { name: "Aprovar" }));
    await waitFor(() =>
      expect(pedidos.some((p) => p.caminho.endsWith("/decisao"))).toBe(true),
    );
    expect(pedidos.find((p) => p.caminho.endsWith("/decisao"))?.corpo).toEqual({
      versao: 1,
      acao: "aprovar",
    });
  });

  it("aprovar pede TOTP quando a sessão não tem", async () => {
    definirAcesso(tokenFalso({ roles: ["aprovar"], mfa: false }));
    const pedidos = simularApi({ "GET /api/v1/recomendacoes": [200, [ITEM]] });
    const dialogo = await abrirDetalhe();
    await userEvent.click(within(dialogo).getByRole("button", { name: "Aprovar" }));
    expect(await within(dialogo).findByRole("alert")).toHaveTextContent("TOTP");
    expect(pedidos.some((p) => p.caminho.endsWith("/decisao"))).toBe(false);
  });

  it("rejeitar exige motivo", async () => {
    const pedidos = simularApi({ "GET /api/v1/recomendacoes": [200, [ITEM]] });
    const dialogo = await abrirDetalhe();
    await userEvent.click(within(dialogo).getByRole("button", { name: "Rejeitar" }));
    expect(await within(dialogo).findByRole("alert")).toHaveTextContent("motivo");
    expect(pedidos.some((p) => p.caminho.endsWith("/decisao"))).toBe(false);
  });

  it("ajusta κ com justificativa", async () => {
    const pedidos = simularApi({
      "GET /api/v1/recomendacoes": [200, [ITEM]],
      "POST /api/v1/recomendacoes/r1/decisao": [204],
    });
    const dialogo = await abrirDetalhe();
    await userEvent.type(within(dialogo).getByLabelText("Novo κ"), "1.10");
    await userEvent.type(within(dialogo).getByLabelText("Justificativa"), "contrato complexo");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Ajustar κ" }));
    await waitFor(() =>
      expect(pedidos.find((p) => p.caminho.endsWith("/decisao"))?.corpo).toEqual({
        versao: 1,
        acao: "ajustar",
        kappa: "1.10",
        justificativa: "contrato complexo",
      }),
    );
  });

  it("conflito avisa que outra pessoa decidiu", async () => {
    simularApi({
      "GET /api/v1/recomendacoes": [200, [ITEM]],
      "POST /api/v1/recomendacoes/r1/decisao": [409, { status: 409 }],
    });
    const dialogo = await abrirDetalhe();
    await userEvent.click(within(dialogo).getByRole("button", { name: "Aprovar" }));
    expect(await within(dialogo).findByRole("alert")).toHaveTextContent("mudou");
  });

  it("não mostra regra de preço própria: os valores vêm da API", async () => {
    simularApi({
      "GET /api/v1/recomendacoes": [
        200,
        [{ ...ITEM, decomposicao: { ...ITEM.decomposicao, preco_alvo: "999.99" } }],
      ],
    });
    const dialogo = await abrirDetalhe();
    expect(texto(dialogo.textContent ?? "")).toContain("R$ 999,99");
  });
});
