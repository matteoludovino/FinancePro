import datetime as dt

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from financepro.db import Base


class InstallmentGroup(Base):
    """One purchase paid in installments ("Magalu - Parcela 3/10" and its siblings across statements).

    It holds only the identity of the purchase. Progress and the installments still to come are derived
    from its member transactions at query time, so importing, deleting or undoing never leaves a stored
    counter out of date.
    """

    __tablename__ = "installment_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    merchant: Mapped[str] = mapped_column(String(60))
    # Canonical merchant without the "k/N" counter: what siblings are matched by.
    merchant_key: Mapped[str] = mapped_column(String(100))
    installments: Mapped[int] = mapped_column(SmallInteger)
    # The month of installment 1, implied from any member: effective date minus (k - 1) months.
    first_month: Mapped[dt.date] = mapped_column(Date)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
