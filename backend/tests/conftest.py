"""Tests run against a real PostgreSQL: constraints, partial indexes and ON CONFLICT don't exist in a mock.

The test database is the configured one with a `_test` suffix. It is migrated once per session, and each
test runs inside a transaction that is rolled back, so tests never see each other's rows.
"""

import os
from collections.abc import Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

from financepro.settings import Settings, get_settings

_configured = make_url(Settings().sqlalchemy_url)
_name = _configured.database or "financepro"
TEST_URL = _configured.set(database=_name if _name.endswith("_test") else f"{_name}_test")
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)
os.environ["ENVIRONMENT"] = "test"
get_settings.cache_clear()

from financepro.ai.classifier import Classifier  # noqa: E402  # after the environment points at the test database
from financepro.ai.routes import get_classifier  # noqa: E402
from financepro.auth import limits  # noqa: E402
from financepro.db import get_db, get_engine  # noqa: E402
from financepro.main import create_app  # noqa: E402

PASSWORD = "senha-forte-de-teste"


def _create_database() -> None:
    admin = create_engine(TEST_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        query = text("SELECT 1 FROM pg_database WHERE datname = :name")
        exists = conn.scalar(query, {"name": TEST_URL.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_URL.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    _create_database()
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        command.upgrade(config, "head")


@pytest.fixture
def db() -> Iterator[Session]:
    connection = get_engine().connect()
    outer = connection.begin()
    # Code under test may commit: with savepoints, its commits stay inside the outer transaction.
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _fresh_limits() -> None:
    limits.failed_by_email.clear()
    limits.all_attempts.clear()


class AiSwitch:
    """The model client the app sees: None (no key, AI off) unless a test plugs in a fake."""

    classifier: Classifier | None = None


@pytest.fixture
def ai() -> AiSwitch:
    return AiSwitch()


@pytest.fixture
def make_client(db: Session, ai: AiSwitch) -> Iterator[Callable[[], TestClient]]:
    """Each client is a separate browser (its own cookies), all sharing the test's transaction."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_classifier] = lambda: ai.classifier
    clients: list[TestClient] = []

    def make() -> TestClient:
        # Browsers send Origin on every POST/PATCH/DELETE; these clients behave like the web app's pages.
        test_client = TestClient(app, headers={"origin": get_settings().web_origin})
        clients.append(test_client)
        return test_client

    yield make
    for test_client in clients:
        test_client.close()


@pytest.fixture
def client(make_client: Callable[[], TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def signed_in(make_client: Callable[[], TestClient]) -> Callable[..., TestClient]:
    """A new browser, signed in as a new user."""
    counter = iter(range(1, 1_000))

    def sign_up(email: str | None = None, name: str = "Ana") -> TestClient:
        browser = make_client()
        email = email or f"user{next(counter)}@example.com"
        response = browser.post("/api/auth/signup", json={"name": name, "email": email, "password": PASSWORD})
        assert response.status_code == 201, response.text
        return browser

    return sign_up
