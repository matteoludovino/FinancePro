"""Installments: "LOJA X - Parcela 3/10" on one statement, 4/10 on the next.

Card exports list each installment once, on the statement that bills it. Some date it on that statement;
others keep the original purchase date on every installment. `effective_date` puts each installment in
the month it is billed either way (ADR 0004), and installments of one purchase are grouped across files.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from financepro.cards.models import InstallmentGroup
from financepro.categorization.normalizer import merchant_of
from financepro.text import canonical
from financepro.transactions.models import Transaction

Convention = Literal["billing", "purchase"]

_COUNTER = re.compile(r"(?:parcela|parc\.?)\s*(\d{1,2})\s*(?:/|de)\s*(\d{1,2})|\s(\d{1,2})/(\d{1,2})\s*$")


def counter(description: str) -> tuple[int, int] | None:
    """(k, n) from "Parcela 3/10", "PARC 03/10", "Parcela 3 de 10" or a trailing "03/10"."""
    found = _COUNTER.search(canonical(description))
    if not found:
        return None
    k, n = (int(g) for g in (found.group(1, 2) if found.group(1) else found.group(3, 4)))
    return (k, n) if 1 <= k <= n and 2 <= n <= 48 else None


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - date(year, month, 1)).days
    return date(year, month, min(day.day, last))


def month_start(day: date) -> date:
    return day.replace(day=1)


def detect_convention(rows: Iterable[tuple[date, tuple[int, int] | None]]) -> Convention:
    """Which date the file gives installments 2..n: the billing date (inside the statement's period, like
    any purchase) or the original purchase date (k - 1 months earlier).

    Votes from installments k >= 2 against the period the file's other lines cover: a date inside it fits
    billing; a date outside it that lands inside once moved k - 1 months fits purchase. Ties: billing.
    """
    items = list(rows)
    plain = [day for day, count in items if count is None]
    if not plain:
        return "billing"
    start, end = min(plain), max(plain)
    billing = purchase = 0
    for day, count in items:
        if count is None or count[0] < 2:
            continue
        if start <= day <= end:
            billing += 1
        elif start <= add_months(day, count[0] - 1) <= end:
            purchase += 1
    return "purchase" if purchase > billing else "billing"


def effective_date(day: date, count: tuple[int, int] | None, convention: Convention) -> date:
    if count is None or convention == "billing":
        return day
    return add_months(day, count[0] - 1)


def link(db: Session, owner_id: int, transactions: list[Transaction]) -> None:
    """Puts each new installment in its purchase's group, creating the group the first time.

    Siblings share the account, the merchant without its counter, the number of installments and the
    month of installment 1 (± one month: billing days move). The amount is not compared: rounding makes the
    first installment differ by a cent. A group never takes two of the same k.
    """
    for transaction in sorted(transactions, key=lambda t: (t.effective_date, t.id)):
        if transaction.installment_k is None or transaction.installment_n is None:
            continue
        k, n = transaction.installment_k, transaction.installment_n
        key = canonical(merchant_of(transaction.description_raw).name)
        first = month_start(add_months(transaction.effective_date, -(k - 1)))
        taken = exists().where(
            Transaction.installment_group_id == InstallmentGroup.id, Transaction.installment_k == k
        )
        group = db.scalar(
            select(InstallmentGroup)
            .where(
                InstallmentGroup.owner_id == owner_id,
                InstallmentGroup.account_id == transaction.account_id,
                InstallmentGroup.merchant_key == key,
                InstallmentGroup.installments == n,
                InstallmentGroup.first_month.between(add_months(first, -1), add_months(first, 1)),
                ~taken,
            )
            .order_by(InstallmentGroup.id)
            .limit(1)
        )
        if group is None:
            group = InstallmentGroup(
                owner_id=owner_id,
                account_id=transaction.account_id,
                merchant=transaction.merchant,
                merchant_key=key,
                installments=n,
                first_month=first,
            )
            db.add(group)
            db.flush()
        transaction.installment_group_id = group.id
        db.flush()


def drop_empty_groups(db: Session, owner_id: int) -> None:
    has_members = exists().where(Transaction.installment_group_id == InstallmentGroup.id)
    db.execute(delete(InstallmentGroup).where(InstallmentGroup.owner_id == owner_id, ~has_members))


@dataclass(frozen=True)
class Progress:
    group: InstallmentGroup
    paid: int  # the highest installment imported so far
    amount_cents: int  # the latest installment's amount (negative: money leaving)
    last_month: date  # month of the latest imported installment
    future: list[tuple[date, int]]  # (month, amount) for each installment still to come


def progress(db: Session, owner_id: int) -> list[Progress]:
    """Where each purchase stands, from its member transactions. Projected installments are not rows:
    when the next statement brings 4/10, it simply becomes the latest member."""
    members = db.execute(
        select(Transaction)
        .where(
            Transaction.owner_id == owner_id,
            Transaction.installment_group_id.is_not(None),
            Transaction.deleted_at.is_(None),
        )
        .order_by(Transaction.installment_k)
    ).scalars()
    latest: dict[int, Transaction] = {}
    for transaction in members:
        latest[transaction.installment_group_id or 0] = transaction
    groups = db.scalars(select(InstallmentGroup).where(InstallmentGroup.id.in_(latest)))
    result = []
    for group in groups:
        last = latest[group.id]
        k = last.installment_k or 0
        month = month_start(last.effective_date)
        future = [(add_months(month, i), last.amount_cents) for i in range(1, group.installments - k + 1)]
        result.append(Progress(group, k, last.amount_cents, month, future))
    return sorted(result, key=lambda p: (not p.future, p.future[-1][0] if p.future else p.last_month))
