from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from financepro.categorization.engine import Source
from financepro.categorization.models import Kind, MatchType

Pattern = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Cents = Annotated[int, Field(ge=0, le=10**12)]


class RuleIn(BaseModel):
    match_type: MatchType
    pattern: Pattern
    sets_kind: Kind = Kind.REGULAR
    category_id: int | None = None
    account_id: int | None = None
    min_cents: Cents | None = None
    max_cents: Cents | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.sets_kind is Kind.REGULAR and self.category_id is None:
            raise ValueError("Escolha a categoria.")
        if self.sets_kind is not Kind.REGULAR:
            self.category_id = None
        if self.min_cents is not None and self.max_cents is not None and self.min_cents > self.max_cents:
            raise ValueError("O valor mínimo é maior que o máximo.")
        return self


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_type: MatchType
    pattern: str
    sets_kind: Kind
    category_id: int | None
    account_id: int | None
    min_cents: int | None
    max_cents: int | None
    is_default: bool


class PreviewIn(BaseModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    amount_cents: int = -1
    account_id: int | None = None


class PreviewOut(BaseModel):
    merchant: str
    kind: Kind
    category_id: int | None
    source: Source | None
    rule_id: int | None
