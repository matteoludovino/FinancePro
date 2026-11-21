import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from financepro.categorization.models import Kind
from financepro.common.enums import db_enum
from financepro.db import Base


class CategorySource(StrEnum):
    RULE = "rule"
    MERCHANT = "merchant"
    AI = "ai"
    USER = "user"


class Transaction(Base):
    """One line of a statement. Amounts are signed integer cents: negative leaves the account."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    # The date the bank printed, and the date the transaction counts in reports and budgets (they differ
    # for card installments; see ADR 0004).
    date: Mapped[dt.date] = mapped_column(Date)
    effective_date: Mapped[dt.date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    description_raw: Mapped[str] = mapped_column(String(300))
    merchant: Mapped[str] = mapped_column(String(60))
    kind: Mapped[Kind] = mapped_column(db_enum(Kind, "transaction_kind"), default=Kind.REGULAR)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category_source: Mapped[CategorySource | None] = mapped_column(db_enum(CategorySource, "category_source"))
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    # Deduplication (ADR 0003). The bank's own id when the file has one, and always a fingerprint of the
    # content: a pure function of stored columns, so a new fingerprint version is a backfill, not a guess.
    external_id: Mapped[str | None] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    fp_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    occurrence_n: Mapped[int] = mapped_column(SmallInteger, default=0)

    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id", ondelete="SET NULL"))
    # The other side of a transfer between the person's accounts (a bill payment: checking ↔ card).
    transfer_pair_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    # A person said a suggested pair isn't a transfer: never suggest this transaction again.
    not_a_transfer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # "Parcela 3/10": the purchase it belongs to, and which installment of how many.
    installment_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("installment_groups.id", ondelete="SET NULL")
    )
    installment_k: Mapped[int | None] = mapped_column(SmallInteger)
    installment_n: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set when a person changes the transaction; undoing its import then asks before discarding that work.
    edited_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Deleted rows stay as tombstones: their fingerprint keeps a re-import from bringing them back.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_transactions_account_fingerprint", account_id, fingerprint, unique=True),
        Index(
            "uq_transactions_account_external_id",
            account_id,
            external_id,
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_transactions_owner_effective_date", owner_id, effective_date),
        Index("ix_transactions_account_date", account_id, date),
        Index("ix_transactions_import_batch_id", import_batch_id),
        CheckConstraint("kind = 'regular' OR category_id IS NULL", name="only_regular_has_category"),
        CheckConstraint("amount_cents <> 0", name="amount_not_zero"),
        CheckConstraint(
            "(installment_k IS NULL) = (installment_n IS NULL) AND (installment_k IS NULL OR "
            "installment_k BETWEEN 1 AND installment_n)",
            name="installment_numbers",
        ),
        Index("ix_transactions_installment_group_id", "installment_group_id"),
    )
