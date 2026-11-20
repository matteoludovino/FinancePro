from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from financepro.accounts.service import get_account
from financepro.categories.service import get_category
from financepro.categorization.models import MatchType, Rule
from financepro.categorization.schemas import RuleIn
from financepro.text import canonical


def list_rules(db: Session, owner_id: int) -> list[Rule]:
    return list(db.scalars(select(Rule).where(Rule.owner_id == owner_id).order_by(Rule.id)))


def get_rule(db: Session, owner_id: int, rule_id: int) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.id == rule_id, Rule.owner_id == owner_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    return rule


def _apply(db: Session, owner_id: int, rule: Rule, data: RuleIn) -> Rule:
    # References must be the person's own: a foreign id is reported as missing, never linked.
    if data.category_id is not None:
        get_category(db, owner_id, data.category_id)
    if data.account_id is not None:
        get_account(db, owner_id, data.account_id)
    pattern = canonical(data.pattern)
    duplicate = db.scalar(
        select(Rule.id).where(
            Rule.owner_id == owner_id,
            Rule.id != (rule.id or 0),
            Rule.match_type == data.match_type,
            Rule.pattern == pattern,
            Rule.account_id.is_(None) if data.account_id is None else Rule.account_id == data.account_id,
            Rule.min_cents.is_(None) if data.min_cents is None else Rule.min_cents == data.min_cents,
            Rule.max_cents.is_(None) if data.max_cents is None else Rule.max_cents == data.max_cents,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Já existe uma regra com estas mesmas condições.")
    rule.match_type = MatchType(data.match_type)
    rule.pattern = pattern
    rule.sets_kind = data.sets_kind
    rule.category_id = data.category_id
    rule.account_id = data.account_id
    rule.min_cents = data.min_cents
    rule.max_cents = data.max_cents
    db.add(rule)
    db.commit()
    return rule


def create_rule(db: Session, owner_id: int, data: RuleIn) -> Rule:
    return _apply(db, owner_id, Rule(owner_id=owner_id), data)


def update_rule(db: Session, owner_id: int, rule_id: int, data: RuleIn) -> Rule:
    return _apply(db, owner_id, get_rule(db, owner_id, rule_id), data)


def delete_rule(db: Session, owner_id: int, rule_id: int) -> None:
    db.delete(get_rule(db, owner_id, rule_id))
    db.commit()
