"""Reports with numbers worked out by hand.

November 2026:
  income   6.850,00  salary (uncategorized, positive)
  spending 2.200,00  rent by Pix (uncategorized, negative)
             100,00  Supermercado Dia (Mercado)
              40,00  iFood 60,00 minus a 20,00 refund (Delivery)
              55,90  Netflix (Streaming)
             289,90  Magalu, installment 3/10 (Compras online)
           --------
           2.685,80
  never counted: the bill payment on both sides (transfers) and money into the savings box (RDB).
October 2026: Supermercado Dia 50,00.
"""

from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient

from financepro import clock
from tests.importing import account, import_file

SignedIn = Callable[..., TestClient]

CHECKING = (
    "Data;Descrição;Valor\n"
    "15/10/2026;Compra no débito - SUPERMERCADO DIA;-50,00\n"
    "05/11/2026;Transferência Recebida - ACME TECNOLOGIA LTDA - 12.345.678/0001-90;6.850,00\n"
    "06/11/2026;Transferência enviada pelo Pix - IMOBILIARIA LAR FELIZ - •••.111.222-••;-2.200,00\n"
    "06/11/2026;Aplicação RDB;-500,00\n"
    "10/11/2026;Pagamento de fatura;-1.000,00\n"
    "12/11/2026;Compra no débito - SUPERMERCADO DIA;-100,00\n"
)
CARD = (
    "date,title,amount\n"
    '2026-11-02,"Magalu - Parcela 3/10",289.90\n'
    '2026-11-03,"IFD*PIZZARIA BELLA",60.00\n'
    '2026-11-04,"Netflix.com",55.90\n'
    '2026-11-08,"IFD*PIZZARIA BELLA",-20.00\n'
    '2026-11-10,"Pagamento recebido",-1000.00\n'
)


@pytest.fixture(autouse=True)
def _today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "today", lambda: date(2026, 11, 20))


@pytest.fixture
def browser(signed_in: SignedIn) -> TestClient:
    person = signed_in()
    import_file(person, account(person), CHECKING)
    import_file(person, account(person, "credit_card"), CARD)
    return person


def _category_id(browser: TestClient, name: str) -> int:
    return int(next(c["id"] for c in browser.get("/api/categories").json() if c["name"] == name))


def test_overview_of_the_month(browser: TestClient) -> None:
    assert browser.get("/api/reports/overview", params={"month": "2026-11"}).json() == {
        "month": "2026-11-01",
        "income_cents": 685000,
        "expense_cents": 268580,
        "previous_income_cents": 0,
        "previous_expense_cents": 5000,
        "uncategorized": 2,  # the salary and the rent: no rule or merchant knows them
        "ai_pending": 0,
    }


def test_income_and_spending_per_month(browser: TestClient) -> None:
    flow = browser.get("/api/reports/flow", params={"until": "2026-11", "count": 3}).json()
    assert flow == [
        {"month": "2026-09-01", "income_cents": 0, "expense_cents": 0},
        {"month": "2026-10-01", "income_cents": 0, "expense_cents": 5000},
        {"month": "2026-11-01", "income_cents": 685000, "expense_cents": 268580},
    ]


def test_spending_by_category_rolls_subcategories_up(browser: TestClient) -> None:
    found = browser.get("/api/reports/categories", params={"month": "2026-11"}).json()
    summary = [
        (c["name"], c["total_cents"], [(s["name"], s["total_cents"]) for s in c["children"]]) for c in found
    ]
    assert summary == [
        ("Compras", 28990, [("Compras online", 28990)]),
        ("Alimentação", 14000, [("Mercado", 10000), ("Delivery", 4000)]),  # the refund lowers Delivery
        ("Lazer", 5590, [("Streaming e assinaturas", 5590)]),
        ("Sem categoria", 220000, []),  # always last, whatever its size
    ]


def test_biggest_merchants(browser: TestClient) -> None:
    found = browser.get("/api/reports/merchants", params={"month": "2026-11"}).json()
    assert [(m["merchant"], m["total_cents"], m["count"]) for m in found] == [
        ("Pix para Imobiliaria Lar Feliz", 220000, 1),
        ("Magalu", 28990, 1),
        ("Supermercado Dia", 10000, 1),
        ("Netflix", 5590, 1),
        ("iFood", 4000, 2),
    ]


def test_installments_still_to_come(browser: TestClient) -> None:
    found = browser.get("/api/reports/commitments", params={"count": 8}).json()
    # 4/10 to 10/10: December to June; nothing in July.
    assert [(c["month"], c["amount_cents"]) for c in found] == [
        ("2026-12-01", 28990),
        ("2027-01-01", 28990),
        ("2027-02-01", 28990),
        ("2027-03-01", 28990),
        ("2027-04-01", 28990),
        ("2027-05-01", 28990),
        ("2027-06-01", 28990),
        ("2027-07-01", 0),
    ]


class TestBudgets:
    def test_spent_against_the_limit_including_subcategories(self, browser: TestClient) -> None:
        food = _category_id(browser, "Alimentação")
        browser.put(f"/api/budgets/{food}", json={"limit_cents": 15000, "from_month": "2026-11"})
        [budget] = browser.get("/api/budgets", params={"month": "2026-11"}).json()
        assert (budget["category_id"], budget["limit_cents"], budget["spent_cents"]) == (food, 15000, 14000)
        assert (budget["committed_cents"], budget["status"]) == (0, "warning")

    def test_installments_already_bought_count_as_committed(self, browser: TestClient) -> None:
        shopping = _category_id(browser, "Compras")
        browser.put(f"/api/budgets/{shopping}", json={"limit_cents": 25000, "from_month": "2026-12"})
        [budget] = browser.get("/api/budgets", params={"month": "2026-12"}).json()
        # Nothing spent yet in December, but Magalu 4/10 will be billed: already over.
        assert (budget["spent_cents"], budget["committed_cents"], budget["status"]) == (0, 28990, "over")

    def test_a_new_limit_applies_from_its_month_on(self, browser: TestClient) -> None:
        food = _category_id(browser, "Alimentação")
        browser.put(f"/api/budgets/{food}", json={"limit_cents": 15000, "from_month": "2026-11"})
        browser.put(f"/api/budgets/{food}", json={"limit_cents": 30000, "from_month": "2026-12"})
        browser.put(f"/api/budgets/{food}", json={"limit_cents": None, "from_month": "2027-02"})
        limits = {
            month: [b["limit_cents"] for b in browser.get("/api/budgets", params={"month": month}).json()]
            for month in ("2026-10", "2026-11", "2026-12", "2027-01", "2027-02")
        }
        assert limits == {
            "2026-10": [],
            "2026-11": [15000],
            "2026-12": [30000],
            "2027-01": [30000],
            "2027-02": [],
        }

    def test_only_spending_categories_have_budgets(self, browser: TestClient) -> None:
        salary = _category_id(browser, "Salário")
        response = browser.put(f"/api/budgets/{salary}", json={"limit_cents": 100})
        assert response.status_code == 422
