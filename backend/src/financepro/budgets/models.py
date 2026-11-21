import datetime as dt

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from financepro.db import Base


class Budget(Base):
    """A monthly limit for a category, from a month on. Changing it adds a row from the new month: the
    months before keep the limit they had, so last March is judged by last March's budget. A NULL limit
    from a month on means "no budget anymore"."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    starts_month: Mapped[dt.date] = mapped_column(Date)  # always the first day of a month
    limit_cents: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("uq_budgets_owner_category_month", owner_id, category_id, starts_month, unique=True),
        CheckConstraint("limit_cents IS NULL OR limit_cents > 0", name="positive_limit"),
        CheckConstraint("extract(day from starts_month) = 1", name="starts_on_the_first"),
    )
