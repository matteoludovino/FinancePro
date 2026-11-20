import hashlib
from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from financepro import clock
from financepro.accounts.models import Account
from financepro.auth.models import Session as SessionRow
from financepro.auth.models import User
from financepro.auth.sessions import cookie_name
from tests.conftest import PASSWORD

SignedIn = Callable[..., TestClient]


def test_signup_signs_in_and_never_stores_the_password(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/auth/signup", json={"name": " Ana ", "email": "Ana@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "name": "Ana",
        "email": "ana@example.com",
        "is_sandbox": False,
    }
    assert client.get("/api/auth/me").json()["email"] == "ana@example.com"
    user = db.scalars(select(User)).one()
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_one_account_per_email_whatever_the_case(signed_in: SignedIn, client: TestClient) -> None:
    signed_in("ana@example.com")
    response = client.post(
        "/api/auth/signup", json={"name": "Outra", "email": "ANA@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe uma conta com este e-mail."


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        (
            {"name": "Ana", "email": "ana@example.com", "password": "curta"},
            "password",
            "Use pelo menos 10 caracteres.",
        ),
        ({"name": "Ana", "email": "não é e-mail", "password": PASSWORD}, "email", "E-mail inválido."),
        ({"name": "  ", "email": "ana@example.com", "password": PASSWORD}, "name", "Campo obrigatório."),
        (
            {"name": "Ana", "email": "ana@example.com", "password": "ana@example.com"},
            "_",
            "A senha não pode ser o seu e-mail.",
        ),
    ],
)
def test_signup_errors_are_written_for_people(
    client: TestClient, body: dict[str, str], field: str, message: str
) -> None:
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 422
    assert response.json()["errors"][field] == message


def test_wrong_password_and_unknown_email_look_the_same(signed_in: SignedIn, client: TestClient) -> None:
    signed_in("ana@example.com")
    wrong = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "errada-errada"})
    unknown = client.post("/api/auth/login", json={"email": "ninguem@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 400
    assert wrong.json() == unknown.json() == {"detail": "E-mail ou senha incorretos."}


def test_login_with_any_case(signed_in: SignedIn, client: TestClient) -> None:
    signed_in("ana@example.com")
    response = client.post("/api/auth/login", json={"email": "ANA@example.com", "password": PASSWORD})
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_guessing_one_account_is_throttled_per_email(signed_in: SignedIn, client: TestClient) -> None:
    signed_in("ana@example.com")
    signed_in("bia@example.com")
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "ana@example.com", "password": "errada-errada"})
    # Locked even with the right password, so guessing can't continue...
    right = client.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert right.status_code == 429
    # ...but only for that e-mail: behind the Vercel proxy everyone shares an IP.
    other = client.post("/api/auth/login", json={"email": "bia@example.com", "password": PASSWORD})
    assert other.status_code == 200


def test_logout_ends_the_session_server_side(
    signed_in: SignedIn, make_client: Callable[[], TestClient]
) -> None:
    browser = signed_in()
    token = browser.cookies[cookie_name()]
    assert browser.post("/api/auth/logout").status_code == 204
    assert browser.get("/api/auth/me").status_code == 401
    # A copy of the old cookie is worthless too.
    thief = make_client()
    thief.cookies.set(cookie_name(), token)
    assert thief.get("/api/auth/me").status_code == 401


def test_only_a_hash_of_the_token_is_stored(signed_in: SignedIn, db: Session) -> None:
    token = signed_in().cookies[cookie_name()]
    stored = db.scalars(select(SessionRow.token_hash)).one()
    assert stored == hashlib.sha256(token.encode()).digest()
    assert token.encode() not in stored


def test_expired_sessions_are_rejected(signed_in: SignedIn, db: Session) -> None:
    browser = signed_in()
    for row in db.scalars(select(SessionRow)):
        row.expires_at = clock.now() - timedelta(seconds=1)
    db.flush()
    assert browser.get("/api/auth/me").status_code == 401


def test_a_session_in_use_is_extended(signed_in: SignedIn, db: Session) -> None:
    browser = signed_in()
    row = db.scalars(select(SessionRow)).one()
    row.expires_at = clock.now() + timedelta(days=3)
    db.flush()
    response = browser.get("/api/auth/me")
    assert response.status_code == 200
    assert "max-age=1209600" in response.headers["set-cookie"].lower()
    db.refresh(row)
    assert row.expires_at > clock.now() + timedelta(days=13)


def test_deleting_the_account_needs_the_password_and_takes_everything(
    signed_in: SignedIn, db: Session
) -> None:
    browser = signed_in()
    browser.post("/api/accounts", json={"name": "Nubank", "kind": "checking"})
    wrong = browser.request("DELETE", "/api/auth/me", json={"password": "errada-errada"})
    assert wrong.status_code == 400
    assert browser.request("DELETE", "/api/auth/me", json={"password": PASSWORD}).status_code == 204
    assert browser.get("/api/auth/me").status_code == 401
    assert db.scalars(select(User)).all() == []
    assert db.scalars(select(Account)).all() == []
    assert db.scalars(select(SessionRow)).all() == []


def test_state_changes_from_other_sites_are_refused(signed_in: SignedIn) -> None:
    browser = signed_in()
    forged = browser.post(
        "/api/accounts", json={"name": "X", "kind": "wallet"}, headers={"origin": "https://evil.example"}
    )
    assert forged.status_code == 403
    # A form post from another site without Origin still carries Sec-Fetch-Site.
    del browser.headers["origin"]
    cross = browser.post(
        "/api/accounts", json={"name": "X", "kind": "wallet"}, headers={"sec-fetch-site": "cross-site"}
    )
    assert cross.status_code == 403
    # Reads are not state changes.
    assert browser.get("/api/accounts", headers={"origin": "https://evil.example"}).status_code == 200
