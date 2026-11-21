from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from financepro.ai import service
from financepro.ai.classifier import AnthropicClassifier, Classifier
from financepro.auth.sessions import CurrentUser
from financepro.db import get_db
from financepro.settings import get_settings

router = APIRouter(prefix="/ai", tags=["ai"])

DB = Annotated[Session, Depends(get_db)]


def get_classifier() -> Classifier | None:
    """The model client, or None when no key is configured (the AI is then off). Tests override this."""
    settings = get_settings()
    if settings.anthropic_api_key is None:
        return None
    return AnthropicClassifier(settings.anthropic_api_key.get_secret_value(), settings.ai_model)


ClassifierDep = Annotated[Classifier | None, Depends(get_classifier)]


class StatusOut(BaseModel):
    enabled: bool
    used_today: int
    daily_limit: int


class SuggestOut(BaseModel):
    suggested: int
    pending: int
    message: str | None


class GroupOut(BaseModel):
    merchant: str
    category_id: int
    confidence: str
    transaction_ids: list[int]
    total_cents: int
    example: str


class DecisionIn(BaseModel):
    transaction_ids: list[int] = Field(min_length=1, max_length=500)
    # Accept with another category than the one suggested.
    category_id: int | None = None
    create_rule: bool = False


class CountOut(BaseModel):
    updated: int


@router.get("/status")
def status(user: CurrentUser, db: DB, classifier: ClassifierDep) -> StatusOut:
    return StatusOut(
        enabled=classifier is not None,
        used_today=service.used_today(db, user.id),
        daily_limit=get_settings().ai_daily_tokens_per_user,
    )


@router.post("/suggest")
def suggest(user: CurrentUser, db: DB, classifier: ClassifierDep) -> SuggestOut:
    outcome = service.suggest(db, user.id, classifier)
    return SuggestOut(suggested=outcome.suggested, pending=outcome.pending, message=outcome.message)


@router.get("/suggestions")
def suggestions(user: CurrentUser, db: DB) -> list[GroupOut]:
    return [
        GroupOut(
            merchant=group.merchant,
            category_id=group.category_id,
            confidence=group.confidence,
            transaction_ids=[t.id for t in group.transactions],
            total_cents=sum(t.amount_cents for t in group.transactions),
            example=group.transactions[0].description_raw,
        )
        for group in service.suggestions(db, user.id)
    ]


@router.post("/suggestions/accept")
def accept(body: DecisionIn, user: CurrentUser, db: DB) -> CountOut:
    return CountOut(
        updated=service.accept(db, user.id, body.transaction_ids, body.category_id, body.create_rule)
    )


@router.post("/suggestions/reject")
def reject(body: DecisionIn, user: CurrentUser, db: DB) -> CountOut:
    return CountOut(updated=service.reject(db, user.id, body.transaction_ids))
