from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient

from financepro import clock
from financepro.accounts.models import Account, AccountKind
from financepro.cards.installments import add_months, counter, detect_convention
from financepro.cards.statements import cycle
from tests.importing import account, import_file, transactions

SignedIn = Callable[..., TestClient]
HEADER = "date,title,amount\n"


@pytest.fixture(autouse=True)
def _today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "today", lambda: date(2026, 11, 20))


def _csv(*lines: tuple[str, str, str]) -> str:
    return HEADER + "".join(f'{day},"{title}",{amount}\n' for day, title, amount in lines)


class TestCounters:
    @pytest.mark.parametrize(
        ("description", "expected"),
        [
            ("Magalu - Parcela 3/10", (3, 10)),
            ("CASAS BAHIA 03/12", (3, 12)),
            ("PARC 01/03 LOJA", (1, 3)),
            ("Loja Parcela 2 de 6", (2, 6)),
            ("PADARIA 12/2026", None),  # a date, not a counter
            ("Pix 1/1", None),  # one installment is not installments
            ("LOJA 11/10", None),  # k > n
        ],
    )
    def test_reading_the_counter(self, description: str, expected: tuple[int, int] | None) -> None:
        assert counter(description) == expected

    def test_adding_months_clamps_to_the_month_end(self) -> None:
        assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
        assert add_months(date(2026, 12, 15), 2) == date(2027, 2, 15)

    def test_which_date_a_file_gives_installments(self) -> None:
        statement = [(date(2026, 11, d), None) for d in (4, 10, 20, 30)]
        billed = [*statement, (date(2026, 11, 5), (3, 10))]
        purchased = [*statement, (date(2026, 9, 5), (3, 10))]  # two months before the statement
        assert detect_convention(billed) == "billing"
        assert detect_convention(purchased) == "purchase"


class TestInstallments:
    def test_installments_across_statements_are_one_purchase(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        card = account(browser, "credit_card")
        import_file(
            browser,
            card,
            _csv(("2026-10-05", "Magalu - Parcela 3/10", "289.90"), ("2026-10-08", "Uber", "20.00")),
        )
        first = browser.get("/api/installments").json()
        assert len(first) == 1
        assert (first[0]["merchant"], first[0]["paid"], first[0]["installments"]) == ("Magalu", 3, 10)
        assert len(first[0]["future"]) == 7  # 1/10 and 2/10 were never imported and are not invented
        assert first[0]["future"][0] == {"month": "2026-11-01", "amount_cents": -28990}

        import_file(browser, card, _csv(("2026-11-05", "Magalu - Parcela 4/10", "289.90")))
        second = browser.get("/api/installments").json()
        assert len(second) == 1
        assert second[0]["id"] == first[0]["id"]
        assert second[0]["paid"] == 4
        assert len(second[0]["future"]) == 6
        assert {t["installment_group_id"] for t in transactions(browser, q="magalu")} == {first[0]["id"]}

    def test_the_first_installment_may_differ_by_a_cent(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        card = account(browser, "credit_card")
        import_file(browser, card, _csv(("2026-09-05", "Loja X - Parcela 1/3", "333.34")))
        import_file(browser, card, _csv(("2026-10-05", "Loja X - Parcela 2/3", "333.33")))
        groups = browser.get("/api/installments").json()
        assert len(groups) == 1
        assert groups[0]["paid"] == 2

    def test_two_identical_purchases_are_two_groups(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        card = account(browser, "credit_card")
        content = _csv(
            ("2026-10-05", "Loja X - Parcela 1/2", "100.00"), ("2026-10-06", "Loja X - Parcela 1/2", "100.00")
        )
        import_file(browser, card, content)
        assert len(browser.get("/api/installments").json()) == 2

    def test_installments_dated_on_the_purchase_count_in_the_billed_month(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        card = account(browser, "credit_card")
        content = _csv(
            ("2026-11-04", "Uber", "20.00"),
            ("2026-11-20", "Padaria", "10.00"),
            ("2026-09-15", "Magalu - Parcela 3/10", "289.90"),  # bought in September, billed in November
        )
        import_file(browser, card, content)
        magalu = transactions(browser, q="magalu")[0]
        assert (magalu["date"], magalu["effective_date"]) == ("2026-09-15", "2026-11-15")
        assert [t["description_raw"] for t in transactions(browser, month="2026-09")] == []
        assert "Magalu - Parcela 3/10" in [
            t["description_raw"] for t in transactions(browser, month="2026-11")
        ]

    def test_undoing_imports_shrinks_and_then_drops_the_group(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        card = account(browser, "credit_card")
        first = import_file(browser, card, _csv(("2026-10-05", "Magalu - Parcela 3/10", "289.90")))
        second = import_file(browser, card, _csv(("2026-11-05", "Magalu - Parcela 4/10", "289.90")))
        browser.post(f"/api/imports/{second['id']}/undo", json={})
        assert browser.get("/api/installments").json()[0]["paid"] == 3
        browser.post(f"/api/imports/{first['id']}/undo", json={})
        assert browser.get("/api/installments").json() == []


class TestStatements:
    def test_the_cycle_around_the_closing_day(self) -> None:
        card = Account(kind=AccountKind.CREDIT_CARD, closing_day=3, due_day=10)
        assert cycle(card, date(2026, 11, 1)) == (date(2026, 10, 3), date(2026, 11, 3), date(2026, 11, 10))
        # Due before closing in the month: the due date falls in the next month.
        late = Account(kind=AccountKind.CREDIT_CARD, closing_day=28, due_day=5)
        assert cycle(late, date(2026, 11, 1))[2] == date(2026, 12, 5)
        # Closing on the 31st closes on the last day of shorter months.
        end = Account(kind=AccountKind.CREDIT_CARD, closing_day=31, due_day=8)
        assert cycle(end, date(2027, 2, 1))[1] == date(2027, 2, 28)

    def test_statements_bill_what_each_cycle_charged(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        card = account(browser, "credit_card")  # closes on the 3rd, due on the 10th
        content = _csv(
            ("2026-10-02", "Uber", "20.00"),  # before Oct 3: October's statement
            ("2026-10-03", "Mercado", "100.00"),  # on the closing day: November's
            ("2026-11-02", "Farmacia", "50.00"),  # November's
            ("2026-11-02", "Estorno Farmacia", "-10.00"),  # a refund lowers it
            ("2026-11-10", "Pagamento recebido", "-140.00"),  # pays November's
            ("2026-11-05", "Livraria", "30.00"),  # December's, still open
        )
        import_file(browser, card, content)
        found = {s["month"]: s for s in browser.get(f"/api/accounts/{card}/statements").json()}
        assert (found["2026-12-01"]["charges_cents"], found["2026-12-01"]["status"]) == (3000, "open")
        assert (found["2026-11-01"]["charges_cents"], found["2026-11-01"]["paid_cents"]) == (14000, 14000)
        assert found["2026-11-01"]["status"] == "paid"
        assert (found["2026-10-01"]["charges_cents"], found["2026-10-01"]["status"]) == (2000, "unpaid")

    def test_only_cards_have_statements(self, signed_in: SignedIn) -> None:
        browser = signed_in()
        response = browser.get(f"/api/accounts/{account(browser)}/statements")
        assert response.status_code == 422
