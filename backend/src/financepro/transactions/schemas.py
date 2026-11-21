import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from financepro.categorization.models import Kind
from financepro.transactions.models import CategorySource


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    date: dt.date
    effective_date: dt.date
    amount_cents: int
    description_raw: str
    merchant: str
    kind: Kind
    category_id: int | None
    category_source: CategorySource | None
    notes: str
    edited_at: dt.datetime | None


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


class TransactionPatch(BaseModel):
    """Only the fields sent change. `category_id: null` clears the category."""

    category_id: int | None = None
    kind: Kind | None = None
    notes: Annotated[str, StringConstraints(max_length=500)] | None = None


class BulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["categorize", "transfer", "ignore", "regular", "delete"]
    category_id: int | None = None


class BulkOut(BaseModel):
    updated: int


class ApplyOut(BaseModel):
    updated: int
