// Dates travel as "YYYY-MM-DD" strings: calendar days, no time zone. They are formatted by splitting the
// string, never through `new Date(...)`, which would read them as UTC midnight and show the day before in
// Brazil.

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MONTHS_FULL = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** "2026-11-03" → "03/11/2026" */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

/** "2026-11-03" → "3 nov" */
export function shortDate(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${Number(day)} ${MONTHS[Number(month) - 1]}`;
}

/** "2026-11" → "novembro de 2026" */
export function monthLabel(month: string): string {
  const [year, number] = month.split("-");
  return `${MONTHS_FULL[Number(number) - 1]} de ${year}`;
}

/** The current month in the visitor's own calendar, "YYYY-MM". */
export function currentMonth(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/** "2026-01" moved by `delta` months. */
export function addMonths(month: string, delta: number): string {
  const [year, number] = month.split("-").map(Number);
  const index = year * 12 + (number - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/** "2026-11-01" or "2026-11" → "nov/26" */
export function shortMonth(iso: string): string {
  const [year, month] = iso.split("-");
  return `${MONTHS[Number(month) - 1]}/${year.slice(2)}`;
}
