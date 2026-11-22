import { describe, expect, it } from "vitest";
import { competenciaAnterior, listarCompetencias, rotuloDaCompetencia } from "./competencia";

describe("competência", () => {
  it("a competência fechada é o mês anterior, inclusive na virada do ano", () => {
    expect(competenciaAnterior(new Date(2026, 10, 16))).toBe("2026-10");
    expect(competenciaAnterior(new Date(2026, 0, 5))).toBe("2025-12");
  });

  it("lista os meses do mais recente para o mais antigo", () => {
    expect(listarCompetencias("2026-02", 4)).toEqual(["2026-02", "2026-01", "2025-12", "2025-11"]);
  });

  it("rotula em português", () => {
    expect(rotuloDaCompetencia("2025-12")).toMatch(/dez/i);
  });
});
