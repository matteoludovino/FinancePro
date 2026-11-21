# 3. Recognizing a transaction already imported

## Context

People export overlapping periods ("last 90 days" every month), re-send the same file, and delete lines they don't want. Statements may or may not carry a per-transaction id, and the same purchase can show a different description in a later export.

## Decision

Each transaction is recognized by two keys, both unique per account:

- **`external_id`**, the bank's own id, when the file has one.
- **`fingerprint`**, always: SHA-256 of `date | amount | canonical description | n`, where `n` numbers identical lines within the file (0 for the first, 1 for the second...). Two R$ 5 coffees at the same bakery on the same day are two transactions; an overlapping export matches them one to one instead of collapsing them.

The canonical description is lowercase, accent-free, whitespace-collapsed, **digits kept**. It deliberately does not use the normalized merchant: the normalizer improves over time (and strips "Parcela 3/10"), and fingerprints must not move when it does. They carry `fp_version`; a new formula is a backfill, never a silent change. A test pins the value of one fingerprint.

Around the exact keys:

- A line with the same amount within 3 days of an existing one, but no exact match, is a **possible duplicate**. It is not imported unless the person ticks it.
- Deleted transactions stay as tombstones (`deleted_at`), keeping their fingerprint, so re-importing the file doesn't bring them back.
- Importing is two-phase: a preview (nothing written), then a confirmation that flips the batch status in a conditional `UPDATE` (two clicks can't both import), recomputes duplicates and inserts with `ON CONFLICT DO NOTHING`.
- Undoing an import deletes its rows for good, tombstones included: the file was never imported. If any of them were edited, the person is asked first.

## Consequences

Re-importing anything is safe and reports "0 new". A bank that rewrites descriptions between exports produces possible duplicates for a person to decide on, never silent doubles. The same text on two different days, or two different amounts, are always different transactions.
