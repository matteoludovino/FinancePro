"""Money moving between a person's own accounts: the bill paid from checking and received by the card,
the Pix to their account at another bank. A transfer is neither spending nor income (ADR 0005).

Candidates are pairs of opposite amounts in two different accounts within 3 days. Only unambiguous ones
count: if a debit could match two credits (two R$ 500 transfers that week), nothing is guessed. Pairs
whose two sides are already marked as transfers (by the default rules) are linked on import; the others
are suggested and a person confirms.
"""

from collections import defaultdict
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from financepro import clock
from financepro.accounts.models import Account, AccountKind
from financepro.categorization.models import Kind
from financepro.transactions.models import Transaction

WINDOW_DAYS = 3


@dataclass(frozen=True)
class Pair:
    outflow: Transaction
    inflow: Transaction


def candidates(db: Session, owner_id: int, among: set[int] | None = None) -> list[Pair]:
    """Unambiguous pairs of unlinked transactions. With `among`, at least one side must be in it."""
    out, inc = aliased(Transaction), aliased(Transaction)
    query = (
        select(out, inc)
        .join(
            inc,
            and_(
                inc.owner_id == out.owner_id,
                inc.account_id != out.account_id,
                inc.amount_cents == -out.amount_cents,
                func.abs(inc.date - out.date) <= WINDOW_DAYS,
            ),
        )
        .where(
            out.owner_id == owner_id,
            out.amount_cents < 0,
            *(side.deleted_at.is_(None) for side in (out, inc)),
            *(side.transfer_pair_id.is_(None) for side in (out, inc)),
            *(side.kind != Kind.IGNORED for side in (out, inc)),
            *(side.not_a_transfer.is_(False) for side in (out, inc)),
            # A purchase on the card is never one side of a transfer; its credits (payments) can be.
            out.account_id.not_in(select(Account.id).where(Account.kind == AccountKind.CREDIT_CARD)),
        )
    )
    if among is not None:
        query = query.where(or_(out.id.in_(among), inc.id.in_(among)))
    rows = db.execute(query).all()
    by_out: defaultdict[int, list[Transaction]] = defaultdict(list)
    by_in: defaultdict[int, list[Transaction]] = defaultdict(list)
    for outflow, inflow in rows:
        by_out[outflow.id].append(inflow)
        by_in[inflow.id].append(outflow)
    return [
        Pair(outflow, inflow)
        for outflow, inflow in rows
        if len(by_out[outflow.id]) == 1 and len(by_in[inflow.id]) == 1
    ]


def _link(pair: Pair) -> None:
    for side, other in ((pair.outflow, pair.inflow), (pair.inflow, pair.outflow)):
        side.transfer_pair_id = other.id
        side.kind = Kind.TRANSFER
        side.category_id = None
        side.category_source = None


def link_obvious(db: Session, owner_id: int, new_ids: set[int]) -> int:
    """On import: links pairs whose two sides the rules already call transfers."""
    pairs = [
        p
        for p in candidates(db, owner_id, among=new_ids)
        if p.outflow.kind is Kind.TRANSFER and p.inflow.kind is Kind.TRANSFER
    ]
    for pair in pairs:
        _link(pair)
    db.flush()
    return len(pairs)


def suggestions(db: Session, owner_id: int) -> list[Pair]:
    """Pairs for a person to confirm: at least one side still counted as spending or income."""
    return [
        p for p in candidates(db, owner_id) if p.outflow.kind is Kind.REGULAR or p.inflow.kind is Kind.REGULAR
    ]


def _owned(db: Session, owner_id: int, transaction_id: int) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.owner_id == owner_id,
            Transaction.deleted_at.is_(None),
        )
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    return transaction


def confirm(db: Session, owner_id: int, first_id: int, second_id: int) -> Pair:
    first, second = _owned(db, owner_id, first_id), _owned(db, owner_id, second_id)
    if first.account_id == second.account_id:
        raise HTTPException(status_code=422, detail="Uma transferência liga duas contas diferentes.")
    if first.amount_cents != -second.amount_cents:
        raise HTTPException(
            status_code=422, detail="Os valores precisam ser iguais, um saindo e outro entrando."
        )
    if first.transfer_pair_id is not None or second.transfer_pair_id is not None:
        raise HTTPException(status_code=409, detail="Um dos lançamentos já faz parte de outra transferência.")
    pair = Pair(first, second) if first.amount_cents < 0 else Pair(second, first)
    _link(pair)
    now = clock.now()
    first.edited_at = second.edited_at = now
    db.commit()
    return pair


def unlink(db: Session, owner_id: int, transaction_id: int) -> None:
    transaction = _owned(db, owner_id, transaction_id)
    if transaction.transfer_pair_id is None:
        raise HTTPException(status_code=409, detail="Este lançamento não está ligado a outro.")
    other = db.get(Transaction, transaction.transfer_pair_id)
    now = clock.now()
    for side in (transaction, other):
        if side is not None:
            side.transfer_pair_id = None
            side.edited_at = now
    db.commit()


def dismiss(db: Session, owner_id: int, first_id: int, second_id: int) -> None:
    """ "Not a transfer": neither side is suggested again."""
    for transaction_id in (first_id, second_id):
        _owned(db, owner_id, transaction_id).not_a_transfer = True
    db.commit()
