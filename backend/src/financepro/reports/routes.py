from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from financepro import clock, months
from financepro.auth.sessions import CurrentUser
from financepro.cards.installments import add_months
from financepro.db import get_db
from financepro.reports import service

router = APIRouter(prefix="/reports", tags=["reports"])

DB = Annotated[Session, Depends(get_db)]


def _month(month: str | None) -> date:
    return months.parse(month) if month else clock.today().replace(day=1)


class OverviewOut(BaseModel):
    month: date
    income_cents: int
    expense_cents: int
    previous_income_cents: int
    previous_expense_cents: int
    uncategorized: int
    ai_pending: int


class FlowOut(BaseModel):
    month: date
    income_cents: int
    expense_cents: int


class CategoryTotalOut(BaseModel):
    category_id: int | None
    name: str
    total_cents: int
    children: list[CategoryTotalOut]


class MerchantOut(BaseModel):
    merchant: str
    total_cents: int
    count: int


class CommitmentOut(BaseModel):
    month: date
    amount_cents: int


@router.get("/overview")
def overview(user: CurrentUser, db: DB, month: str | None = None) -> OverviewOut:
    return OverviewOut.model_validate(service.overview(db, user.id, _month(month)), from_attributes=True)


@router.get("/flow")
def flow(
    user: CurrentUser, db: DB, until: str | None = None, count: Annotated[int, Query(ge=1, le=36)] = 12
) -> list[FlowOut]:
    last = _month(until)
    found = service.flow(db, user.id, add_months(last, -(count - 1)), last)
    return [FlowOut.model_validate(f, from_attributes=True) for f in found]


@router.get("/categories")
def categories(user: CurrentUser, db: DB, month: str | None = None) -> list[CategoryTotalOut]:
    found = service.spending_by_category(db, user.id, _month(month))
    return [CategoryTotalOut.model_validate(c, from_attributes=True) for c in found]


@router.get("/merchants")
def merchants(user: CurrentUser, db: DB, month: str | None = None) -> list[MerchantOut]:
    return [
        MerchantOut.model_validate(m, from_attributes=True)
        for m in service.top_merchants(db, user.id, _month(month))
    ]


@router.get("/commitments")
def commitments(
    user: CurrentUser, db: DB, count: Annotated[int, Query(ge=1, le=24)] = 6
) -> list[CommitmentOut]:
    first = add_months(clock.today().replace(day=1), 1)
    return [CommitmentOut(month=m, amount_cents=a) for m, a in service.commitments(db, user.id, first, count)]
