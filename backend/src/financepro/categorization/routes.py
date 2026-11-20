from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from financepro.accounts.service import get_account
from financepro.auth.sessions import CurrentUser
from financepro.categorization import service
from financepro.categorization.engine import Categorizer
from financepro.categorization.schemas import PreviewIn, PreviewOut, RuleIn, RuleOut
from financepro.db import get_db

router = APIRouter(prefix="/rules", tags=["rules"])

DB = Annotated[Session, Depends(get_db)]


@router.get("")
def list_rules(user: CurrentUser, db: DB) -> list[RuleOut]:
    return [RuleOut.model_validate(r) for r in service.list_rules(db, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rule(body: RuleIn, user: CurrentUser, db: DB) -> RuleOut:
    return RuleOut.model_validate(service.create_rule(db, user.id, body))


@router.put("/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, user: CurrentUser, db: DB) -> RuleOut:
    return RuleOut.model_validate(service.update_rule(db, user.id, rule_id, body))


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, user: CurrentUser, db: DB) -> None:
    service.delete_rule(db, user.id, rule_id)


@router.post("/preview")
def preview(body: PreviewIn, user: CurrentUser, db: DB) -> PreviewOut:
    """What the rules would decide for a description: the "test a description" box on the rules page."""
    if body.account_id is not None:
        get_account(db, user.id, body.account_id)
    decision = Categorizer.for_owner(db, user.id).decide(body.description, body.amount_cents, body.account_id)
    return PreviewOut(
        merchant=decision.merchant,
        kind=decision.kind,
        category_id=decision.category_id,
        source=decision.source,
        rule_id=decision.rule_id,
    )
