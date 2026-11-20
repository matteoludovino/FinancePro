// Money travels from the API as integer cents. The browser formats it but never does arithmetic on
// floats: sums the UI needs come from the API, already in cents.

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** 123456 → "R$ 1.234,56"; negative values keep their sign. */
export function formatCents(cents: number): string {
  if (!Number.isSafeInteger(cents)) throw new RangeError(`not an integer amount of cents: ${cents}`);
  return brl.format(cents / 100);
}
