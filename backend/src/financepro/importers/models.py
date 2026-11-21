from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from financepro.common.enums import db_enum
from financepro.db import Base


class BatchStatus(StrEnum):
    PREVIEW = "preview"
    COMMITTED = "committed"
    UNDONE = "undone"


class ImportBatch(Base):
    """One uploaded file. In `preview` nothing is written yet; confirming inserts every row in one go."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    status: Mapped[BatchStatus] = mapped_column(
        db_enum(BatchStatus, "batch_status"), default=BatchStatus.PREVIEW
    )
    filename: Mapped[str] = mapped_column(String(200))
    # The decoded file, kept while in preview so a changed column mapping can re-read it; cleared after.
    content: Mapped[str | None] = mapped_column(Text)
    mapping: Mapped[dict[str, Any]] = mapped_column(JSONB)
    detected_by: Mapped[str] = mapped_column(String(40))
    # Header, a few sample rows, delimiter and encoding: what the mapping editor shows.
    layout: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Parsed rows with their status, while in preview; emptied once committed (the summary stays).
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Counts by status, and after commit how many were inserted.
    summary: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportProfile(Base):
    """The column mapping that worked for a file layout, keyed by its header: the next file from the same
    bank imports with no questions, whichever account it goes to."""

    __tablename__ = "import_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    signature: Mapped[str] = mapped_column(String(64))
    mapping: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("uq_import_profiles_owner_signature", owner_id, signature, unique=True),)
