"""A visitor's own copy of the demo (docs/adr/0007).

Built through the real import pipeline from the same generator the tests use, so the demo exercises what
a person would: presets, deduplication, installments, bill payments linked as transfers and cached AI
answers. Dates are relative to today, so the current month is never empty. The checking account stops
two weeks ago: importing the "more recent statement" sample shows deduplication adding only what's new.
"""

import secrets
import threading
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from financepro import clock
from financepro.accounts.models import Account, AccountKind
from financepro.ai.classifier import PROMPT_VERSION, TAXONOMY_VERSION
from financepro.ai.models import AiSuggestion
from financepro.auth.limits import SlidingWindow
from financepro.auth.models import Session as SessionRow
from financepro.auth.models import User
from financepro.budgets.models import Budget
from financepro.categories import defaults
from financepro.categories.models import Category
from financepro.demo import generator
from financepro.importers import service as imports
from financepro.settings import get_settings

IDLE_TTL = timedelta(hours=3)

# What the model answered for the generator's unknown merchants, so the demo shows suggestions with no
# live call (and no key needed to see them).
KNOWN_ANSWERS = {
    "livraria cultura": ("cursos", "high"),
    "clinica sorriso": ("consultas-exames", "medium"),
    "pet feliz": ("pets", "high"),
    "acougue bom corte": ("mercado", "high"),
    "samsung store": ("eletronicos", "high"),
}
BUDGETS = {"alimentacao": 150_000, "delivery": 45_000, "transporte": 60_000, "lazer": 30_000}

_creations = SlidingWindow(limit=30, seconds=60)
_lock = threading.Lock()


def warm_ai_cache(db: Session) -> None:
    model = get_settings().ai_model
    db.execute(
        insert(AiSuggestion)
        .values(
            [
                {
                    "merchant_key": key,
                    "taxonomy_version": TAXONOMY_VERSION,
                    "prompt_version": PROMPT_VERSION,
                    "model": model,
                    "slug": slug,
                    "confidence": confidence,
                }
                for key, (slug, confidence) in KNOWN_ANSWERS.items()
            ]
        )
        .on_conflict_do_nothing()
    )


def cleanup(db: Session) -> int:
    """Deletes sandboxes nobody used for IDLE_TTL: no session alive. Cascades to everything they hold."""
    alive = exists().where(SessionRow.user_id == User.id, SessionRow.expires_at > clock.now())
    result = db.execute(
        delete(User).where(User.is_sandbox.is_(True), User.created_at < clock.now() - IDLE_TTL, ~alive)
    )
    db.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def _active(db: Session) -> int:
    alive = exists().where(SessionRow.user_id == User.id, SessionRow.expires_at > clock.now())
    return int(db.scalar(select(func.count()).where(User.is_sandbox.is_(True), alive)) or 0)


def create(db: Session) -> User:
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Não encontrado.")
    with _lock:
        if _creations.blocked("all"):
            raise HTTPException(
                status_code=429, detail="Muita gente entrando agora. Tente de novo em um minuto."
            )
        _creations.hit("all")
    cleanup(db)
    if _active(db) >= settings.demo_max_sandboxes:
        raise HTTPException(
            status_code=503, detail="A demonstração está cheia agora. Tente de novo mais tarde."
        )

    user = User(name="Visitante", email=f"demo-{secrets.token_hex(8)}@demo.financepro", is_sandbox=True)
    db.add(user)
    db.flush()
    defaults.seed(db, user.id)
    warm_ai_cache(db)
    checking = Account(
        owner_id=user.id, name="Nubank", kind=AccountKind.CHECKING, institution="Nu Pagamentos"
    )
    card = Account(
        owner_id=user.id, name="Cartão Nubank", kind=AccountKind.CREDIT_CARD, closing_day=3, due_day=10
    )
    db.add_all([checking, card])
    db.flush()

    today = clock.today()
    card_lines, bills = generator.card(today)
    checking_lines = [
        line
        for line in generator.checking(today, card_bills=bills)
        if line.date <= today - timedelta(days=15)
    ]
    for account, content, name in (
        (card, generator.nubank_card_csv(card_lines), "nubank-cartao.csv"),
        (checking, generator.nubank_checking_csv(checking_lines), "nubank-conta.csv"),
    ):
        batch = imports.create_preview(db, user.id, account.id, name, content.encode())
        imports.confirm(db, user.id, batch.id, set())

    month = today.replace(day=1)
    slugs = dict(db.execute(select(Category.slug, Category.id).where(Category.owner_id == user.id)).all())
    db.add_all(
        Budget(owner_id=user.id, category_id=slugs[slug], starts_month=month, limit_cents=limit)
        for slug, limit in BUDGETS.items()
    )
    db.commit()
    return user
