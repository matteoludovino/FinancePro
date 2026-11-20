"""Deciding what a transaction is: the person's rules first, then built-in merchant knowledge.

The AI (stage 6) only sees what neither of these decided.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from financepro.categories.models import Category
from financepro.categorization.models import Kind, MatchType, Rule
from financepro.categorization.normalizer import merchant_of
from financepro.text import canonical

Source = Literal["rule", "merchant"]

_MATCH_RANK = {MatchType.MERCHANT: 2, MatchType.STARTS_WITH: 1, MatchType.CONTAINS: 0}


@dataclass(frozen=True)
class Decision:
    merchant: str
    kind: Kind
    category_id: int | None
    source: Source | None
    rule_id: int | None = None


def specificity(rule: Rule) -> tuple[int, int, int, int, int]:
    """Higher is more specific. A rule narrowed to one account beats one that isn't, an amount range beats
    none, an exact merchant beats "starts with", which beats "contains"; then the longer pattern; then the
    newer rule. So "Uber, R$ 30 or less → Transport" wins over "uber → Work trips" without any ordering UI.
    """
    narrowing = (rule.min_cents is not None) + (rule.max_cents is not None)
    return (rule.account_id is not None, narrowing, _MATCH_RANK[rule.match_type], len(rule.pattern), rule.id)


def _matches(rule: Rule, text: str, merchant: str, amount_cents: int, account_id: int | None) -> bool:
    if rule.account_id is not None and rule.account_id != account_id:
        return False
    if rule.min_cents is not None and abs(amount_cents) < rule.min_cents:
        return False
    if rule.max_cents is not None and abs(amount_cents) > rule.max_cents:
        return False
    if rule.match_type is MatchType.MERCHANT:
        return merchant == rule.pattern
    if rule.match_type is MatchType.STARTS_WITH:
        return text.startswith(rule.pattern)
    return rule.pattern in text


class Categorizer:
    def __init__(self, rules: Iterable[Rule], category_by_slug: dict[str, int]) -> None:
        self.rules = sorted(rules, key=specificity, reverse=True)
        self.category_by_slug = category_by_slug

    @classmethod
    def for_owner(cls, db: Session, owner_id: int) -> Categorizer:
        rules = db.scalars(select(Rule).where(Rule.owner_id == owner_id))
        slugs = db.execute(
            select(Category.slug, Category.id).where(
                Category.owner_id == owner_id, Category.slug.is_not(None)
            )
        )
        return cls(rules, {slug: category_id for slug, category_id in slugs if slug})

    def decide(self, description: str, amount_cents: int, account_id: int | None = None) -> Decision:
        merchant = merchant_of(description)
        text, merchant_text = canonical(description), canonical(merchant.name)
        for rule in self.rules:
            if _matches(rule, text, merchant_text, amount_cents, account_id):
                return Decision(merchant.name, rule.sets_kind, rule.category_id, "rule", rule.id)
        if merchant.slug and (category_id := self.category_by_slug.get(merchant.slug)) is not None:
            return Decision(merchant.name, Kind.REGULAR, category_id, "merchant")
        return Decision(merchant.name, Kind.REGULAR, None, None)
