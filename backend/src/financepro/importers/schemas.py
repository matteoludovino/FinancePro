from datetime import datetime
from typing import Any

from pydantic import BaseModel

from financepro.importers.mapping import Mapping
from financepro.importers.models import BatchStatus, ImportBatch


class PreviewRow(BaseModel):
    line: int
    status: str
    description: str
    date: str | None
    effective_date: str | None = None
    installment_k: int | None = None
    installment_n: int | None = None
    amount_cents: int | None
    external_id: str | None
    message: str | None
    match: dict[str, Any] | None
    merchant: str
    kind: str
    category_id: int | None
    category_source: str | None


class BatchOut(BaseModel):
    id: int
    account_id: int
    status: BatchStatus
    filename: str
    detected_by: str
    label: str
    warnings: list[str]
    header: list[str]
    sample: list[list[str]]
    mapping: Mapping | None
    summary: dict[str, int]
    rows: list[PreviewRow]
    created_at: datetime
    expires_at: datetime | None
    committed_at: datetime | None
    undone_at: datetime | None

    @classmethod
    def of(cls, batch: ImportBatch, with_rows: bool = True) -> BatchOut:
        layout = batch.layout
        return cls(
            id=batch.id,
            account_id=batch.account_id,
            status=batch.status,
            filename=batch.filename,
            detected_by=batch.detected_by,
            label=layout.get("label", ""),
            warnings=layout.get("warnings", []),
            header=layout.get("header", []),
            sample=layout.get("sample", []),
            mapping=Mapping.model_validate(batch.mapping) if batch.mapping else None,
            summary=batch.summary,
            rows=[PreviewRow.model_validate(row) for row in batch.rows] if with_rows else [],
            created_at=batch.created_at,
            expires_at=batch.expires_at,
            committed_at=batch.committed_at,
            undone_at=batch.undone_at,
        )


class ConfirmIn(BaseModel):
    # Lines flagged as possible duplicates that the person chose to import anyway.
    include_lines: list[int] = []


class UndoIn(BaseModel):
    discard_edits: bool = False
