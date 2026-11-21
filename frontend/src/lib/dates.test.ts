import { describe, expect, it } from "vitest";
import { addMonths, currentMonth, formatDate, monthLabel, shortDate } from "./dates";

describe("dates", () => {
  it("formats calendar days without a time zone shift", () => {
    expect(formatDate("2026-11-01")).toBe("01/11/2026");
    expect(shortDate("2026-11-01")).toBe("1 nov");
  });

  it("names months in Portuguese", () => {
    expect(monthLabel("2026-03")).toBe("março de 2026");
  });

  it("moves across years", () => {
    expect(addMonths("2026-01", -1)).toBe("2025-12");
    expect(addMonths("2026-12", 1)).toBe("2027-01");
    expect(addMonths("2026-05", -17)).toBe("2024-12");
  });

  it("reads the current month from the local calendar", () => {
    expect(currentMonth(new Date(2026, 0, 31, 23, 30))).toBe("2026-01");
  });
});
