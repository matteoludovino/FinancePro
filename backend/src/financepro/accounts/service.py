"""Every query is scoped by owner: a foreign id is indistinguishable from one that doesn't exist (404)."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financepro.accounts.models import Account, AccountKind
from financepro.accounts.schemas import AccountIn, AccountPatch

DUPLICATE_NAME = "Você já tem uma conta com este nome."
CARD_DAYS_REQUIRED = "Informe o dia de fechamento e o de vencimento da fatura."


def list_accounts(db: Session, owner_id: int) -> list[Account]:
    query = select(Account).where(Account.owner_id == owner_id).order_by(Account.is_archived, Account.name)
    return list(db.scalars(query))


def get_account(db: Session, owner_id: int, account_id: int) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.owner_id == owner_id))
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    return account


def _save(db: Session, account: Account) -> Account:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_NAME) from None
    db.commit()
    return account


def create_account(db: Session, owner_id: int, data: AccountIn) -> Account:
    account = Account(owner_id=owner_id, **data.model_dump())
    db.add(account)
    return _save(db, account)


def update_account(db: Session, owner_id: int, account_id: int, data: AccountPatch) -> Account:
    account = get_account(db, owner_id, account_id)
    changes = data.model_dump(exclude_unset=True)
    card_days = {"closing_day", "due_day"}
    for field, value in changes.items():
        if field in card_days and account.kind is not AccountKind.CREDIT_CARD:
            continue  # only cards have a statement cycle
        if value is None and field not in card_days:
            continue  # null means "unchanged" for the required fields
        setattr(account, field, value)
    if account.kind is AccountKind.CREDIT_CARD and (account.closing_day is None or account.due_day is None):
        raise HTTPException(status_code=422, detail=CARD_DAYS_REQUIRED)
    return _save(db, account)


def delete_account(db: Session, owner_id: int, account_id: int) -> None:
    db.delete(get_account(db, owner_id, account_id))
    db.commit()
