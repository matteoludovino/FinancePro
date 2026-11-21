"""Every ORM model, imported here so Alembic and the tests see the full schema."""

from financepro.accounts.models import Account, AccountKind
from financepro.ai.models import AiSuggestion, AiUsage
from financepro.auth.models import Session, User
from financepro.budgets.models import Budget
from financepro.cards.models import InstallmentGroup
from financepro.categories.models import Category
from financepro.categorization.models import Rule
from financepro.importers.models import ImportBatch, ImportProfile
from financepro.transactions.models import Transaction

__all__ = [
    "Account",
    "AccountKind",
    "AiSuggestion",
    "AiUsage",
    "Budget",
    "Category",
    "ImportBatch",
    "ImportProfile",
    "InstallmentGroup",
    "Rule",
    "Session",
    "Transaction",
    "User",
]
