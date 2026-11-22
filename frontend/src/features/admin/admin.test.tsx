import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Administracao } from "./Administracao";

const USUARIO = {
  id: "u2",
  email: "ana@escritorio.com",
  ativo: true,
  mfa_ativo: false,
  papeis: ["analisar"],
};
const CONECTOR = {
  tipo: "omie",
  parametros: {},
  dias_fechamento: 5,
  credencial_configurada: true,
};
const BASE = {
  "GET /api/v1/usuarios": [200, [USUARIO]],
  "GET /api/v1/conectores": [200, [CONECTOR]],
  "GET /api/v1/vinculos/pendencias": [200, ["P123"]],
  "GET /api/v1/alertas": [200, [{ tipo: "job_falhou", referencia: "j1", criado_em: "2027-01-01" }]],
} as const;

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["administrar"], mfa: true }));
});

function tela() {
  renderizar(<Administracao competencia="2027-01" />);
}

describe("administração", () => {
  it("lista usuários com papéis e situação do MFA", async () => {
    simularApi({ ...BASE });
    tela();
    const linha = (await screen.findByText("ana@escritorio.com")).closest("tr") as HTMLElement;
    expect(linha).toHaveTextContent("analisar");
    expect(linha).toHaveTextContent("MFA pendente");
  });

  it("cria usuário no inquilino", async () => {
    const pedidos = simularApi({ ...BASE, "POST /api/v1/usuarios": [201, { id: "u3" }] });
    tela();
    await screen.findByText("ana@escritorio.com");
    await userEvent.type(screen.getByLabelText("E-mail do novo usuário"), "bia@e.com");
    await userEvent.type(screen.getByLabelText("Senha inicial"), "senha-bem-longa-1");
    await userEvent.click(screen.getByRole("button", { name: "Criar usuário" }));
    await waitFor(() =>
      expect(pedidos.find((p) => p.metodo === "POST")?.corpo).toEqual({
        email: "bia@e.com",
        senha: "senha-bem-longa-1",
        papeis: ["analisar"],
      }),
    );
  });

  it("mostra conector configurado sem exibir segredo e testa a conexão", async () => {
    const pedidos = simularApi({
      ...BASE,
      "POST /api/v1/conectores/omie/teste": [200, { situacao: "ok", detalhe: "" }],
    });
    tela();
    const linha = (await screen.findByText("omie")).closest("tr") as HTMLElement;
    expect(linha).toHaveTextContent("Credencial configurada");
    await userEvent.click(within(linha).getByRole("button", { name: "Testar conexão" }));
    expect(await within(linha).findByText("Conexão ok")).toBeInTheDocument();
    expect(pedidos.some((p) => p.caminho.endsWith("/teste"))).toBe(true);
  });

  it("mostra credencial recusada no teste", async () => {
    simularApi({
      ...BASE,
      "POST /api/v1/conectores/omie/teste": [200, { situacao: "credencial_invalida", detalhe: "" }],
    });
    tela();
    const linha = (await screen.findByText("omie")).closest("tr") as HTMLElement;
    await userEvent.click(within(linha).getByRole("button", { name: "Testar conexão" }));
    expect(await within(linha).findByText("Credencial recusada")).toBeInTheDocument();
  });

  it("fila de pendências de vínculo fica visível", async () => {
    simularApi({ ...BASE });
    tela();
    expect(await screen.findByText("P123")).toBeInTheDocument();
  });

  it("alerta de job falho fica visível", async () => {
    simularApi({ ...BASE });
    tela();
    expect(await screen.findByText(/job_falhou/)).toBeInTheDocument();
  });

  it("gera link de redefinição", async () => {
    simularApi({ ...BASE, "POST /api/v1/usuarios/u2/redefinicao": [200, { token: "tk1" }] });
    tela();
    const linha = (await screen.findByText("ana@escritorio.com")).closest("tr") as HTMLElement;
    await userEvent.click(within(linha).getByRole("button", { name: "Gerar link" }));
    expect(await screen.findByText(/tk1/)).toBeInTheDocument();
  });
});
