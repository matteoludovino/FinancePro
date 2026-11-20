from collections.abc import Callable

from fastapi.testclient import TestClient

from financepro.categories.taxonomy import SLUGS

SignedIn = Callable[..., TestClient]


def _by_name(categories: list[dict[str, object]], name: str) -> dict[str, object]:
    return next(c for c in categories if c["name"] == name)


def test_a_new_person_starts_with_the_taxonomy(signed_in: SignedIn) -> None:
    categories = signed_in().get("/api/categories").json()
    assert {c["slug"] for c in categories} == set(SLUGS)
    food = _by_name(categories, "Alimentação")
    restaurants = _by_name(categories, "Restaurantes e bares")
    assert restaurants["parent_id"] == food["id"]
    assert (food["type"], _by_name(categories, "Salário")["type"]) == ("expense", "income")


def test_subcategories_take_the_parent_type_and_stop_at_two_levels(signed_in: SignedIn) -> None:
    browser = signed_in()
    food = _by_name(browser.get("/api/categories").json(), "Alimentação")
    child = browser.post("/api/categories", json={"name": "Feira", "parent_id": food["id"], "type": "income"})
    assert child.status_code == 201
    assert child.json()["type"] == "expense"
    grandchild = browser.post("/api/categories", json={"name": "Frutas", "parent_id": child.json()["id"]})
    assert grandchild.status_code == 422
    assert grandchild.json()["detail"] == "Subcategorias não podem ter subcategorias."


def test_a_top_level_category_needs_a_type(signed_in: SignedIn) -> None:
    response = signed_in().post("/api/categories", json={"name": "Investimentos"})
    assert response.status_code == 422


def test_names_are_unique_among_siblings_only(signed_in: SignedIn) -> None:
    browser = signed_in()
    categories = browser.get("/api/categories").json()
    food, leisure = _by_name(categories, "Alimentação"), _by_name(categories, "Lazer")
    assert (
        browser.post("/api/categories", json={"name": "outros", "parent_id": food["id"]}).status_code == 201
    )
    duplicate = browser.post("/api/categories", json={"name": "OUTROS", "parent_id": food["id"]})
    assert duplicate.status_code == 409
    # Another parent may have its own "Outros"; so may the top level.
    assert (
        browser.post("/api/categories", json={"name": "Outros", "parent_id": leisure["id"]}).status_code
        == 201
    )
    assert browser.post("/api/categories", json={"name": "Outros", "type": "expense"}).status_code == 201


def test_categories_in_use_are_archived_not_deleted(signed_in: SignedIn) -> None:
    browser = signed_in()
    categories = browser.get("/api/categories").json()
    food = _by_name(categories, "Alimentação")
    assert browser.delete(f"/api/categories/{food['id']}").status_code == 409  # it has subcategories

    bakery = _by_name(categories, "Padaria e café")
    browser.post(
        "/api/rules", json={"match_type": "contains", "pattern": "padoca", "category_id": bakery["id"]}
    )
    in_use = browser.delete(f"/api/categories/{bakery['id']}")
    assert in_use.status_code == 409
    assert "1 regra(s)" in in_use.json()["detail"]

    archived = browser.patch(f"/api/categories/{bakery['id']}", json={"is_archived": True})
    assert archived.json()["is_archived"] is True

    created = browser.post("/api/categories", json={"name": "Temporária", "type": "expense"}).json()
    assert browser.delete(f"/api/categories/{created['id']}").status_code == 204
