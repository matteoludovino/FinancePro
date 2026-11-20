from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from financepro.db import Base


class MatchType(StrEnum):
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    # Equal to the normalized merchant ("Uber"), whatever the bank wrote around it.
    MERCHANT = "merchant"


class Kind(StrEnum):
    """What a transaction is, apart from its category. Only `regular` ones are income or spending."""

    REGULAR = "regular"
    # Money moving between the person's own accounts, a card bill payment included: never spending.
    TRANSFER = "transfer"
    # Lines that aren't money moving at all, such as a statement's carried-over balance.
    IGNORED = "ignored"


def _enum[E: StrEnum](enum: type[E], name: str) -> Enum:
    return Enum(
        enum,
        native_enum=False,
        create_constraint=True,
        length=20,
        name=name,
        values_callable=lambda members: [m.value for m in members],
    )


class Rule(Base):
    """ "When the description contains 'uber', it's Transport". The most specific matching rule wins."""

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_type: Mapped[MatchType] = mapped_column(_enum(MatchType, "rule_match_type"))
    # Stored in canonical form (lowercase, no accents), the form descriptions are compared in.
    pattern: Mapped[str] = mapped_column(String(100))
    # Either a category (for regular transactions) or a kind that has none (transfer, ignored).
    sets_kind: Mapped[Kind] = mapped_column(_enum(Kind, "rule_sets_kind"), default=Kind.REGULAR)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    # Optional narrowing: only this account, only amounts in this range (absolute value, in cents).
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    min_cents: Mapped[int | None] = mapped_column(BigInteger)
    max_cents: Mapped[int | None] = mapped_column(BigInteger)
    # Created with the account (Caixinha transfers, IOF...); shown as "padrão", editable like any other.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "(sets_kind = 'regular') = (category_id IS NOT NULL)", name="category_only_when_regular"
        ),
        CheckConstraint(
            "min_cents IS NULL OR max_cents IS NULL OR min_cents <= max_cents", name="amount_range"
        ),
        CheckConstraint("min_cents IS NULL OR min_cents >= 0", name="min_not_negative"),
        CheckConstraint("length(pattern) > 0", name="pattern_not_empty"),
    )
