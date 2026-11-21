from fastapi import FastAPI

from financepro.accounts import routes as accounts
from financepro.ai import routes as ai
from financepro.api import health
from financepro.auth import routes as auth
from financepro.budgets import routes as budgets
from financepro.cards import routes as cards
from financepro.categories import routes as categories
from financepro.categorization import routes as rules
from financepro.common import errors, origin
from financepro.demo import routes as samples
from financepro.importers import routes as imports
from financepro.reports import routes as reports
from financepro.settings import get_settings
from financepro.transactions import routes as transactions
from financepro.transfers import routes as transfers

ROUTERS = (
    health,
    auth,
    accounts,
    categories,
    rules,
    imports,
    transactions,
    transfers,
    cards,
    ai,
    budgets,
    reports,
    samples,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FinancePro API",
        version="0.1.0",
        # Interactive docs only outside production: the API is private to the web app.
        docs_url=None if settings.production else "/api/docs",
        openapi_url=None if settings.production else "/api/openapi.json",
        redoc_url=None,
    )
    errors.install(app)
    origin.install(app)
    for module in ROUTERS:
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
