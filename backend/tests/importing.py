"""Helpers for tests that import files."""

from typing import Any

from fastapi.testclient import TestClient


def account(browser: TestClient, kind: str = "checking", name: str | None = None) -> int:
    body: dict[str, Any] = {"name": name or f"Conta {kind}", "kind": kind}
    if kind == "credit_card":
        body |= {"closing_day": 3, "due_day": 10}
    response = browser.post("/api/accounts", json=body)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def upload(
    browser: TestClient, account_id: int, content: str | bytes, name: str = "extrato.csv"
) -> dict[str, Any]:
    data = content.encode() if isinstance(content, str) else content
    response = browser.post(
        "/api/imports", data={"account_id": str(account_id)}, files={"file": (name, data, "text/csv")}
    )
    assert response.status_code == 201, response.text
    batch: dict[str, Any] = response.json()
    return batch


def confirm(browser: TestClient, batch: dict[str, Any], include: list[int] | None = None) -> dict[str, Any]:
    response = browser.post(f"/api/imports/{batch['id']}/confirm", json={"include_lines": include or []})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def import_file(browser: TestClient, account_id: int, content: str | bytes) -> dict[str, Any]:
    return confirm(browser, upload(browser, account_id, content))


def transactions(browser: TestClient, **params: Any) -> list[dict[str, Any]]:
    """Every matching transaction, following the pages."""
    items: list[dict[str, Any]] = []
    while True:
        response = browser.get("/api/transactions", params={"limit": 200, "offset": len(items), **params})
        assert response.status_code == 200, response.text
        page = response.json()
        items += page["items"]
        if len(items) >= page["total"] or not page["items"]:
            return items
