from datetime import date

from fastapi import HTTPException
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from financepro import clock, months
from financepro.categories.service import get_category
from financepro.categorization.engine import Categorizer
from financepro.categorization.models import Kind, Rule
from financepro.transactions.models import CategorySource, Transaction
from financepro.transactions.schemas import BulkIn, TransactionPatch


def _month_range(month: str) -> tuple[date, date]:
    start = months.parse(month)
    return start, months.following(start)


def _visible(owner_id: int) -> Select[Transaction]:
    return select(Transaction).where(Transaction.owner_id == owner_id, Transaction.deleted_at.is_(None))


def list_transactions(
    db: Session,
    owner_id: int,
    *,
    month: str | None,
    account_id: int | None,
    category_id: int | None,
    uncategorized: bool,
    kind: Kind | None,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Transaction], int]:
    query = _visible(owner_id)
    if month:
        start, end = _month_range(month)
        query = query.where(Transaction.effective_date >= start, Transaction.effective_date < end)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if uncategorized:
        query = query.where(Transaction.kind == Kind.REGULAR, Transaction.category_id.is_(None))
    if kind is not None:
        query = query.where(Transaction.kind == kind)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Transaction.merchant.ilike(like), Transaction.description_raw.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(page)), total


def get_transaction(db: Session, owner_id: int, transaction_id: int) -> Transaction:
    transaction = db.scalar(_visible(owner_id).where(Transaction.id == transaction_id))
    if transaction is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    return transaction


def _categorize(transaction: Transaction, category_id: int | None) -> None:
    transaction.kind = Kind.REGULAR
    transaction.category_id = category_id
    transaction.category_source = CategorySource.USER if category_id is not None else None


def update_transaction(
    db: Session, owner_id: int, transaction_id: int, data: TransactionPatch
) -> Transaction:
    transaction = get_transaction(db, owner_id, transaction_id)
    changes = data.model_dump(exclude_unset=True)
    if "kind" in changes and data.kind is not None:
        transaction.kind = data.kind
        if data.kind is not Kind.REGULAR:
            transaction.category_id = None
            transaction.category_source = None
    if "category_id" in changes:
        if data.category_id is not None:
            get_category(db, owner_id, data.category_id)
        _categorize(transaction, data.category_id)
    if data.notes is not None:
        transaction.notes = data.notes
    transaction.edited_at = clock.now()
    db.commit()
    return transaction


def bulk_update(db: Session, owner_id: int, data: BulkIn) -> int:
    rows = list(db.scalars(_visible(owner_id).where(Transaction.id.in_(data.ids))))
    if len(rows) != len(set(data.ids)):
        raise HTTPException(status_code=404, detail="Algum dos lançamentos não foi encontrado.")
    if data.action == "categorize":
        if data.category_id is None:
            raise HTTPException(status_code=422, detail="Escolha a categoria.")
        get_category(db, owner_id, data.category_id)
    now = clock.now()
    for transaction in rows:
        match data.action:
            case "categorize":
                _categorize(transaction, data.category_id)
            case "regular":
                transaction.kind = Kind.REGULAR
            case "transfer" | "ignore":
                transaction.kind = Kind.TRANSFER if data.action == "transfer" else Kind.IGNORED
                transaction.category_id = None
                transaction.category_source = None
            case "delete":
                transaction.deleted_at = now
        transaction.edited_at = now
    db.commit()
    return len(rows)


def delete_transaction(db: Session, owner_id: int, transaction_id: int) -> None:
    """A tombstone, not a DELETE: its fingerprint keeps the next import of the same file from reviving it."""
    transaction = get_transaction(db, owner_id, transaction_id)
    transaction.deleted_at = clock.now()
    transaction.edited_at = clock.now()
    db.commit()


def apply_rule(db: Session, owner_id: int, rule: Rule) -> int:
    """Applies a rule to the transactions it matches, except those a person categorized by hand."""
    categorizer = Categorizer.for_owner(db, owner_id)
    candidates = db.scalars(
        _visible(owner_id).where(
            or_(Transaction.category_source.is_(None), Transaction.category_source != CategorySource.USER)
        )
    )
    changed = 0
    for transaction in candidates:
        decision = categorizer.decide(
            transaction.description_raw, transaction.amount_cents, transaction.account_id
        )
        if decision.rule_id != rule.id:
            continue
        if (transaction.kind, transaction.category_id) != (decision.kind, decision.category_id):
            transaction.kind = decision.kind
            transaction.category_id = decision.category_id
            transaction.category_source = CategorySource.RULE if decision.category_id else None
            changed += 1
    db.commit()
    return changed
