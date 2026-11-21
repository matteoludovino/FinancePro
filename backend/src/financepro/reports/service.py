"""Reports over regular transactions, by `effective_date` (ADR 0004).

Transfers and ignored lines never count. A transaction is income or spending by its category's type;
an uncategorized one by its sign. A refund (a positive amount in a spending category) lowers spending
instead of counting as income.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import ColumnElement, and_, case, func, select
from sqlalchemy.orm import Session, aliased

from financepro import months
from financepro.cards import installments
from financepro.categories.models import Category
from financepro.categories.taxonomy import CategoryType
from financepro.categorization.models import Kind
from financepro.transactions.models import Transaction


def _regular(owner_id: int, start: date, end: date) -> list[ColumnElement[bool]]:
    return [
        Transaction.owner_id == owner_id,
        Transaction.deleted_at.is_(None),
        Transaction.kind == Kind.REGULAR,
        Transaction.effective_date >= start,
        Transaction.effective_date < end,
    ]


_is_income = case(
    (Category.type == CategoryType.INCOME, True),
    (Category.type == CategoryType.EXPENSE, False),
    else_=Transaction.amount_cents > 0,
)


@dataclass(frozen=True)
class Flow:
    month: date
    income_cents: int
    expense_cents: int


def flow(db: Session, owner_id: int, first: date, last: date) -> list[Flow]:
    """Income and spending per month, from `first` to `last` (inclusive), months with nothing included."""
    month = func.date_trunc("month", Transaction.effective_date)
    query = (
        select(
            month.label("month"),
            func.coalesce(func.sum(case((_is_income, Transaction.amount_cents), else_=0)), 0),
            func.coalesce(func.sum(case((_is_income, 0), else_=-Transaction.amount_cents)), 0),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*_regular(owner_id, first, months.following(last)))
        .group_by(month)
    )
    found = {when.date(): (int(income), int(expense)) for when, income, expense in db.execute(query)}
    result, current = [], first
    while current <= last:
        income, expense = found.get(current, (0, 0))
        result.append(Flow(current, income, expense))
        current = months.following(current)
    return result


@dataclass(frozen=True)
class CategoryTotal:
    category_id: int | None  # None: uncategorized
    name: str
    total_cents: int  # spending, positive
    children: list[CategoryTotal]


@dataclass
class _Top:
    name: str
    total: int = 0
    children: list[CategoryTotal] = field(default_factory=list)


def spending_by_category(db: Session, owner_id: int, month: date) -> list[CategoryTotal]:
    """Spending in the month per top-level category, with its subcategories; uncategorized outflows last."""
    parent = aliased(Category)
    query = (
        select(Category.id, Category.name, parent.id, parent.name, func.sum(-Transaction.amount_cents))
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .outerjoin(parent, parent.id == Category.parent_id)
        .where(
            *_regular(owner_id, month, months.following(month)),
            ~_is_income,
        )
        .group_by(Category.id, Category.name, parent.id, parent.name)
    )
    tops: dict[int | None, _Top] = {}
    for category_id, name, parent_id, parent_name, total in db.execute(query):
        top_id, top_name = (parent_id, parent_name) if parent_id else (category_id, name or "Sem categoria")
        top = tops.setdefault(top_id, _Top(top_name))
        top.total += int(total)
        if parent_id:
            top.children.append(CategoryTotal(category_id, name, int(total), []))
    result = [
        CategoryTotal(top_id, top.name, top.total, sorted(top.children, key=lambda c: -c.total_cents))
        for top_id, top in tops.items()
    ]
    return sorted(result, key=lambda c: (c.category_id is None, -c.total_cents))


@dataclass(frozen=True)
class MerchantTotal:
    merchant: str
    total_cents: int
    count: int


def top_merchants(db: Session, owner_id: int, month: date, limit: int = 8) -> list[MerchantTotal]:
    query = (
        select(Transaction.merchant, func.sum(-Transaction.amount_cents), func.count())
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(*_regular(owner_id, month, months.following(month)), ~_is_income)
        .group_by(Transaction.merchant)
        .order_by(func.sum(-Transaction.amount_cents).desc())
        .limit(limit)
    )
    return [MerchantTotal(m, int(t), int(c)) for m, t, c in db.execute(query) if t > 0]


@dataclass(frozen=True)
class Overview:
    month: date
    income_cents: int
    expense_cents: int
    previous_income_cents: int
    previous_expense_cents: int
    uncategorized: int
    ai_pending: int


def overview(db: Session, owner_id: int, month: date) -> Overview:
    previous, current = flow(db, owner_id, installments.add_months(month, -1), month)
    in_month = _regular(owner_id, month, months.following(month))
    uncategorized = db.scalar(select(func.count()).where(*in_month, Transaction.category_id.is_(None)))
    ai_pending = db.scalar(
        select(func.count()).where(
            Transaction.owner_id == owner_id,
            Transaction.deleted_at.is_(None),
            Transaction.category_id.is_(None),
            Transaction.ai_category_id.is_not(None),
        )
    )
    return Overview(
        month,
        current.income_cents,
        current.expense_cents,
        previous.income_cents,
        previous.expense_cents,
        int(uncategorized or 0),
        int(ai_pending or 0),
    )


def commitments(db: Session, owner_id: int, first: date, count: int) -> list[tuple[date, int]]:
    """Installments still to come, per month: how much of the next months is already spoken for."""
    totals: defaultdict[date, int] = defaultdict(int)
    for progress in installments.progress(db, owner_id):
        for month, amount in progress.future:
            totals[month] -= amount
    return [(m, totals.get(m, 0)) for m in (installments.add_months(first, i) for i in range(count))]


def category_family(db: Session, owner_id: int, category_id: int) -> set[int]:
    children = db.scalars(
        select(Category.id).where(and_(Category.owner_id == owner_id, Category.parent_id == category_id))
    )
    return {category_id, *children}


def spent_in(db: Session, owner_id: int, month: date, family: set[int]) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(-Transaction.amount_cents), 0)).where(
            *_regular(owner_id, month, months.following(month)),
            Transaction.category_id.in_(family),
        )
    )
    return int(total or 0)
