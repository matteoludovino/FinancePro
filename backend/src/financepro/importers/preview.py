"""A file + a mapping → rows with a status, before anything is written.

Statuses: `new`, `duplicate` (already imported: same bank id or fingerprint, deleted ones included),
`possible_duplicate` (same amount within 3 days but not identical: the bank may have rewritten the
description between exports; the person decides) and `error` (the line can't be read).
"""

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from financepro.cards import installments
from financepro.categorization.engine import Categorizer
from financepro.importers.mapping import Mapping, Sign
from financepro.importers.parsing import ParseError, parse_cents, parse_date
from financepro.importers.reader import Table
from financepro.transactions.dedup import Occurrences, fingerprint
from financepro.transactions.models import Transaction

Status = Literal["new", "duplicate", "possible_duplicate", "error"]
NEARBY_DAYS = 3


@dataclass
class Row:
    line: int  # line number in the file, as a person counts them
    status: Status
    description: str
    date: str | None = None
    effective_date: str | None = None
    installment_k: int | None = None
    installment_n: int | None = None
    amount_cents: int | None = None
    external_id: str | None = None
    occurrence_n: int = 0
    fingerprint: str | None = None
    message: str | None = None
    match: dict[str, Any] | None = None
    merchant: str = ""
    kind: str = "regular"
    category_id: int | None = None
    category_source: str | None = None


def _amount(cells: list[str], mapping: Mapping) -> int:
    if mapping.amount is not None:
        cents = parse_cents(cells[mapping.amount], mapping.decimals)
    else:
        debit = cells[mapping.debit].strip() if mapping.debit is not None else ""
        credit = cells[mapping.credit].strip() if mapping.credit is not None else ""
        if debit and credit:
            raise ParseError("A linha tem débito e crédito ao mesmo tempo.")
        if not debit and not credit:
            raise ParseError("Sem valor.")
        cents = (
            -abs(parse_cents(debit, mapping.decimals))
            if debit
            else abs(parse_cents(credit, mapping.decimals))
        )
    return -cents if mapping.sign is Sign.INVERTED else cents


def parse_rows(table: Table, mapping: Mapping) -> list[Row]:
    width = len(table.header)
    if any(column >= width for column in mapping.columns()):
        raise ValueError("O mapeamento aponta para uma coluna que o arquivo não tem.")
    occurrences = Occurrences()
    rows = []
    for offset, cells in enumerate(table.rows):
        line = table.header_row + offset + 2
        description = " - ".join(cells[i].strip() for i in mapping.description if cells[i].strip())[:300]
        if not description:
            rows.append(Row(line, "error", "", message="Sem descrição."))
            continue
        try:
            day = parse_date(cells[mapping.date], mapping.date_format)
            cents = _amount(cells, mapping)
        except ParseError as error:
            rows.append(Row(line, "error", description, message=str(error)))
            continue
        if cents == 0:
            rows.append(
                Row(line, "error", description, date=day.isoformat(), message="Valor zero; linha ignorada.")
            )
            continue
        external_id = (
            cells[mapping.external_id].strip()[:100] or None if mapping.external_id is not None else None
        )
        n = occurrences.next(day, cents, description)
        count = installments.counter(description)
        rows.append(
            Row(
                line,
                "new",
                description,
                date=day.isoformat(),
                installment_k=count[0] if count else None,
                installment_n=count[1] if count else None,
                amount_cents=cents,
                external_id=external_id,
                occurrence_n=n,
                fingerprint=fingerprint(day, cents, description, n),
            )
        )
    _set_effective_dates(rows, mapping)
    return rows


def _count(row: Row) -> tuple[int, int] | None:
    return (row.installment_k, row.installment_n) if row.installment_k and row.installment_n else None


def _set_effective_dates(rows: list[Row], mapping: Mapping) -> None:
    dated = [row for row in rows if row.date]
    convention: installments.Convention = (
        installments.detect_convention((date.fromisoformat(r.date or ""), _count(r)) for r in dated)
        if mapping.installment_dates == "auto"
        else mapping.installment_dates
    )
    for row in dated:
        day = installments.effective_date(date.fromisoformat(row.date or ""), _count(row), convention)
        row.effective_date = day.isoformat()


def classify(db: Session, owner_id: int, account_id: int, rows: list[Row]) -> None:
    """Marks duplicates against what the account already has, and decides each new row's category."""
    readable = [row for row in rows if row.status != "error"]
    if not readable:
        return
    in_account = Transaction.account_id == account_id
    columns = (Transaction.id, Transaction.deleted_at)
    fingerprints = {row.fingerprint for row in readable}
    external_ids = {row.external_id for row in readable if row.external_id}
    by_fingerprint = {
        fp: (tx_id, deleted)
        for fp, tx_id, deleted in db.execute(
            select(Transaction.fingerprint, *columns).where(
                in_account, Transaction.fingerprint.in_(fingerprints)
            )
        )
    }
    by_external_id = {
        ext: (tx_id, deleted)
        for ext, tx_id, deleted in db.execute(
            select(Transaction.external_id, *columns).where(
                in_account, Transaction.external_id.in_(external_ids)
            )
        )
        if ext
    }

    # First the exact duplicates, so the transactions they match can't also be someone's "possible" match.
    claimed: set[int] = set()
    for row in readable:
        known = by_external_id.get(row.external_id or "") or by_fingerprint.get(row.fingerprint or "")
        if known:
            tx_id, deleted_at = known
            claimed.add(tx_id)
            row.status = "duplicate"
            row.message = "Você excluiu este lançamento antes." if deleted_at else "Já importado."

    fresh = [row for row in readable if row.status == "new"]
    if not fresh:
        return
    days = [date.fromisoformat(row.date or "") for row in fresh]
    window = (min(days) - timedelta(NEARBY_DAYS), max(days) + timedelta(NEARBY_DAYS))
    nearby = list(
        db.scalars(
            select(Transaction).where(
                in_account, Transaction.deleted_at.is_(None), Transaction.date.between(*window)
            )
        )
    )
    categorizer = Categorizer.for_owner(db, owner_id)
    for row, day in zip(fresh, days, strict=True):
        candidate = next(
            (
                t
                for t in nearby
                if t.id not in claimed
                and t.amount_cents == row.amount_cents
                and abs((t.date - day).days) <= NEARBY_DAYS
            ),
            None,
        )
        if candidate is not None:
            claimed.add(candidate.id)
            row.status = "possible_duplicate"
            row.match = {
                "id": candidate.id,
                "date": candidate.date.isoformat(),
                "description": candidate.description_raw,
                "amount_cents": candidate.amount_cents,
            }
        decision = categorizer.decide(row.description, row.amount_cents or 0, account_id)
        row.merchant = decision.merchant
        row.kind = decision.kind.value
        row.category_id = decision.category_id
        row.category_source = decision.source


def summarize(rows: list[Row]) -> dict[str, int]:
    counts = {"total": len(rows), "new": 0, "duplicate": 0, "possible_duplicate": 0, "error": 0}
    for row in rows:
        counts[row.status] += 1
    return counts


def to_json(rows: list[Row]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def from_json(data: list[dict[str, Any]]) -> list[Row]:
    return [Row(**item) for item in data]
