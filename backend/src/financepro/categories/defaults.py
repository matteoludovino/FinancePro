"""What a new person starts with: the taxonomy as categories, and rules for lines that aren't spending."""

from sqlalchemy.orm import Session

from financepro.categories.models import Category
from financepro.categories.taxonomy import EXPENSES, INCOME, CategoryType
from financepro.categorization.models import Kind, MatchType, Rule
from financepro.text import canonical

# Lines that move money between the person's own pockets. Without these, a bill payment or money put into
# a savings box ("Caixinha", shown as RDB on Nubank statements) would look like enormous spending.
DEFAULT_RULES: tuple[tuple[MatchType, str, Kind], ...] = (
    # Every wording the normalizer reads as a bill payment ("Pagamento efetuado", "Pagamento recebido"...).
    (MatchType.MERCHANT, "pagamento de fatura", Kind.TRANSFER),
    (MatchType.CONTAINS, "pagamento de fatura", Kind.TRANSFER),
    (MatchType.CONTAINS, "pagamento da fatura", Kind.TRANSFER),
    (MatchType.STARTS_WITH, "pagamento recebido", Kind.TRANSFER),
    (MatchType.STARTS_WITH, "aplicacao rdb", Kind.TRANSFER),
    (MatchType.STARTS_WITH, "resgate rdb", Kind.TRANSFER),
    (MatchType.CONTAINS, "saldo anterior", Kind.IGNORED),
)


def seed(db: Session, owner_id: int) -> None:
    for kind, roots in ((CategoryType.EXPENSE, EXPENSES), (CategoryType.INCOME, INCOME)):
        for root in roots:
            parent = Category(owner_id=owner_id, name=root.name, type=kind, slug=root.slug)
            db.add(parent)
            db.flush()
            db.add_all(
                Category(owner_id=owner_id, parent_id=parent.id, name=child.name, type=kind, slug=child.slug)
                for child in root.children
            )
    db.add_all(
        Rule(owner_id=owner_id, match_type=match, pattern=canonical(pattern), sets_kind=kind, is_default=True)
        for match, pattern, kind in DEFAULT_RULES
    )
    db.flush()
