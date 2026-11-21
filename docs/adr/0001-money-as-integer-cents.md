# 1. Money as integer cents

## Context

Amounts arrive as text in at least three shapes (`-1.234,56`, `1234.56`, `(12,34)`) and are summed into reports and budgets. Floats can't represent most cents exactly (`0.1 + 0.2`), and a report that is off by a cent is a report nobody trusts.

## Decision

- Amounts are stored as `BIGINT` cents with a sign: negative leaves the account.
- Text goes straight to `Decimal` and then to cents; it never passes through a float. The decimal separator is decided for the whole column, because `1.234` alone is ambiguous and next to `10,50` it isn't.
- The API sends integer cents. The browser formats them (`Intl.NumberFormat`) and parses what people type on the string (`"0,29"` is 29 cents), but every sum it shows comes from the API.

## Consequences

Sums are exact and comparisons are integer comparisons. Any currency other than BRL would need a currency column; the app is for Brazilian statements, so there is none.
