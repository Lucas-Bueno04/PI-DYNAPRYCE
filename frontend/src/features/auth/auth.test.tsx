import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../shared/api/cliente";
import { limparSessao, obterAcesso, definirAcesso } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Entrar } from "./Entrar";
import { Guarda } from "./Guarda";

const ACESSO = tokenFalso({ roles: ["analisar"], mfa: false });
const NOVO = tokenFalso({ roles: ["analisar"], mfa: true });
const TOKENS = { acesso: ACESSO, tenant_id: "t1", inquilinos: ["t1"] };

beforeEach(() => {
  limparSessao();
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

function telaDeEntrar(rota = "/entrar") {
  renderizar(
    <Routes>
      <Route path="/entrar" element={<Entrar />} />
      <Route path="/" element={<p>início</p>} />
    </Routes>,
    rota,
  );
}

async function preencherLogin() {
  await userEvent.type(screen.getByLabelText("E-mail"), "a@b.com");
  await userEvent.type(screen.getByLabelText("Senha"), "senha-bem-longa");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("sessão", () => {
  it("guarda o token só em memória", async () => {
    simularApi({ "POST /api/v1/auth/entrar": [200, { tokens: TOKENS }] });
    telaDeEntrar();
    await preencherLogin();
    await screen.findByText("início");
    expect(obterAcesso()).toBe(ACESSO);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("envia o Bearer", async () => {
    definirAcesso(ACESSO);
    const pedidos = simularApi({ "GET /api/v1/alertas": [200, []] });
    await api.GET("/api/v1/alertas");
    expect(pedidos[0]?.cabecalhos.get("authorization")).toBe(`Bearer ${ACESSO}`);
  });

  it("um 401 dispara uma renovação e reenvia a fila", async () => {
    definirAcesso(ACESSO);
    let renovada = false;
    const pedidos = simularApi({
      "POST /api/v1/auth/renovar": () => {
        renovada = true;
        return [200, { ...TOKENS, acesso: NOVO }];
      },
      "GET /api/v1/alertas": (p) =>
        p.cabecalhos.get("authorization") === `Bearer ${NOVO}` ? [200, []] : [401],
      "GET /api/v1/politicas": (p) =>
        p.cabecalhos.get("authorization") === `Bearer ${NOVO}` ? [200, []] : [401],
    });
    const [a, b] = await Promise.all([api.GET("/api/v1/alertas"), api.GET("/api/v1/politicas")]);
    expect(renovada).toBe(true);
    expect(a.response.status).toBe(200);
    expect(b.response.status).toBe(200);
    expect(pedidos.filter((p) => p.caminho.endsWith("/renovar"))).toHaveLength(1);
    expect(obterAcesso()).toBe(NOVO);
  });

  it("renovação recusada encerra a sessão", async () => {
    definirAcesso(ACESSO);
    simularApi({ "POST /api/v1/auth/renovar": [401], "GET /api/v1/alertas": [401] });
    const { response } = await api.GET("/api/v1/alertas");
    expect(response.status).toBe(401);
    expect(obterAcesso()).toBeNull();
  });

  it("409 na renovação (outra aba) tenta de novo sem derrubar a sessão", async () => {
    definirAcesso(ACESSO);
    let tentativas = 0;
    simularApi({
      "POST /api/v1/auth/renovar": () => {
        tentativas += 1;
        return tentativas === 1 ? [409] : [200, { ...TOKENS, acesso: NOVO }];
      },
      "GET /api/v1/alertas": (p) =>
        p.cabecalhos.get("authorization") === `Bearer ${NOVO}` ? [200, []] : [401],
    });
    const { response } = await api.GET("/api/v1/alertas");
    expect(response.status).toBe(200);
    expect(tentativas).toBe(2);
  });
});

describe("login", () => {
  it("pede o TOTP quando a API devolve desafio", async () => {
    const pedidos = simularApi({
      "POST /api/v1/auth/entrar": [200, { desafio: "d1" }],
      "POST /api/v1/auth/mfa": [200, TOKENS],
    });
    telaDeEntrar();
    await preencherLogin();
    await userEvent.type(await screen.findByLabelText("Código TOTP"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    await screen.findByText("início");
    expect(pedidos.at(-1)?.corpo).toEqual({ desafio: "d1", codigo: "123456" });
  });

  it("cadastra o MFA e mostra os códigos de recuperação uma vez", async () => {
    simularApi({
      "POST /api/v1/auth/entrar": [200, { desafio: "d1", cadastro_mfa_requerido: true }],
      "POST /api/v1/auth/mfa/cadastrar": [200, { segredo: "ABC123", uri: "otpauth://x" }],
      "POST /api/v1/auth/mfa/confirmar": [200, { tokens: TOKENS, codigos_de_recuperacao: ["c1"] }],
    });
    telaDeEntrar();
    await preencherLogin();
    expect(await screen.findByText("ABC123")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Código TOTP"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(await screen.findByText("c1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Já guardei" }));
    await screen.findByText("início");
  });

  it("mostra erro genérico com credencial errada", async () => {
    simularApi({ "POST /api/v1/auth/entrar": [401, { status: 401 }] });
    telaDeEntrar();
    await preencherLogin();
    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha inválidos");
  });

  it("avisa quando há muitas tentativas", async () => {
    simularApi({ "POST /api/v1/auth/entrar": [429, { status: 429 }] });
    telaDeEntrar();
    await preencherLogin();
    expect(await screen.findByRole("alert")).toHaveTextContent("Muitas tentativas");
  });
});

describe("login federado", () => {
  it("mostra o botão do provedor só quando a API informa que existe", async () => {
    simularApi({ "GET /api/v1/auth/oidc/disponivel": [200, { disponivel: true }] });
    telaDeEntrar();
    const link = await screen.findByRole("link", { name: "Entrar com o provedor da empresa" });
    expect(link).toHaveAttribute("href", "/api/v1/auth/oidc/entrar");
  });

  it("sem provedor não há botão", async () => {
    const pedidos = simularApi({ "GET /api/v1/auth/oidc/disponivel": [200, { disponivel: false }] });
    telaDeEntrar();
    await waitFor(() => expect(pedidos.length).toBeGreaterThan(0));
    expect(screen.queryByRole("link", { name: /provedor/ })).toBeNull();
  });

  it("retorno com desafio no fragmento pede o TOTP", async () => {
    const pedidos = simularApi({ "POST /api/v1/auth/mfa": [200, TOKENS] });
    telaDeEntrar("/entrar#desafio=d9");
    await userEvent.type(await screen.findByLabelText("Código TOTP"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    await screen.findByText("início");
    expect(pedidos.at(-1)?.corpo).toEqual({ desafio: "d9", codigo: "123456" });
  });

  it("retorno que exige cadastro de MFA abre o cadastro", async () => {
    const pedidos = simularApi({
      "POST /api/v1/auth/mfa/cadastrar": [200, { segredo: "XYZ789", uri: "otpauth://x" }],
    });
    telaDeEntrar("/entrar#desafio=d9&cadastro_mfa=1");
    expect(await screen.findByText("XYZ789")).toBeInTheDocument();
    expect(pedidos.find((p) => p.caminho.endsWith("/mfa/cadastrar"))?.corpo).toEqual({ desafio: "d9" });
  });

  it("falha no provedor mostra erro genérico", async () => {
    simularApi({});
    telaDeEntrar("/entrar?erro=federacao");
    expect(await screen.findByRole("alert")).toHaveTextContent("provedor");
  });
});

describe("guarda", () => {
  function telaProtegida(papel: "aprovar" | "analisar") {
    renderizar(
      <Routes>
        <Route
          path="/"
          element={
            <Guarda papel={papel}>
              <p>conteúdo</p>
            </Guarda>
          }
        />
        <Route path="/entrar" element={<p>tela de login</p>} />
      </Routes>,
    );
  }

  it("sem sessão vai para o login", async () => {
    simularApi({ "POST /api/v1/auth/renovar": [401] });
    telaProtegida("analisar");
    await screen.findByText("tela de login");
  });

  it("restaura a sessão pelo cookie ao abrir", async () => {
    simularApi({ "POST /api/v1/auth/renovar": [200, TOKENS] });
    telaProtegida("analisar");
    await screen.findByText("conteúdo");
  });

  it("esconde a tela de quem não tem o papel", async () => {
    definirAcesso(ACESSO);
    telaProtegida("aprovar");
    await waitFor(() => expect(screen.queryByText("conteúdo")).not.toBeInTheDocument());
    expect(await screen.findByText("Você não tem acesso a esta tela.")).toBeInTheDocument();
  });
});

describe("redefinição de senha", () => {
  it("usa o token do link e volta para o login", async () => {
    const { Redefinir } = await import("./Redefinir");
    const pedidos = simularApi({ "POST /api/v1/auth/redefinir": [204] });
    renderizar(
      <Routes>
        <Route path="/redefinir" element={<Redefinir />} />
        <Route path="/entrar" element={<p>tela de login</p>} />
      </Routes>,
      "/redefinir?token=tk1",
    );
    await userEvent.type(screen.getByLabelText("Nova senha"), "senha-bem-longa-2");
    await userEvent.click(screen.getByRole("button", { name: "Redefinir" }));
    await screen.findByText("tela de login");
    expect(pedidos[0]?.corpo).toEqual({ token: "tk1", nova_senha: "senha-bem-longa-2" });
  });
});
