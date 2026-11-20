from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from financepro.accounts import service
from financepro.accounts.schemas import AccountIn, AccountOut, AccountPatch
from financepro.auth.sessions import CurrentUser
from financepro.db import get_db

router = APIRouter(prefix="/accounts", tags=["accounts"])

DB = Annotated[Session, Depends(get_db)]


@router.get("")
def list_accounts(user: CurrentUser, db: DB) -> list[AccountOut]:
    return [AccountOut.model_validate(a) for a in service.list_accounts(db, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(body: AccountIn, user: CurrentUser, db: DB) -> AccountOut:
    return AccountOut.model_validate(service.create_account(db, user.id, body))


@router.get("/{account_id}")
def get_account(account_id: int, user: CurrentUser, db: DB) -> AccountOut:
    return AccountOut.model_validate(service.get_account(db, user.id, account_id))


@router.patch("/{account_id}")
def update_account(account_id: int, body: AccountPatch, user: CurrentUser, db: DB) -> AccountOut:
    return AccountOut.model_validate(service.update_account(db, user.id, account_id, body))


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, user: CurrentUser, db: DB) -> None:
    service.delete_account(db, user.id, account_id)
