from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.importing import account, import_file, transactions

SignedIn = Callable[..., TestClient]

STATEMENT = (
    "Data;Descrição;Valor\n"
    "28/10/2026;UBER *TRIP;-23,90\n"
    "03/11/2026;IFD*PIZZARIA BELLA;-61,00\n"
    "04/11/2026;LOJA DESCONHECIDA;-150,00\n"
    "05/11/2026;Pagamento de fatura;-1.000,00\n"
    "06/11/2026;UBER *TRIP;-18,50\n"
)


def _category(browser: TestClient, name: str) -> int:
    return int(next(c["id"] for c in browser.get("/api/categories").json() if c["name"] == name))


def _imported(signed_in: SignedIn) -> TestClient:
    browser = signed_in()
    import_file(browser, account(browser), STATEMENT)
    return browser


def test_filters(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    assert len(transactions(browser)) == 5
    assert len(transactions(browser, month="2026-11")) == 4
    assert [t["merchant"] for t in transactions(browser, q="uber")] == ["Uber", "Uber"]
    assert [t["description_raw"] for t in transactions(browser, uncategorized=True)] == ["LOJA DESCONHECIDA"]
    assert [t["description_raw"] for t in transactions(browser, kind="transfer")] == ["Pagamento de fatura"]
    assert browser.get("/api/transactions", params={"month": "2026-13"}).status_code == 422


def test_newest_first_with_a_total_for_paging(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    page = browser.get("/api/transactions", params={"limit": 2}).json()
    assert page["total"] == 5
    assert [t["date"] for t in page["items"]] == ["2026-11-06", "2026-11-05"]


def test_a_person_categorizes_by_hand(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    unknown = transactions(browser, uncategorized=True)[0]
    gifts = _category(browser, "Doações e presentes")
    updated = browser.patch(f"/api/transactions/{unknown['id']}", json={"category_id": gifts}).json()
    assert (updated["category_id"], updated["category_source"]) == (gifts, "user")
    assert updated["edited_at"] is not None


def test_marking_a_transfer_clears_the_category(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    pizza = transactions(browser, q="pizzaria")[0]
    assert pizza["category_id"] is not None
    updated = browser.patch(f"/api/transactions/{pizza['id']}", json={"kind": "transfer"}).json()
    assert (updated["kind"], updated["category_id"]) == ("transfer", None)


def test_bulk_actions(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    rides = [t["id"] for t in transactions(browser, q="uber")]
    work = browser.post("/api/categories", json={"name": "Trabalho", "type": "expense"}).json()["id"]
    result = browser.post(
        "/api/transactions/bulk", json={"ids": rides, "action": "categorize", "category_id": work}
    )
    assert result.json() == {"updated": 2}
    assert {t["category_id"] for t in transactions(browser, q="uber")} == {work}

    assert browser.post("/api/transactions/bulk", json={"ids": rides, "action": "delete"}).json() == {
        "updated": 2
    }
    assert transactions(browser, q="uber") == []


def test_bulk_refuses_ids_that_are_not_yours(signed_in: SignedIn) -> None:
    owner, intruder = _imported(signed_in), _imported(signed_in)
    foreign = transactions(owner)[0]["id"]
    mine = transactions(intruder)[0]["id"]
    response = intruder.post("/api/transactions/bulk", json={"ids": [mine, foreign], "action": "ignore"})
    assert response.status_code == 404
    assert transactions(owner)[0]["kind"] == "regular"


def test_applying_a_new_rule_to_past_transactions_spares_hand_edits(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    first, second = sorted(transactions(browser, q="uber"), key=lambda t: t["date"])
    commute = browser.post("/api/categories", json={"name": "Ida ao trabalho", "type": "expense"}).json()[
        "id"
    ]
    gifts = _category(browser, "Doações e presentes")
    browser.patch(f"/api/transactions/{first['id']}", json={"category_id": gifts})  # a person's choice

    rule = browser.post(
        "/api/rules", json={"match_type": "merchant", "pattern": "Uber", "category_id": commute}
    )
    applied = browser.post(f"/api/rules/{rule.json()['id']}/apply")
    assert applied.json() == {"updated": 1}
    by_id = {t["id"]: t for t in transactions(browser, q="uber")}
    assert by_id[second["id"]]["category_id"] == commute
    assert by_id[second["id"]]["category_source"] == "rule"
    assert by_id[first["id"]]["category_id"] == gifts
