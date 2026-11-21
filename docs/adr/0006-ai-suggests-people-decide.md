# 6. The AI suggests, people decide

## Context

Rules and built-in merchant knowledge categorize most of a statement, but every person has a long tail of merchants nobody wrote a rule for. A language model is good at "Livraria Cultura is books"; it is also a cost, a privacy question, and occasionally wrong.

## Decision

- **Last layer, not first.** Categorization runs the person's rules, then built-in merchant knowledge, then the AI only for what's left.
- **Suggestions are not categories.** A suggestion is stored next to the transaction (`ai_category_id`). Reports and budgets ignore it until a person accepts it, alone or as a rule ("always Livraria Cultura → Books"), or rejects it, and a rejected one isn't made again.
- **A fixed answer space.** Requests use structured outputs with a JSON schema whose category is an enum of the fixed taxonomy slugs plus `unknown`. The model can't invent a category, the schema is identical for everyone (so it is cached by the API), and slugs map to each person's own categories however they renamed them. Self-reported confidence is `low | medium | high`, shown to people and never used to apply anything on its own. Anything outside the asked ids or the enum is dropped.
- **Cheap calls.** Claude Haiku 5.5 at effort `low`. One request classifies up to 50 distinct merchants, each referred to by a short number. The instructions and taxonomy are a fixed, cached system prompt. The browser drives one batch per request while some remain, so no request runs long.
- **Shared cache.** Answers are cached by `(canonical merchant, taxonomy version, prompt version, model)` for everyone: the second person with a "Padaria Real" costs nothing, and the answers are applied during the import itself, with no model call. A changed prompt or taxonomy bumps its version and stops reusing old answers.
- **Privacy (LGPD).** What leaves is the normalized merchant name and whether money came in or went out. Never the amount, the date, the account or who the person is. Lines about a person (Pix and transfers to someone) are never sent at all, and documents (CPF, CNPJ) and long numbers are masked in what is.
- **Cost ceilings, enforced atomically.** A daily token ledger per person and a global one. Before each call an estimate is reserved in a single `INSERT ... ON CONFLICT DO UPDATE ... WHERE used + n <= cap`, so concurrent requests can't both pass a check only one fits in. The real usage replaces the estimate afterwards. A spend limit in the Anthropic Console is the backstop.
- **Optional.** Without an API key the AI is off and the app says so; everything else works. Tests use a fake classifier; no test touches the network.

## Consequences

A wrong answer costs a person one click, never a wrong report. The public demo can show suggestions with no live calls (its sample merchants are in the cache). A refusal or a truncated answer suggests nothing and still counts against the ceiling.
