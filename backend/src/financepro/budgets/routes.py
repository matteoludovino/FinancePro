from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from financepro import clock, months
from financepro.auth.sessions import CurrentUser
from financepro.budgets import service
from financepro.budgets.service import Status
from financepro.db import get_db

router = APIRouter(prefix="/budgets", tags=["budgets"])

DB = Annotated[Session, Depends(get_db)]


class BudgetOut(BaseModel):
    category_id: int
    limit_cents: int
    spent_cents: int
    committed_cents: int
    status: Status


class LimitIn(BaseModel):
    # null removes the budget from `from_month` on; earlier months keep theirs.
    limit_cents: Annotated[int, Field(gt=0, le=10**12)] | None
    from_month: str | None = None


@router.get("")
def list_budgets(user: CurrentUser, db: DB, month: str | None = None) -> list[BudgetOut]:
    when = months.parse(month) if month else clock.today().replace(day=1)
    return [BudgetOut.model_validate(s, from_attributes=True) for s in service.statuses(db, user.id, when)]


@router.put("/{category_id}")
def set_limit(category_id: int, body: LimitIn, user: CurrentUser, db: DB) -> list[BudgetOut]:
    when = months.parse(body.from_month) if body.from_month else clock.today().replace(day=1)
    service.set_limit(db, user.id, category_id, body.limit_cents, when)
    return [BudgetOut.model_validate(s, from_attributes=True) for s in service.statuses(db, user.id, when)]
