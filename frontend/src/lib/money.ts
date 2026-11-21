// Money travels from the API as integer cents. The browser formats it but never does arithmetic on
// floats: sums the UI needs come from the API, already in cents.

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** 123456 → "R$ 1.234,56"; negative values keep their sign. */
export function formatCents(cents: number): string {
  if (!Number.isSafeInteger(cents)) throw new RangeError(`not an integer amount of cents: ${cents}`);
  return brl.format(cents / 100);
}

/**
 * What a person types ("1.234,56", "R$ 30", "30,5") → integer cents, or null when it isn't an amount.
 * Done on the string, never through a float: "0,29" is 29 cents, not 28.999….
 */
export function parseCents(input: string): number | null {
  const text = input.replace(/R\$|\s/g, "");
  if (!/^\d{1,3}(\.\d{3})*(,\d{1,2})?$|^\d+(,\d{1,2})?$/.test(text)) return null;
  const [units, fraction = ""] = text.replace(/\./g, "").split(",");
  const cents = Number(units) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(cents) ? cents : null;
}

/** 123456 → "1.234,56", for prefilling an input. */
export function centsToInput(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const compact = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

/** 685000 → "R$ 6,9 mil", for axis ticks and tight spots; full values stay in tooltips and tables. */
export function formatCompact(cents: number): string {
  return compact.format(cents / 100);
}

const rounded = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

/** 70648 → "R$ 706": whole reais, for a label next to a mark (the exact value is one hover away). */
export function formatRounded(cents: number): string {
  return Math.abs(cents) >= 1_000_000 ? formatCompact(cents) : rounded.format(cents / 100);
}
