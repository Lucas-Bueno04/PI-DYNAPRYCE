import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Usuarios } from "./Usuarios";

const USUARIO = { id: "u1", email: "ana@escritorio.com", papeis: ["analisar"], mfa_ativo: false, ativo: true };

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
  definirAcesso(tokenFalso({ roles: ["administrar"], mfa: true }));
});

describe("usuários", () => {
  it("lista os usuários com papéis e situação do MFA", async () => {
    simularApi({ "GET /api/v1/usuarios": [200, [USUARIO]] });
    renderizar(<Usuarios />);
    expect(await screen.findByText("ana@escritorio.com")).toBeInTheDocument();
    expect(screen.getByText("Pendente")).toBeInTheDocument();
  });

  it("cria um usuário com os papéis escolhidos", async () => {
    const pedidos = simularApi({ "GET /api/v1/usuarios": [200, [USUARIO]], "POST /api/v1/usuarios": [201, { ...USUARIO, id: "u2" }] });
    renderizar(<Usuarios />);
    await screen.findByText("ana@escritorio.com");
    await userEvent.type(screen.getByLabelText("E-mail"), "novo@escritorio.com");
    await userEvent.type(screen.getByLabelText(/Senha inicial/), "senha-bem-longa-123");
    await userEvent.click(screen.getByRole("button", { name: "Criar usuário" }));
    const envio = pedidos.find((p) => p.metodo === "POST" && p.caminho === "/api/v1/usuarios");
    expect(envio?.corpo).toMatchObject({ email: "novo@escritorio.com", papeis: ["analisar"] });
  });

  it("gera o link de redefinição de uso único", async () => {
    simularApi({ "GET /api/v1/usuarios": [200, [USUARIO]], "POST /api/v1/usuarios/u1/redefinicao": [200, { token: "abc123" }] });
    renderizar(<Usuarios />);
    await userEvent.click(await screen.findByRole("button", { name: "Gerar link" }));
    expect(await screen.findByText(/redefinir\?token=abc123/)).toBeInTheDocument();
  });
});
