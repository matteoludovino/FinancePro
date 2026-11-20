from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from financepro.db import Base


class AccountKind(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    WALLET = "wallet"
    # A liability: purchases make its balance more negative, paying the bill is a transfer into it.
    CREDIT_CARD = "credit_card"
    # Money that leaves the tracked accounts without being spent: savings boxes, investments, Pix to an
    # own account at a bank that isn't imported. One side of a transfer, never spending.
    EXTERNAL = "external"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[AccountKind] = mapped_column(
        Enum(
            AccountKind,
            native_enum=False,
            create_constraint=True,
            length=20,
            name="account_kind",
            values_callable=lambda kinds: [k.value for k in kinds],
        )
    )
    institution: Mapped[str] = mapped_column(String(60), default="", server_default="")
    # Credit cards only: the statement closes and is due on these days of the month.
    closing_day: Mapped[int | None] = mapped_column(SmallInteger)
    due_day: Mapped[int | None] = mapped_column(SmallInteger)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("uq_accounts_owner_name", owner_id, func.lower(name), unique=True),
        CheckConstraint(
            "(kind = 'credit_card') = (closing_day IS NOT NULL AND due_day IS NOT NULL)",
            name="card_days_only_on_cards",
        ),
        CheckConstraint("closing_day BETWEEN 1 AND 31 AND due_day BETWEEN 1 AND 31", name="valid_days"),
    )
