from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.importing import account, import_file, transactions

SignedIn = Callable[..., TestClient]

CHECKING = "Data;Descrição;Valor\n"
CARD = "date,title,amount\n"


def _by_description(browser: TestClient) -> dict[str, dict[str, object]]:
    return {str(t["description_raw"]): t for t in transactions(browser)}


def test_a_bill_payment_links_both_sides_on_import(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, card = account(browser), account(browser, "credit_card")
    import_file(browser, card, CARD + '2026-11-02,"Uber",140.00\n2026-11-10,"Pagamento recebido",-140.00\n')
    import_file(browser, checking, CHECKING + "10/11/2026;Pagamento de fatura;-140,00\n")
    found = _by_description(browser)
    paid, received = found["Pagamento de fatura"], found["Pagamento recebido"]
    assert paid["transfer_pair_id"] == received["id"]
    assert received["transfer_pair_id"] == paid["id"]
    assert paid["kind"] == received["kind"] == "transfer"


def test_a_transfer_to_another_own_account_is_suggested_then_confirmed(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, savings = account(browser), account(browser, "savings", name="Poupança")
    import_file(browser, checking, CHECKING + "05/11/2026;Pix para Dani - Banco Inter;-500,00\n")
    import_file(browser, savings, CHECKING + "06/11/2026;Pix recebido de Dani;500,00\n")
    suggestions = browser.get("/api/transfers/suggestions").json()
    assert len(suggestions) == 1
    pair = suggestions[0]
    assert (pair["outflow"]["amount_cents"], pair["inflow"]["amount_cents"]) == (-50000, 50000)

    confirmed = browser.post(
        "/api/transfers", json={"first_id": pair["outflow"]["id"], "second_id": pair["inflow"]["id"]}
    )
    assert confirmed.status_code == 201
    assert {t["kind"] for t in transactions(browser)} == {"transfer"}
    assert {t["category_id"] for t in transactions(browser)} == {None}
    assert browser.get("/api/transfers/suggestions").json() == []

    assert browser.delete(f"/api/transfers/{pair['outflow']['id']}").status_code == 204
    assert {t["transfer_pair_id"] for t in transactions(browser)} == {None}


def test_ambiguous_matches_are_not_guessed(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, savings = account(browser), account(browser, "savings", name="Poupança")
    import_file(browser, checking, CHECKING + "05/11/2026;Pix enviado;-500,00\n")
    import_file(
        browser, savings, CHECKING + "05/11/2026;Pix recebido A;500,00\n06/11/2026;Pix recebido B;500,00\n"
    )
    assert browser.get("/api/transfers/suggestions").json() == []


def test_a_card_purchase_is_never_one_side(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, card = account(browser), account(browser, "credit_card")
    import_file(browser, card, CARD + '2026-11-05,"Loja",500.00\n')
    import_file(browser, checking, CHECKING + "06/11/2026;Pix recebido de um amigo;500,00\n")
    assert browser.get("/api/transfers/suggestions").json() == []


def test_a_dismissed_suggestion_stays_dismissed(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, savings = account(browser), account(browser, "savings", name="Poupança")
    import_file(browser, checking, CHECKING + "05/11/2026;Aluguel;-500,00\n")
    import_file(browser, savings, CHECKING + "06/11/2026;Rendimento;500,00\n")
    pair = browser.get("/api/transfers/suggestions").json()[0]
    ids = {"first_id": pair["outflow"]["id"], "second_id": pair["inflow"]["id"]}
    assert browser.post("/api/transfers/dismiss", json=ids).status_code == 204
    assert browser.get("/api/transfers/suggestions").json() == []
    assert {t["kind"] for t in transactions(browser)} == {"regular"}


def test_pairs_must_be_opposite_amounts_in_two_accounts(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, savings = account(browser), account(browser, "savings", name="Poupança")
    import_file(browser, checking, CHECKING + "05/11/2026;A;-500,00\n06/11/2026;B;-500,00\n")
    import_file(browser, savings, CHECKING + "06/11/2026;C;400,00\n")
    found = _by_description(browser)
    same_account = browser.post(
        "/api/transfers", json={"first_id": found["A"]["id"], "second_id": found["B"]["id"]}
    )
    assert same_account.status_code == 422
    different = browser.post(
        "/api/transfers", json={"first_id": found["A"]["id"], "second_id": found["C"]["id"]}
    )
    assert different.status_code == 422


def test_undoing_one_side_unlinks_the_other(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking, card = account(browser), account(browser, "credit_card")
    import_file(browser, card, CARD + '2026-11-10,"Pagamento recebido",-140.00\n')
    checking_import = import_file(browser, checking, CHECKING + "10/11/2026;Pagamento de fatura;-140,00\n")
    browser.post(f"/api/imports/{checking_import['id']}/undo", json={})
    remaining = transactions(browser)
    assert [t["description_raw"] for t in remaining] == ["Pagamento recebido"]
    assert remaining[0]["transfer_pair_id"] is None
    assert remaining[0]["kind"] == "transfer"  # still a payment, just without its other side
