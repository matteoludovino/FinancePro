"""Suggestions from the AI, end to end (docs/adr/0006).

Only what rules and built-in knowledge left uncategorized is asked, one request per 50 distinct merchants,
and every answer is cached for everyone. A suggestion is stored next to the transaction, never as its
category: a person accepts it (optionally turning it into a rule) or rejects it.

Cost has two ceilings, per person and global, kept in a ledger and reserved atomically before each call:
`UPDATE ... WHERE used + n <= cap` in a single statement, so concurrent clicks can't both pass a check
that only one of them fits in.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from financepro import clock
from financepro.ai import privacy
from financepro.ai.classifier import (
    BATCH_SIZE,
    PROMPT_VERSION,
    TAXONOMY_VERSION,
    UNKNOWN,
    AiUnavailableError,
    Classifier,
    Item,
)
from financepro.ai.models import AiSuggestion, AiUsage
from financepro.categories.models import Category
from financepro.categories.service import get_category
from financepro.categorization.models import Kind, MatchType, Rule
from financepro.settings import get_settings
from financepro.text import canonical
from financepro.transactions.models import CategorySource, Transaction

# Reserved before a call and corrected with the real usage after it.
ESTIMATED_TOKENS_PER_BATCH = 6_000


def _candidates(db: Session, owner_id: int, ids: Iterable[int] | None = None) -> list[Transaction]:
    query = select(Transaction).where(
        Transaction.owner_id == owner_id,
        Transaction.deleted_at.is_(None),
        Transaction.kind == Kind.REGULAR,
        Transaction.category_id.is_(None),
        Transaction.ai_category_id.is_(None),
        Transaction.ai_dismissed.is_(False),
    )
    if ids is not None:
        query = query.where(Transaction.id.in_(list(ids)))
    return [t for t in db.scalars(query) if not privacy.about_a_person(t.merchant)]


def _by_merchant(transactions: list[Transaction]) -> dict[str, list[Transaction]]:
    groups: defaultdict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        groups[canonical(transaction.merchant)[:100]].append(transaction)
    return groups


def _cached(db: Session, model: str, keys: Iterable[str]) -> dict[str, AiSuggestion]:
    rows = db.scalars(
        select(AiSuggestion).where(
            AiSuggestion.merchant_key.in_(list(keys)),
            AiSuggestion.taxonomy_version == TAXONOMY_VERSION,
            AiSuggestion.prompt_version == PROMPT_VERSION,
            AiSuggestion.model == model,
        )
    )
    return {row.merchant_key: row for row in rows}


def _apply(
    db: Session, owner_id: int, groups: dict[str, list[Transaction]], answers: dict[str, AiSuggestion]
) -> int:
    slugs = {answer.slug for answer in answers.values() if answer.slug != UNKNOWN}
    # A comprehension, not dict(result): a Result has .keys() (its column names), which dict() would use.
    query = select(Category.slug, Category.id).where(Category.owner_id == owner_id, Category.slug.in_(slugs))
    category_by_slug = {slug: category_id for slug, category_id in db.execute(query)} if slugs else {}  # noqa: C416
    suggested = 0
    for key, answer in answers.items():
        category_id = category_by_slug.get(answer.slug)
        if category_id is None:
            continue
        for transaction in groups.get(key, []):
            transaction.ai_category_id = category_id
            transaction.ai_confidence = answer.confidence
            suggested += 1
    return suggested


def apply_cached(db: Session, owner_id: int, transaction_ids: Iterable[int] | None = None) -> int:
    """Fills suggestions from the shared cache, with no call to the model (used right after an import)."""
    groups = _by_merchant(_candidates(db, owner_id, transaction_ids))
    if not groups:
        return 0
    return _apply(db, owner_id, groups, _cached(db, get_settings().ai_model, groups))


def _reserve(db: Session, scope: str, tokens: int, cap: int) -> bool:
    statement = insert(AiUsage).values(day=clock.today(), scope=scope, tokens=tokens)
    statement = statement.on_conflict_do_update(
        index_elements=[AiUsage.day, AiUsage.scope],
        set_={"tokens": AiUsage.tokens + statement.excluded.tokens},
        where=AiUsage.tokens + statement.excluded.tokens <= cap,
    )
    return tokens <= cap and db.execute(statement.returning(AiUsage.tokens)).first() is not None


def _adjust(db: Session, scopes: list[str], delta: int) -> None:
    for scope in scopes:
        row = db.scalar(select(AiUsage).where(AiUsage.day == clock.today(), AiUsage.scope == scope))
        if row is not None:
            row.tokens = max(0, row.tokens + delta)


def used_today(db: Session, owner_id: int) -> int:
    row = db.scalar(
        select(AiUsage.tokens).where(AiUsage.day == clock.today(), AiUsage.scope == f"user:{owner_id}")
    )
    return int(row or 0)


@dataclass
class Outcome:
    suggested: int = 0
    pending: int = 0
    message: str | None = None
    asked: list[str] = field(default_factory=list)


def suggest(db: Session, owner_id: int, classifier: Classifier | None) -> Outcome:
    """One step: applies everything the cache knows, then asks the model about up to 50 new merchants.
    The browser calls it again while `pending` > 0, so no request runs long."""
    settings = get_settings()
    groups = _by_merchant(_candidates(db, owner_id))
    cached = _cached(db, settings.ai_model, groups)
    outcome = Outcome(suggested=_apply(db, owner_id, groups, cached))
    unknown = [key for key in groups if key not in cached]
    if not unknown:
        db.commit()
        return outcome
    if classifier is None:
        db.commit()
        outcome.pending = len(unknown)
        outcome.message = "A categorização com IA não está ligada neste servidor."
        return outcome

    batch = unknown[:BATCH_SIZE]
    scopes = [f"user:{owner_id}", "global"]
    with db.begin_nested() as reservation:
        fits = _reserve(
            db, scopes[0], ESTIMATED_TOKENS_PER_BATCH, settings.ai_daily_tokens_per_user
        ) and _reserve(db, scopes[1], ESTIMATED_TOKENS_PER_BATCH, settings.ai_daily_tokens_global)
        if not fits:
            reservation.rollback()
    if not fits:
        db.commit()
        outcome.pending = len(unknown)
        outcome.message = "O limite diário de uso da IA foi atingido. Tente de novo amanhã."
        return outcome
    db.commit()  # the reservation is visible to concurrent requests before the slow call starts

    items = []
    for number, key in enumerate(batch, start=1):
        members = groups[key]
        outflow = sum(t.amount_cents for t in members) < 0
        items.append(Item(number, privacy.mask(members[0].merchant), outflow))
    try:
        result = classifier.classify(items)
    except AiUnavailableError:
        _adjust(db, scopes, -ESTIMATED_TOKENS_PER_BATCH)
        db.commit()
        outcome.pending = len(unknown)
        outcome.message = "A IA não respondeu agora. Tente de novo em instantes."
        return outcome

    _adjust(db, scopes, result.tokens - ESTIMATED_TOKENS_PER_BATCH)
    fresh: dict[str, AiSuggestion] = {}
    for number, key in enumerate(batch, start=1):
        answer = result.answers.get(number)
        if answer is None:
            continue  # missing from the answer: stays uncategorized, asked again next time
        db.execute(
            insert(AiSuggestion)
            .values(
                merchant_key=key,
                taxonomy_version=TAXONOMY_VERSION,
                prompt_version=PROMPT_VERSION,
                model=classifier.model,
                slug=answer.slug,
                confidence=answer.confidence,
            )
            .on_conflict_do_nothing()
        )
        fresh[key] = AiSuggestion(merchant_key=key, slug=answer.slug, confidence=answer.confidence)
    outcome.suggested += _apply(db, owner_id, groups, fresh)
    outcome.asked = batch
    outcome.pending = max(0, len(unknown) - len(batch))
    db.commit()
    return outcome


@dataclass(frozen=True)
class Group:
    merchant: str
    category_id: int
    confidence: str
    transactions: list[Transaction]


def suggestions(db: Session, owner_id: int) -> list[Group]:
    rows = db.scalars(
        select(Transaction)
        .where(
            Transaction.owner_id == owner_id,
            Transaction.deleted_at.is_(None),
            Transaction.ai_category_id.is_not(None),
            Transaction.category_id.is_(None),
        )
        .order_by(Transaction.date.desc())
    )
    grouped: defaultdict[tuple[str, int], list[Transaction]] = defaultdict(list)
    for transaction in rows:
        grouped[(transaction.merchant, transaction.ai_category_id or 0)].append(transaction)
    groups = [
        Group(merchant, category_id, members[0].ai_confidence or "low", members)
        for (merchant, category_id), members in grouped.items()
    ]
    return sorted(groups, key=lambda g: (-len(g.transactions), g.merchant))


def _pending_suggestions(db: Session, owner_id: int, ids: list[int]) -> list[Transaction]:
    rows = list(
        db.scalars(
            select(Transaction).where(
                Transaction.id.in_(ids),
                Transaction.owner_id == owner_id,
                Transaction.deleted_at.is_(None),
                Transaction.ai_category_id.is_not(None),
            )
        )
    )
    if len(rows) != len(set(ids)):
        raise HTTPException(status_code=404, detail="Alguma das sugestões não foi encontrada.")
    return rows


def accept(db: Session, owner_id: int, ids: list[int], category_id: int | None, create_rule: bool) -> int:
    """Accepts the suggestion, or the category the person picked instead. With `create_rule`, the merchant
    becomes a rule: next month's statement is categorized before the AI is ever asked."""
    rows = _pending_suggestions(db, owner_id, ids)
    if category_id is not None:
        get_category(db, owner_id, category_id)
    now = clock.now()
    for transaction in rows:
        chosen = category_id or transaction.ai_category_id
        transaction.category_source = (
            CategorySource.AI if chosen == transaction.ai_category_id else CategorySource.USER
        )
        transaction.category_id = chosen
        transaction.ai_category_id = None
        transaction.edited_at = now
    if create_rule:
        for merchant, chosen in {(t.merchant, t.category_id) for t in rows}:
            pattern = canonical(merchant)
            exists = db.scalar(
                select(func.count()).where(
                    Rule.owner_id == owner_id, Rule.match_type == MatchType.MERCHANT, Rule.pattern == pattern
                )
            )
            if not exists:
                db.add(
                    Rule(
                        owner_id=owner_id, match_type=MatchType.MERCHANT, pattern=pattern, category_id=chosen
                    )
                )
    db.commit()
    return len(rows)


def reject(db: Session, owner_id: int, ids: list[int]) -> int:
    rows = _pending_suggestions(db, owner_id, ids)
    for transaction in rows:
        transaction.ai_category_id = None
        transaction.ai_confidence = None
        transaction.ai_dismissed = True
    db.commit()
    return len(rows)
