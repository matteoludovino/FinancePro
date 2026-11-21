import { describe, expect, it } from "vitest";
import { centsToInput, formatCents, formatCompact, formatRounded, parseCents } from "./money";

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

describe("parseCents", () => {
  it("reads the ways people type amounts in Brazil", () => {
    expect(parseCents("1.234,56")).toBe(123456);
    expect(parseCents("R$ 30")).toBe(3000);
    expect(parseCents("30,5")).toBe(3050);
    expect(parseCents("0,29")).toBe(29);
    expect(parseCents("1234,5")).toBe(123450);
  });

  it("refuses what isn't an amount", () => {
    for (const input of ["", "abc", "1,234", "12.34", "1.23,45", "-5", "1,999"]) {
      expect(parseCents(input)).toBeNull();
    }
  });

  it("round-trips with centsToInput", () => {
    for (const cents of [0, 5, 2990, 123456, 100000000]) expect(parseCents(centsToInput(cents))).toBe(cents);
  });
});

describe("formatCompact", () => {
  it("shortens thousands for axes", () => {
    expect(formatCompact(685000)).toBe(nbsp("R$ 6,9 mil"));
    expect(formatCompact(9990)).toBe(nbsp("R$ 99,9"));
  });
});

describe("formatRounded", () => {
  it("drops cents for labels, and goes compact from ten thousand", () => {
    expect(formatRounded(70648)).toBe(nbsp("R$ 706"));
    expect(formatRounded(1250000)).toBe(nbsp("R$ 12,5 mil"));
  });
});
