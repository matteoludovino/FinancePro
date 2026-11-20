"""One person can never reach another's data: a foreign id answers exactly like a missing one (404).

The test walks every route of the app that takes an id in its path, so a new endpoint can't be added
without being covered here: it fails until the route's resource has a factory below.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from financepro.main import create_app

SignedIn = Callable[..., TestClient]


# How to create, as the owner, the resource each path parameter points to. Returns its id.
def _account(owner: TestClient) -> int:
    response = owner.post("/api/accounts", json={"name": "Nubank", "kind": "checking"})
    return int(response.json()["id"])


FACTORIES: dict[str, Callable[[TestClient], int]] = {"account_id": _account}

# Plausible bodies, so a request reaches the ownership check instead of failing validation first.
BODIES: dict[str, dict[str, object]] = {"PATCH": {"name": "Outro nome"}}


def _routes_with_ids() -> list[tuple[str, str]]:
    # The OpenAPI document is the public list of every operation, however routers are nested.
    paths: dict[str, dict[str, object]] = create_app().openapi()["paths"]
    return [
        (method.upper(), path) for path, operations in paths.items() if "{" in path for method in operations
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
            url = url.replace(f"{{{param}}}", str(factory(owner)))
    response = intruder.request(method, url, json=BODIES.get(method))
    assert response.status_code == 404, response.text
    # And the owner still can.
    if method == "GET":
        assert owner.request(method, url).status_code == 200
