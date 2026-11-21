from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from financepro import clock
from financepro.accounts.models import AccountKind
from financepro.accounts.service import get_account
from financepro.auth.sessions import CurrentUser
from financepro.cards import installments
from financepro.cards.statements import Status, statements
from financepro.db import get_db

router = APIRouter(tags=["cards"])

DB = Annotated[Session, Depends(get_db)]


class StatementOut(BaseModel):
    month: date
    opens: date
    closes: date
    due: date
    charges_cents: int
    paid_cents: int
    status: Status


class ScheduledOut(BaseModel):
    month: date
    amount_cents: int


class InstallmentsOut(BaseModel):
    id: int
    account_id: int
    merchant: str
    installments: int
    paid: int
    amount_cents: int
    last_month: date
    future: list[ScheduledOut]


@router.get("/accounts/{account_id}/statements")
def list_statements(account_id: int, user: CurrentUser, db: DB) -> list[StatementOut]:
    account = get_account(db, user.id, account_id)
    if account.kind is not AccountKind.CREDIT_CARD:
        raise HTTPException(status_code=422, detail="Só cartões de crédito têm fatura.")
    return [
        StatementOut.model_validate(s, from_attributes=True) for s in statements(db, account, clock.today())
    ]


@router.get("/installments")
def list_installments(user: CurrentUser, db: DB) -> list[InstallmentsOut]:
    return [
        InstallmentsOut(
            id=p.group.id,
            account_id=p.group.account_id,
            merchant=p.group.merchant,
            installments=p.group.installments,
            paid=p.paid,
            amount_cents=p.amount_cents,
            last_month=p.last_month,
            future=[ScheduledOut(month=month, amount_cents=amount) for month, amount in p.future],
        )
        for p in installments.progress(db, user.id)
    ]
