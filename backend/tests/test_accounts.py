from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financepro.accounts.models import Account, AccountKind
from financepro.auth.models import User

SignedIn = Callable[..., TestClient]


def test_create_list_update_and_delete(signed_in: SignedIn) -> None:
    browser = signed_in()
    nubank = browser.post("/api/accounts", json={"name": "Nubank", "kind": "checking", "institution": "Nu"})
    assert nubank.status_code == 201
    account_id = nubank.json()["id"]
    browser.post("/api/accounts", json={"name": "Carteira", "kind": "wallet"})
    assert [a["name"] for a in browser.get("/api/accounts").json()] == ["Carteira", "Nubank"]

    renamed = browser.patch(f"/api/accounts/{account_id}", json={"name": "Nubank PF", "is_archived": True})
    assert renamed.json()["name"] == "Nubank PF"
    assert renamed.json()["is_archived"] is True
    # Archived accounts go last.
    assert [a["name"] for a in browser.get("/api/accounts").json()] == ["Carteira", "Nubank PF"]

    assert browser.delete(f"/api/accounts/{account_id}").status_code == 204
    assert browser.get(f"/api/accounts/{account_id}").status_code == 404


def test_a_card_needs_its_statement_days(signed_in: SignedIn) -> None:
    browser = signed_in()
    missing = browser.post("/api/accounts", json={"name": "Cartão", "kind": "credit_card"})
    assert missing.status_code == 422
    assert missing.json()["detail"] == "Informe o dia de fechamento e o de vencimento da fatura."
    card = browser.post(
        "/api/accounts", json={"name": "Cartão", "kind": "credit_card", "closing_day": 3, "due_day": 10}
    )
    assert card.status_code == 201
    assert (card.json()["closing_day"], card.json()["due_day"]) == (3, 10)
    cleared = browser.patch(f"/api/accounts/{card.json()['id']}", json={"due_day": None})
    assert cleared.status_code == 422


def test_other_kinds_ignore_statement_days(signed_in: SignedIn) -> None:
    browser = signed_in()
    account = browser.post("/api/accounts", json={"name": "Conta", "kind": "checking", "closing_day": 3})
    assert account.json()["closing_day"] is None
    patched = browser.patch(f"/api/accounts/{account.json()['id']}", json={"closing_day": 5})
    assert patched.json()["closing_day"] is None


def test_names_are_unique_per_person_whatever_the_case(signed_in: SignedIn) -> None:
    ana, bia = signed_in(), signed_in()
    assert ana.post("/api/accounts", json={"name": "Nubank", "kind": "checking"}).status_code == 201
    duplicate = ana.post("/api/accounts", json={"name": "NUBANK", "kind": "savings"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Você já tem uma conta com este nome."
    # Another person may use the same name.
    assert bia.post("/api/accounts", json={"name": "Nubank", "kind": "checking"}).status_code == 201


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "Cartão", "kind": AccountKind.CREDIT_CARD},
        {"name": "Conta", "kind": AccountKind.CHECKING, "closing_day": 3, "due_day": 10},
    ],
)
def test_the_database_refuses_mismatched_statement_days(
    signed_in: SignedIn, db: Session, fields: dict[str, object]
) -> None:
    signed_in()
    account = Account(owner_id=db.scalars(select(User.id)).one(), **fields)
    with db.begin_nested():
        db.add(account)
        with pytest.raises(IntegrityError):
            db.flush()
