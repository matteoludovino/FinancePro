from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from financepro.accounts.models import AccountKind

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Institution = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Day = Annotated[int, Field(ge=1, le=31)]


class AccountIn(BaseModel):
    name: Name
    kind: AccountKind
    institution: Institution = ""
    closing_day: Day | None = None
    due_day: Day | None = None

    @model_validator(mode="after")
    def card_days(self) -> Self:
        if self.kind is AccountKind.CREDIT_CARD:
            if self.closing_day is None or self.due_day is None:
                raise ValueError("Informe o dia de fechamento e o de vencimento da fatura.")
        else:
            self.closing_day = self.due_day = None
        return self


class AccountPatch(BaseModel):
    name: Name | None = None
    institution: Institution | None = None
    closing_day: Day | None = None
    due_day: Day | None = None
    is_archived: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: AccountKind
    institution: str
    closing_day: int | None
    due_day: int | None
    is_archived: bool
