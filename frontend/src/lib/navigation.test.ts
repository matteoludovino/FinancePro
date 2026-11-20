import { describe, expect, it } from "vitest";
import { safeNext } from "./navigation";

describe("safeNext", () => {
  it("keeps paths inside the app", () => {
    expect(safeNext("/contas")).toBe("/contas");
    expect(safeNext("/lancamentos?mes=2026-11")).toBe("/lancamentos?mes=2026-11");
  });

  it("refuses anything that leaves the site", () => {
    for (const next of ["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"]) {
      expect(safeNext(next)).toBe("/painel");
    }
  });

  it("defaults to the dashboard", () => {
    expect(safeNext(null)).toBe("/painel");
    expect(safeNext("")).toBe("/painel");
  });
});
