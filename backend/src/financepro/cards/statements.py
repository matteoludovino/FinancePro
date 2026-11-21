"""Card statements, computed from the closing day rather than stored (ADR 0004).

The statement due in month M holds what was charged from the closing day of M-1 up to (not including) the
closing day of M; a purchase on the closing day goes to the next statement, as card issuers do. If the
bank moves the closing date, changing the card's closing day recomputes every statement.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financepro.accounts.models import Account
from financepro.cards.installments import add_months
from financepro.categorization.models import Kind
from financepro.transactions.models import Transaction

Status = Literal["open", "paid", "partial", "unpaid"]


def _on_day(month: date, day: int) -> date:
    """`day` of the month of `month`, or its last day when the month is shorter (closing on the 31st)."""
    last = (add_months(month.replace(day=1), 1) - month.replace(day=1)).days
    return month.replace(day=min(day, last))


@dataclass(frozen=True)
class Statement:
    month: date  # first day of the month it is due in
    opens: date
    closes: date
    due: date
    charges_cents: int  # what the statement bills (purchases minus refunds)
    paid_cents: int  # payments received after it closed, up to the next closing
    status: Status


def cycle(account: Account, month: date) -> tuple[date, date, date]:
    if account.closing_day is None or account.due_day is None:
        raise ValueError("only credit cards have statements")
    closes = _on_day(month, account.closing_day)
    opens = _on_day(add_months(month, -1), account.closing_day)
    due_month = month if account.due_day > account.closing_day else add_months(month, 1)
    return opens, closes, _on_day(due_month, account.due_day)


def statements(db: Session, account: Account, today: date) -> list[Statement]:
    visible = (Transaction.account_id == account.id, Transaction.deleted_at.is_(None))
    first = db.scalar(select(func.min(Transaction.effective_date)).where(*visible))
    if first is None:
        return []
    month = first.replace(day=1)
    if first >= cycle(account, month)[1]:
        month = add_months(month, 1)
    found = []
    while True:
        opens, closes, due = cycle(account, month)
        charges = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                *visible,
                Transaction.kind == Kind.REGULAR,
                Transaction.effective_date >= opens,
                Transaction.effective_date < closes,
            )
        )
        next_close = cycle(account, add_months(month, 1))[1]
        paid = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                *visible,
                Transaction.kind == Kind.TRANSFER,
                Transaction.amount_cents > 0,
                Transaction.date >= closes,
                Transaction.date < next_close,
            )
        )
        total = -int(charges or 0)
        paid_cents = int(paid or 0)
        status: Status
        if closes > today:
            status = "open"
        elif paid_cents >= total:
            status = "paid"
        elif paid_cents > 0:
            status = "partial"
        else:
            status = "unpaid"
        found.append(Statement(month, opens, closes, due, total, paid_cents, status))
        if closes > today:
            break
        month = add_months(month, 1)
    return found[::-1]
