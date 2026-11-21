from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.importing import account, import_file

SignedIn = Callable[..., TestClient]


def test_samples_are_public_and_current(client: TestClient) -> None:
    response = client.get("/api/samples/nubank-conta.csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.text.startswith("Data,Valor,Identificador,Descrição\n")
    assert client.get("/api/samples/../../etc/passwd").status_code == 404
    assert client.get("/api/samples/outro.csv").status_code == 404


def test_the_updated_statement_brings_only_the_new_weeks(signed_in: SignedIn) -> None:
    browser = signed_in()
    checking = account(browser)
    first = import_file(browser, checking, browser.get("/api/samples/nubank-conta.csv").content)
    updated = import_file(browser, checking, browser.get("/api/samples/nubank-conta-atualizado.csv").content)
    assert first["summary"]["inserted"] > 0
    assert updated["summary"]["duplicate"] > 0
    assert 0 < updated["summary"]["inserted"] < updated["summary"]["total"]


def test_the_card_sample_imports_with_its_preset(signed_in: SignedIn) -> None:
    browser = signed_in()
    result = import_file(
        browser, account(browser, "credit_card"), browser.get("/api/samples/nubank-cartao.csv").content
    )
    assert result["detected_by"] == "preset:nubank_cartao"
    assert result["summary"]["error"] == 0
