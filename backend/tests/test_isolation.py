"""One person can never reach another's data: a foreign id answers exactly like a missing one (404).

The test walks every route of the app that takes an id in its path, so a new endpoint can't be added
without being covered here: it fails until the route's resource has a factory below.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from financepro.main import create_app
from tests.importing import import_file, transactions, upload

SignedIn = Callable[..., TestClient]


# How to create, as the owner, the resource each path parameter points to. Returns its id.
def _account(owner: TestClient) -> int:
    response = owner.post("/api/accounts", json={"name": "Nubank", "kind": "checking"})
    return int(response.json()["id"])


def _card(owner: TestClient) -> int:
    body = {"name": "Cartão", "kind": "credit_card", "closing_day": 3, "due_day": 10}
    return int(owner.post("/api/accounts", json=body).json()["id"])


def _category(owner: TestClient) -> int:
    response = owner.post("/api/categories", json={"name": "Minha categoria", "type": "expense"})
    return int(response.json()["id"])


def _rule(owner: TestClient) -> int:
    body = {"match_type": "contains", "pattern": "uber", "sets_kind": "ignored"}
    response = owner.post("/api/rules", json=body)
    return int(response.json()["id"])


def _batch(owner: TestClient) -> int:
    return int(upload(owner, _account(owner), "Data;Descrição;Valor\n03/11/2026;LOJA;-5,00\n")["id"])


def _transaction(owner: TestClient) -> int:
    import_file(owner, _account(owner), "Data;Descrição;Valor\n03/11/2026;LOJA;-5,00\n")
    return int(transactions(owner)[0]["id"])


FACTORIES: dict[str, Callable[[TestClient], int]] = {
    "account_id": _account,
    "category_id": _category,
    "rule_id": _rule,
    "batch_id": _batch,
    "transaction_id": _transaction,
}

# Plausible bodies, so a request reaches the ownership check instead of failing validation first.
BODIES: dict[tuple[str, str], dict[str, object]] = {
    ("PATCH", "/api/accounts/{account_id}"): {"name": "Outro nome"},
    ("PATCH", "/api/categories/{category_id}"): {"name": "Outro nome"},
    ("PUT", "/api/rules/{rule_id}"): {"match_type": "contains", "pattern": "99app", "sets_kind": "transfer"},
    ("PUT", "/api/imports/{batch_id}/mapping"): {
        "date": 0,
        "description": [1],
        "amount": 2,
        "date_format": "%d/%m/%Y",
        "decimals": ",",
    },
    ("POST", "/api/imports/{batch_id}/confirm"): {},
    ("POST", "/api/imports/{batch_id}/undo"): {},
    ("PATCH", "/api/transactions/{transaction_id}"): {"notes": "x"},
}


# Routes with a path parameter that belong to no one, on purpose.
PUBLIC = {"/api/samples/{name}"}


def _routes_with_ids() -> list[tuple[str, str]]:
    # The OpenAPI document is the public list of every operation, however routers are nested.
    paths: dict[str, dict[str, object]] = create_app().openapi()["paths"]
    return [
        (method.upper(), path)
        for path, operations in paths.items()
        if "{" in path and path not in PUBLIC
        for method in operations
    ]


ROUTES = _routes_with_ids()


def test_every_route_with_an_id_has_a_factory() -> None:
    segments = (segment for _, path in ROUTES for segment in path.split("/"))
    params = {segment.strip("{}") for segment in segments if segment.startswith("{")}
    assert params <= FACTORIES.keys(), f"add factories for: {params - FACTORIES.keys()}"


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_a_foreign_id_is_not_found(signed_in: SignedIn, method: str, path: str) -> None:
    owner, intruder = signed_in(), signed_in()
    url = path
    for param, factory in FACTORIES.items():
        if f"{{{param}}}" in url:
            # Only cards have statements: the owner's resource must be one the route serves.
            make = _card if path.endswith("/statements") else factory
            url = url.replace(f"{{{param}}}", str(make(owner)))
    response = intruder.request(method, url, json=BODIES.get((method, path)))
    assert response.status_code == 404, response.text
    # And the owner still can.
    if method == "GET":
        assert owner.request(method, url).status_code == 200
