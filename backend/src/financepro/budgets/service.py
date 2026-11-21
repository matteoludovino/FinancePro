from dataclasses import dataclass
from datetime import date
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.orm import Session

from financepro.budgets.models import Budget
from financepro.cards import installments
from financepro.categories.service import get_category
from financepro.categories.taxonomy import CategoryType
from financepro.reports.service import category_family, spent_in

Status = Literal["ok", "warning", "over"]
WARNING_AT = 0.8


def limits_in(db: Session, owner_id: int, month: date) -> dict[int, int]:
    """The limit each category has in `month`: its latest budget row starting on or before it."""
    rows = db.execute(
        select(Budget.category_id, Budget.limit_cents)
        .where(Budget.owner_id == owner_id, Budget.starts_month <= month)
        .order_by(Budget.category_id, Budget.starts_month.desc())
        .ext(distinct_on(Budget.category_id))
    )
    return {category_id: limit for category_id, limit in rows if limit is not None}


def set_limit(
    db: Session, owner_id: int, category_id: int, limit_cents: int | None, from_month: date
) -> None:
    category = get_category(db, owner_id, category_id)
    if category.type is not CategoryType.EXPENSE:
        raise HTTPException(status_code=422, detail="Orçamento é para categorias de gasto.")
    statement = insert(Budget).values(
        owner_id=owner_id, category_id=category_id, starts_month=from_month, limit_cents=limit_cents
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[Budget.owner_id, Budget.category_id, Budget.starts_month],
            set_={"limit_cents": statement.excluded.limit_cents},
        )
    )
    db.commit()


@dataclass(frozen=True)
class BudgetStatus:
    category_id: int
    limit_cents: int
    spent_cents: int
    # Installments of earlier purchases that will be billed this month and aren't imported yet.
    committed_cents: int
    status: Status


def statuses(db: Session, owner_id: int, month: date) -> list[BudgetStatus]:
    """Spent plus committed against each limit. No linear end-of-month projection: fixed bills (rent on
    the 5th) make "spent so far x days in the month" mislead; what is certain is spent and committed."""
    limits = limits_in(db, owner_id, month)
    if not limits:
        return []
    upcoming = [
        (p.category_id, amount)
        for p in installments.progress(db, owner_id)
        for when, amount in p.future
        if when == month
    ]
    result = []
    for category_id, limit in limits.items():
        family = category_family(db, owner_id, category_id)
        spent = spent_in(db, owner_id, month, family)
        committed = -sum(amount for owner_category, amount in upcoming if owner_category in family)
        used = (spent + committed) / limit
        status: Status = "over" if used > 1 else "warning" if used >= WARNING_AT else "ok"
        result.append(BudgetStatus(category_id, limit, spent, committed, status))
    return sorted(result, key=lambda b: -(b.spent_cents + b.committed_cents) / b.limit_cents)
