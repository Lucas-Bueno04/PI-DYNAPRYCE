import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProvedorDeCompetencia } from "../../app/competencia";
import { definirAcesso, limparSessao } from "../../shared/api/sessao";
import { renderizar, simularApi, tokenFalso } from "../../test/apoio";
import { Acompanhamento } from "./Acompanhamento";

const DIVERGENCIA = { id: "d1", contrato_id: "C0001", competencia: "2025-12", aprovado: "500.00", cobrado: "450.00", situacao: "aberta", justificativa: "" };

beforeEach(() => {
  limparSessao();
  vi.unstubAllGlobals();
});

describe("acompanhamento", () => {
  it("aprovador vê e trata as divergências", async () => {
    definirAcesso(tokenFalso({ roles: ["aprovar"], mfa: true }));
    simularApi({ "GET /api/v1/divergencias": [200, [DIVERGENCIA]], "POST /api/v1/divergencias/d1/resolucao": [204] });
    renderizar(<ProvedorDeCompetencia><Acompanhamento /></ProvedorDeCompetencia>);
    expect(await screen.findByText("C0001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Justificar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolver" })).toBeInTheDocument();
  });

  it("analista só consulta: não vê as ações", async () => {
    definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
    simularApi({ "GET /api/v1/divergencias": [200, [DIVERGENCIA]] });
    renderizar(<ProvedorDeCompetencia><Acompanhamento /></ProvedorDeCompetencia>);
    await screen.findByText("C0001");
    expect(screen.queryByRole("button", { name: "Resolver" })).not.toBeInTheDocument();
  });

  it("mostra os alertas abertos em linguagem do usuário", async () => {
    definirAcesso(tokenFalso({ roles: ["analisar"], mfa: false }));
    simularApi({
      "GET /api/v1/divergencias": [200, []],
      "GET /api/v1/alertas": [200, [{ tipo: "indice_ausente", referencia: "2025-12", criado_em: "2026-11-16T12:00:00Z" }]],
    });
    renderizar(<ProvedorDeCompetencia><Acompanhamento /></ProvedorDeCompetencia>);
    await userEvent.click(await screen.findByRole("tab", { name: "Alertas" }));
    expect(await screen.findByText("Índice de inflação ausente na janela")).toBeInTheDocument();
  });
});
