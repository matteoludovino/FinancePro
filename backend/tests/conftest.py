"""Tests run against a real PostgreSQL: constraints, partial indexes and ON CONFLICT don't exist in a mock.

The test database is the configured one with a `_test` suffix. It is migrated once per session, and each
test runs inside a transaction that is rolled back, so tests never see each other's rows.
"""

import os
from collections.abc import Iterator

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

from financepro.db import get_db, get_engine  # noqa: E402  # after the environment points at the test database
from financepro.main import create_app  # noqa: E402


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


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
