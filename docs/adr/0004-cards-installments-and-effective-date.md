# 4. Credit cards, installments and the month a transaction counts in

## Context

A card is where most spending happens, and it breaks naive personal-finance math in three ways:

- The bill is paid from the checking account. Counting the card purchases **and** the bill payment counts the same spending twice.
- A purchase in 10 installments shows up as one line per statement ("Magalu - Parcela 3/10"). Some exports date each installment on the statement that bills it; others repeat the original purchase date on every installment.
- Statements follow a closing day, not the calendar month.

## Decision

- **The card is an account like any other, holding a liability.** Purchases are negative, refunds positive. Paying the bill is a transfer into it (ADR 0005), never spending.
- **`effective_date`** is the date a transaction counts in for reports and budgets; `date` stays what the bank printed (and what deduplication uses). For a purchase they are equal. For installment k of a file whose installments carry the purchase date, `effective_date = date + (k - 1) months`. Which convention a file uses is detected per import: installments dated inside the period the file's other lines cover fit "billing"; dated outside it but landing inside once moved fit "purchase". The mapping editor can force either.
- **Installment groups hold only the purchase's identity**: account, merchant without its counter, number of installments, month of installment 1 (± one month, billing days move). The amount is not part of the key, since rounding makes installment 1 differ by a cent. Progress and the installments still to come are derived from the members at query time: no projected rows, no counters that an undo or a deletion could leave wrong. A first import that starts at 3/10 does not invent 1/10 and 2/10.
- **Statements are computed** from the card's closing and due days: the statement due in month M holds what was charged from the closing day of M-1 up to (not including) the closing day of M. Nothing is stored; if the bank moves the closing date, editing the card's closing day recomputes everything.

## Consequences

Monthly spending is purchase-based and never doubled. Committed future spending ("how much of the next months is already spoken for") is the sum of the projected installments. A closing date that moves for a weekend can put a purchase made on that day in the neighbouring statement; reports, which use `effective_date`, are unaffected.
