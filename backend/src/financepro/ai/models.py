import datetime as dt

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from financepro.db import Base


class AiSuggestion(Base):
    """What the model answered for a merchant, shared by everyone: "Padaria Real" is a bakery for any
    person. Keyed by everything that could change the answer, so a new taxonomy, prompt or model starts a
    fresh cache instead of serving stale answers. Only the canonical merchant is stored, never a person's
    description or amount."""

    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    merchant_key: Mapped[str] = mapped_column(String(100))
    taxonomy_version: Mapped[int] = mapped_column(Integer)
    prompt_version: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(60))
    slug: Mapped[str] = mapped_column(String(40))  # a taxonomy slug or "unknown"
    confidence: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("uq_ai_suggestions_key", merchant_key, taxonomy_version, prompt_version, model, unique=True),
    )


class AiUsage(Base):
    """Tokens spent per day, per person and in total ("global"); caps are enforced atomically on it."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date)
    scope: Mapped[str] = mapped_column(String(30))  # "global" or "user:<id>"
    tokens: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (Index("uq_ai_usage_day_scope", day, scope, unique=True),)
