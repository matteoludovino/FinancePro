# 5. Transfers between a person's own accounts

## Context

Money that moves between pockets is neither spending nor income: the bill paid from checking and received by the card, money put into a savings box, a Pix to one's own account at another bank. Counted as regular transactions, they inflate both sides of every report.

## Decision

- A transaction has a **kind**, separate from its category: `regular` (spending or income, by the sign and the category's type), `transfer`, or `ignored` (lines that aren't money moving, like a carried-over balance). A CHECK constraint keeps categories on regular transactions only.
- **Default rules** mark the lines that are transfers whatever the account (bill payment wordings, Nubank's savings box "Aplicação/Resgate RDB").
- **Pairs** are linked through `transfer_pair_id`. Candidates are opposite amounts in two different accounts within 3 days, both unlinked. Only unambiguous candidates count: if a debit could match two credits, nothing is guessed. A card's outflow (a purchase) is never one side.
- On import, pairs whose two sides the rules already call transfers are linked automatically (the bill payment). Pairs with a side still counted as spending or income are **suggested**; a person confirms or dismisses them, and a dismissed transaction is not suggested again.
- A transfer may have one side only (the other account isn't imported); the "outside the app" account kind exists for people who want to see where that money went.

## Consequences

Reports can exclude transfers by kind alone. Unlinking a pair, or undoing the import of one side, leaves the other side a one-sided transfer rather than turning it back into spending.
