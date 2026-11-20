import { describe, expect, it } from "vitest";
import { formatCents } from "./money";

// Intl separates "R$" from the number with a no-break space.
const nbsp = (s: string) => s.replace(/ /g, " ");

describe("formatCents", () => {
  it("formats cents as Brazilian reais", () => {
    expect(formatCents(123456)).toBe(nbsp("R$ 1.234,56"));
    expect(formatCents(5)).toBe(nbsp("R$ 0,05"));
    expect(formatCents(0)).toBe(nbsp("R$ 0,00"));
  });

  it("keeps the sign of outflows", () => {
    expect(formatCents(-4990)).toBe(nbsp("-R$ 49,90"));
  });

  it("rejects anything that is not whole cents", () => {
    expect(() => formatCents(12.5)).toThrow(RangeError);
  });
});
