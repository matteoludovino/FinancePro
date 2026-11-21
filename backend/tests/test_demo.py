from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from financepro import clock
from financepro.auth.models import Session as SessionRow
from financepro.auth.models import User
from financepro.auth.sessions import cookie_name
from financepro.demo import sandbox
from financepro.settings import get_settings
from tests.conftest import PASSWORD
from tests.importing import account, import_file, transactions

SignedIn = Callable[..., TestClient]


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", True)


def _visitor(make_client: Callable[[], TestClient]) -> TestClient:
    browser = make_client()
    response = browser.post("/api/demo/start")
    assert response.status_code == 201, response.text
    return browser


def test_there_is_no_demo_outside_demo_mode(client: TestClient) -> None:
    assert client.post("/api/demo/start").status_code == 404


@pytest.mark.usefixtures("demo")
class TestSandbox:
    def test_a_visitor_gets_a_lived_in_copy(self, make_client: Callable[[], TestClient]) -> None:
        browser = _visitor(make_client)
        me = browser.get("/api/auth/me").json()
        assert me["is_sandbox"] is True
        assert [a["name"] for a in browser.get("/api/accounts").json()] == ["Cartão Nubank", "Nubank"]
        everything = transactions(browser)
        assert len(everything) > 150
        # Built through the real pipeline: bills linked as transfers, installments grouped...
        assert any(t["transfer_pair_id"] for t in everything)
        assert browser.get("/api/installments").json()
        # ...budgets to look at, and AI suggestions served from the cache with no model behind them.
        assert len(browser.get("/api/budgets").json()) == len(sandbox.BUDGETS)
        assert "Acougue Bom Corte" in {g["merchant"] for g in browser.get("/api/ai/suggestions").json()}

    def test_visitors_never_see_each_other(self, make_client: Callable[[], TestClient]) -> None:
        first, second = _visitor(make_client), _visitor(make_client)
        assert first.get("/api/auth/me").json()["id"] != second.get("/api/auth/me").json()["id"]
        mine = {t["id"] for t in transactions(first)}
        assert mine.isdisjoint({t["id"] for t in transactions(second)})

    def test_the_more_recent_sample_shows_deduplication(self, make_client: Callable[[], TestClient]) -> None:
        browser = _visitor(make_client)
        checking = next(a["id"] for a in browser.get("/api/accounts").json() if a["kind"] == "checking")
        result = import_file(
            browser, checking, browser.get("/api/samples/nubank-conta-atualizado.csv").content
        )
        assert result["summary"]["duplicate"] > 0
        assert result["summary"]["inserted"] > 0

    def test_only_the_sites_samples_can_be_imported(self, make_client: Callable[[], TestClient]) -> None:
        browser = _visitor(make_client)
        response = browser.post(
            "/api/imports",
            data={"account_id": str(account(browser))},
            files={"file": ("meu-extrato.csv", b"Data;Descricao;Valor\n01/11/2026;LOJA;-5,00\n")},
        )
        assert response.status_code == 422
        assert "arquivos de exemplo" in response.json()["detail"]

    def test_nobody_signs_up_with_a_password(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/signup", json={"name": "Ana", "email": "ana@example.com", "password": PASSWORD}
        )
        assert response.status_code == 403

    def test_a_sandbox_session_lasts_three_idle_hours(self, make_client: Callable[[], TestClient]) -> None:
        browser = make_client()
        response = browser.post("/api/demo/start")
        assert "max-age=10800" in response.headers["set-cookie"].lower()
        assert browser.cookies[cookie_name()]

    def test_the_number_of_live_sandboxes_is_capped(
        self, make_client: Callable[[], TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "demo_max_sandboxes", 1)
        _visitor(make_client)
        response = make_client().post("/api/demo/start")
        assert response.status_code == 503
        assert response.json()["detail"] == "A demonstração está cheia agora. Tente de novo mais tarde."

    def test_idle_sandboxes_are_deleted_with_everything_in_them(
        self, make_client: Callable[[], TestClient], db: Session
    ) -> None:
        idle, active = _visitor(make_client), _visitor(make_client)
        idle_id = idle.get("/api/auth/me").json()["id"]
        db.execute(update(SessionRow).where(SessionRow.user_id == idle_id).values(expires_at=clock.now()))
        db.execute(update(User).values(created_at=clock.now() - timedelta(hours=4)))
        assert sandbox.cleanup(db) == 1
        assert db.scalars(select(User.id)).all() == [active.get("/api/auth/me").json()["id"]]
        assert idle.get("/api/auth/me").status_code == 401
