from collections.abc import Callable
from itertools import count

import pytest
from fastapi.testclient import TestClient

from financepro.categorization.engine import Categorizer, specificity
from financepro.categorization.models import Kind, MatchType, Rule

SignedIn = Callable[..., TestClient]

_ids = count(1)


def _rule(pattern: str, match: MatchType = MatchType.CONTAINS, **fields: object) -> Rule:
    fields.setdefault("sets_kind", Kind.REGULAR)
    fields.setdefault("category_id", next(_ids))
    return Rule(id=next(_ids), match_type=match, pattern=pattern, **fields)


class TestSpecificity:
    """The most specific rule wins, so people never have to order rules by hand."""

    def test_narrower_rules_win(self) -> None:
        broad = _rule("uber")
        cheap = _rule("uber", max_cents=3000)
        on_card = _rule("uber", account_id=7)
        ranked = sorted([broad, cheap, on_card], key=specificity, reverse=True)
        assert ranked == [on_card, cheap, broad]

    def test_exact_merchant_beats_prefix_beats_contains(self) -> None:
        contains, prefix, merchant = (
            _rule("uber"),
            _rule("uber", MatchType.STARTS_WITH),
            _rule("uber", MatchType.MERCHANT),
        )
        assert sorted([contains, prefix, merchant], key=specificity, reverse=True) == [
            merchant,
            prefix,
            contains,
        ]

    def test_a_longer_pattern_is_more_specific(self) -> None:
        assert specificity(_rule("uber eats")) > specificity(_rule("uber"))


class TestDecide:
    def test_rules_match_without_case_or_accents(self) -> None:
        rule = _rule("pao de acucar")
        decision = Categorizer([rule], {}).decide("PÃO DE AÇÚCAR 123", -5000)
        assert decision.rule_id == rule.id

    def test_amount_range_is_on_the_absolute_value(self) -> None:
        rule = _rule("uber", min_cents=1000, max_cents=3000)
        categorizer = Categorizer([rule], {})
        assert categorizer.decide("UBER TRIP", -2000).rule_id == rule.id
        assert categorizer.decide("UBER TRIP", 2000).rule_id == rule.id  # a refund of the same ride
        assert categorizer.decide("UBER TRIP", -5000).rule_id is None

    def test_account_filter(self) -> None:
        rule = _rule("anuidade", account_id=3)
        categorizer = Categorizer([rule], {})
        assert categorizer.decide("ANUIDADE", -100, account_id=3).rule_id == rule.id
        assert categorizer.decide("ANUIDADE", -100, account_id=4).rule_id is None

    def test_merchant_rules_compare_the_normalized_merchant(self) -> None:
        rule = _rule("ifood", MatchType.MERCHANT)
        assert Categorizer([rule], {}).decide("IFD*PIZZARIA BELLA 991", -4500).rule_id == rule.id

    def test_known_merchants_fill_in_when_no_rule_matches(self) -> None:
        decision = Categorizer([], {"delivery": 42}).decide("IFD*PIZZARIA BELLA", -4500)
        assert (decision.category_id, decision.source, decision.merchant) == (42, "merchant", "iFood")

    def test_a_rule_beats_built_in_knowledge(self) -> None:
        rule = _rule("ifood")
        decision = Categorizer([rule], {"delivery": 42}).decide("IFOOD *PEDIDO", -4500)
        assert (decision.category_id, decision.source) == (rule.category_id, "rule")

    def test_nothing_known_stays_undecided(self) -> None:
        decision = Categorizer([], {}).decide("LOJA DESCONHECIDA", -100)
        assert (decision.kind, decision.category_id, decision.source) == (Kind.REGULAR, None, None)


def _category_id(browser: TestClient, name: str) -> int:
    return int(next(c["id"] for c in browser.get("/api/categories").json() if c["name"] == name))


def _preview(browser: TestClient, description: str, **extra: object) -> dict[str, object]:
    response = browser.post("/api/rules/preview", json={"description": description, **extra})
    assert response.status_code == 200, response.text
    data: dict[str, object] = response.json()
    return data


@pytest.mark.parametrize(
    "description",
    ["Pagamento recebido", "Pagamento de fatura", "PAGAMENTO EFETUADO", "Aplicação RDB", "Resgate RDB"],
)
def test_default_rules_keep_transfers_out_of_spending(signed_in: SignedIn, description: str) -> None:
    decision = _preview(signed_in(), description)
    assert (decision["kind"], decision["category_id"], decision["source"]) == ("transfer", None, "rule")


def test_built_in_merchants_map_to_the_persons_own_category(signed_in: SignedIn) -> None:
    browser = signed_in()
    decision = _preview(browser, "IFD*PIZZARIA BELLA")
    assert decision["category_id"] == _category_id(browser, "Delivery")
    assert decision["source"] == "merchant"


def test_a_new_rule_changes_the_decision(signed_in: SignedIn) -> None:
    browser = signed_in()
    work = browser.post("/api/categories", json={"name": "Trabalho", "type": "expense"}).json()
    created = browser.post(
        "/api/rules",
        json={"match_type": "contains", "pattern": "  UBER  ", "category_id": work["id"], "max_cents": 3000},
    )
    assert created.status_code == 201
    assert created.json()["pattern"] == "uber"
    assert _preview(browser, "UBER *TRIP", amount_cents=-2500)["category_id"] == work["id"]
    # Above the range, built-in knowledge applies again.
    expensive = _preview(browser, "UBER *TRIP", amount_cents=-9000)
    assert expensive["category_id"] == _category_id(browser, "Apps de transporte")


def test_rules_need_a_category_unless_they_mark_a_transfer(signed_in: SignedIn) -> None:
    browser = signed_in()
    missing = browser.post("/api/rules", json={"match_type": "contains", "pattern": "uber"})
    assert missing.status_code == 422
    assert missing.json()["detail"] == "Escolha a categoria."
    transfer = browser.post(
        "/api/rules", json={"match_type": "contains", "pattern": "minha poupanca", "sets_kind": "transfer"}
    )
    assert transfer.json()["category_id"] is None


def test_identical_rules_are_refused(signed_in: SignedIn) -> None:
    browser = signed_in()
    body = {
        "match_type": "contains",
        "pattern": "padoca",
        "category_id": _category_id(browser, "Padaria e café"),
    }
    assert browser.post("/api/rules", json=body).status_code == 201
    assert browser.post("/api/rules", json={**body, "pattern": "PADOCA"}).status_code == 409
    assert browser.post("/api/rules", json={**body, "max_cents": 2000}).status_code == 201


def test_rules_cannot_point_at_someone_elses_category(signed_in: SignedIn) -> None:
    owner, intruder = signed_in(), signed_in()
    foreign = _category_id(owner, "Mercado")
    response = intruder.post(
        "/api/rules", json={"match_type": "contains", "pattern": "xy", "category_id": foreign}
    )
    assert response.status_code == 404
