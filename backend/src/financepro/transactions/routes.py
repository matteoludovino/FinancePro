from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from financepro.auth.sessions import CurrentUser
from financepro.categorization.models import Kind
from financepro.db import get_db
from financepro.transactions import service
from financepro.transactions.schemas import BulkIn, BulkOut, TransactionOut, TransactionPage, TransactionPatch

router = APIRouter(prefix="/transactions", tags=["transactions"])

DB = Annotated[Session, Depends(get_db)]


@router.get("")
def list_transactions(
    user: CurrentUser,
    db: DB,
    month: str | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
    kind: Kind | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionPage:
    items, total = service.list_transactions(
        db,
        user.id,
        month=month,
        account_id=account_id,
        category_id=category_id,
        uncategorized=uncategorized,
        kind=kind,
        q=q,
        limit=limit,
        offset=offset,
    )
    return TransactionPage(items=[TransactionOut.model_validate(t) for t in items], total=total)


@router.patch("/{transaction_id}")
def update_transaction(
    transaction_id: int, body: TransactionPatch, user: CurrentUser, db: DB
) -> TransactionOut:
    return TransactionOut.model_validate(service.update_transaction(db, user.id, transaction_id, body))


@router.post("/bulk")
def bulk(body: BulkIn, user: CurrentUser, db: DB) -> BulkOut:
    return BulkOut(updated=service.bulk_update(db, user.id, body))


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, user: CurrentUser, db: DB) -> None:
    service.delete_transaction(db, user.id, transaction_id)
