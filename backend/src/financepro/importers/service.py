from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from financepro import clock
from financepro.accounts.models import Account
from financepro.accounts.service import get_account
from financepro.importers import preview
from financepro.importers.mapping import Mapping, detect, find_preset, signature
from financepro.importers.models import BatchStatus, ImportBatch, ImportProfile
from financepro.importers.reader import ReadError, Table, read_table
from financepro.transactions.dedup import FP_VERSION
from financepro.transactions.models import CategorySource, Transaction

PREVIEW_TTL = timedelta(hours=1)
SAMPLE_ROWS = 5


def get_batch(db: Session, owner_id: int, batch_id: int) -> ImportBatch:
    batch = db.scalar(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.owner_id == owner_id))
    if batch is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    return batch


def list_batches(db: Session, owner_id: int) -> list[ImportBatch]:
    query = (
        select(ImportBatch)
        .where(ImportBatch.owner_id == owner_id, ImportBatch.status != BatchStatus.PREVIEW)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        .limit(50)
    )
    return list(db.scalars(query))


def _read(data: bytes) -> Table:
    try:
        return read_table(data)
    except ReadError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


def _layout(table: Table) -> dict[str, Any]:
    return {
        "header": table.header,
        "sample": table.rows[:SAMPLE_ROWS],
        "delimiter": table.delimiter,
        "encoding": table.encoding,
        "header_row": table.header_row,
        "signature": signature(table),
    }


def _fill(db: Session, batch: ImportBatch, table: Table, mapping: Mapping | None) -> None:
    # Set before classify() queries the database: autoflush may insert the batch, and mapping is NOT NULL.
    batch.mapping = mapping.model_dump(mode="json") if mapping else {}
    rows: list[preview.Row] = []
    if mapping is not None:
        try:
            rows = preview.parse_rows(table, mapping)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        preview.classify(db, batch.owner_id, batch.account_id, rows)
    batch.rows = preview.to_json(rows)
    batch.summary = preview.summarize(rows)


def create_preview(db: Session, owner_id: int, account_id: int, filename: str, data: bytes) -> ImportBatch:
    account = get_account(db, owner_id, account_id)
    table = _read(data)
    # Abandoned previews hold a whole file each: clear this person's expired ones on the way in.
    db.execute(
        delete(ImportBatch).where(
            ImportBatch.owner_id == owner_id,
            ImportBatch.status == BatchStatus.PREVIEW,
            ImportBatch.expires_at < clock.now(),
        )
    )
    layout = _layout(table)
    profile = db.scalar(
        select(ImportProfile).where(
            ImportProfile.owner_id == owner_id, ImportProfile.signature == layout["signature"]
        )
    )
    warnings: list[str] = []
    if profile is not None:
        mapping: Mapping | None = Mapping.model_validate(profile.mapping)
        detected_by, label = "profile", "Mesmo formato da sua última importação"
    elif preset := find_preset(table):
        mapping, detected_by, label = preset.mapping, f"preset:{preset.name}", preset.label
    else:
        detection = detect(table, account.kind)
        mapping, detected_by, label, warnings = (
            detection.mapping,
            detection.detected_by,
            detection.label,
            detection.warnings,
        )
    batch = ImportBatch(
        owner_id=owner_id,
        account_id=account.id,
        filename=filename[:200] or "extrato.csv",
        content=data.decode(table.encoding if table.encoding != "utf-8" else "utf-8-sig", errors="replace"),
        detected_by=detected_by,
        layout={**layout, "label": label, "warnings": warnings},
        expires_at=clock.now() + PREVIEW_TTL,
    )
    db.add(batch)
    _fill(db, batch, table, mapping)
    db.commit()
    return batch


def _open_preview(db: Session, owner_id: int, batch_id: int) -> ImportBatch:
    batch = get_batch(db, owner_id, batch_id)
    if batch.status is not BatchStatus.PREVIEW or batch.content is None:
        raise HTTPException(status_code=409, detail="Esta importação já foi concluída.")
    if batch.expires_at is not None and batch.expires_at < clock.now():
        raise HTTPException(status_code=409, detail="Esta prévia expirou. Envie o arquivo de novo.")
    return batch


def _table(batch: ImportBatch) -> Table:
    assert batch.content is not None  # noqa: S101  # checked by _open_preview
    return _read(batch.content.encode())


def remap(db: Session, owner_id: int, batch_id: int, mapping: Mapping) -> ImportBatch:
    batch = _open_preview(db, owner_id, batch_id)
    _fill(db, batch, _table(batch), mapping)
    batch.detected_by = "manual"
    batch.layout = {**batch.layout, "label": "Mapeamento ajustado por você", "warnings": []}
    db.commit()
    return batch


def confirm(db: Session, owner_id: int, batch_id: int, include_lines: set[int]) -> ImportBatch:
    """Writes the new rows, plus the possible duplicates the person chose, in one transaction.

    The status flips from preview to committed in a conditional UPDATE: two clicks (or two tabs) can't
    both import. Duplicates are recomputed now, not trusted from the preview, and ON CONFLICT DO NOTHING
    covers a race with another import of the same lines.
    """
    batch = _open_preview(db, owner_id, batch_id)
    if not batch.mapping:
        raise HTTPException(status_code=422, detail="Indique as colunas antes de importar.")
    claimed = db.execute(
        update(ImportBatch)
        .where(ImportBatch.id == batch.id, ImportBatch.status == BatchStatus.PREVIEW)
        .values(status=BatchStatus.COMMITTED, committed_at=clock.now())
        .returning(ImportBatch.id)
    ).first()
    if claimed is None:
        raise HTTPException(status_code=409, detail="Esta importação já foi concluída.")

    rows = preview.parse_rows(_table(batch), Mapping.model_validate(batch.mapping))
    preview.classify(db, owner_id, batch.account_id, rows)
    chosen = [
        r for r in rows if r.status == "new" or (r.status == "possible_duplicate" and r.line in include_lines)
    ]
    inserted = 0
    if chosen:
        values = [
            {
                "owner_id": owner_id,
                "account_id": batch.account_id,
                "date": date.fromisoformat(r.date or ""),
                "effective_date": date.fromisoformat(r.date or ""),
                "amount_cents": r.amount_cents,
                "description_raw": r.description,
                "merchant": r.merchant[:60],
                "kind": r.kind,
                "category_id": r.category_id,
                "category_source": CategorySource(r.category_source) if r.category_source else None,
                "external_id": r.external_id,
                "fingerprint": r.fingerprint,
                "fp_version": FP_VERSION,
                "occurrence_n": r.occurrence_n,
                "import_batch_id": batch.id,
            }
            for r in chosen
        ]
        result = db.execute(
            insert(Transaction).values(values).on_conflict_do_nothing().returning(Transaction.id)
        )
        inserted = len(result.all())

    counts = preview.summarize(rows)
    batch.summary = {**counts, "inserted": inserted}
    batch.rows = []
    batch.content = None
    _remember_layout(db, owner_id, batch)
    db.commit()
    db.refresh(batch)
    return batch


def _remember_layout(db: Session, owner_id: int, batch: ImportBatch) -> None:
    statement = insert(ImportProfile).values(
        owner_id=owner_id, signature=batch.layout["signature"], mapping=batch.mapping
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[ImportProfile.owner_id, ImportProfile.signature],
            set_={"mapping": statement.excluded.mapping, "updated_at": func.now()},
        )
    )


def undo(db: Session, owner_id: int, batch_id: int, discard_edits: bool) -> ImportBatch:
    batch = get_batch(db, owner_id, batch_id)
    if batch.status is not BatchStatus.COMMITTED:
        raise HTTPException(status_code=409, detail="Só dá para desfazer uma importação concluída.")
    of_batch = Transaction.import_batch_id == batch.id
    edited = db.scalar(select(func.count()).where(of_batch, Transaction.edited_at.is_not(None))) or 0
    if edited and not discard_edits:
        message = f"{edited} lançamento(s) desta importação foram editados por você. Desfazer descarta isso."
        raise HTTPException(status_code=409, detail=message)
    # Removed for good, tombstones included: undoing means the file was never imported.
    db.execute(delete(Transaction).where(of_batch))
    batch.status = BatchStatus.UNDONE
    batch.undone_at = clock.now()
    db.commit()
    return batch


def cancel(db: Session, owner_id: int, batch_id: int) -> None:
    batch = get_batch(db, owner_id, batch_id)
    if batch.status is BatchStatus.PREVIEW:
        db.delete(batch)
        db.commit()


def account_of(db: Session, batch: ImportBatch) -> Account:
    return get_account(db, batch.owner_id, batch.account_id)
