from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from financepro.auth.sessions import CurrentUser
from financepro.db import get_db
from financepro.transactions.schemas import TransactionOut
from financepro.transfers import service

router = APIRouter(prefix="/transfers", tags=["transfers"])

DB = Annotated[Session, Depends(get_db)]


class PairOut(BaseModel):
    outflow: TransactionOut
    inflow: TransactionOut


class PairIn(BaseModel):
    first_id: int
    second_id: int


def _out(pair: service.Pair) -> PairOut:
    return PairOut(
        outflow=TransactionOut.model_validate(pair.outflow), inflow=TransactionOut.model_validate(pair.inflow)
    )


@router.get("/suggestions")
def suggestions(user: CurrentUser, db: DB) -> list[PairOut]:
    return [_out(pair) for pair in service.suggestions(db, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def confirm(body: PairIn, user: CurrentUser, db: DB) -> PairOut:
    return _out(service.confirm(db, user.id, body.first_id, body.second_id))


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink(transaction_id: int, user: CurrentUser, db: DB) -> None:
    service.unlink(db, user.id, transaction_id)


@router.post("/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(body: PairIn, user: CurrentUser, db: DB) -> None:
    service.dismiss(db, user.id, body.first_id, body.second_id)
