from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from financepro.ai import privacy, service
from financepro.ai.classifier import UNKNOWN, Answer, AnthropicClassifier, Item, Result, parse, schema
from financepro.categories.taxonomy import SLUGS
from financepro.settings import get_settings
from tests.conftest import AiSwitch
from tests.importing import account, import_file, transactions

SignedIn = Callable[..., TestClient]

KNOWN = {"Livraria Cultura": "cursos", "Clinica Sorriso": "consultas-exames", "Pet Feliz": "pets"}


@dataclass
class FakeClassifier:
    """Answers from a table; anything not in it is "unknown". Records what it was asked."""

    answers: dict[str, str] = field(default_factory=lambda: dict(KNOWN))
    tokens: int = 1_000
    model: str = "claude-haiku-5-5"
    calls: list[list[Item]] = field(default_factory=list)

    def classify(self, items: list[Item]) -> Result:
        self.calls.append(items)
        return Result(
            {item.id: Answer(self.answers.get(item.merchant, UNKNOWN), "high") for item in items}, self.tokens
        )


STATEMENT = (
    "Data;Descrição;Valor\n"
    "01/11/2026;LIVRARIA CULTURA;-89,90\n"
    "02/11/2026;CLINICA SORRISO;-250,00\n"
    "03/11/2026;XPTO 12;-15,00\n"
    "04/11/2026;IFD*PIZZARIA;-60,00\n"  # built-in knowledge already knows: never asked
    "05/11/2026;Transferência enviada pelo Pix - MARIA S SOUZA - •••.123.456-•• - NU;-100,00\n"  # a person
    "06/11/2026;LIVRARIA CULTURA;-35,00\n"
)


def _category_id(browser: TestClient, name: str) -> int:
    return int(next(c["id"] for c in browser.get("/api/categories").json() if c["name"] == name))


def _imported(signed_in: SignedIn, content: str = STATEMENT) -> TestClient:
    browser = signed_in()
    import_file(browser, account(browser), content)
    return browser


@pytest.fixture
def fake(ai: AiSwitch) -> FakeClassifier:
    classifier = FakeClassifier()
    ai.classifier = classifier
    return classifier


def test_without_a_key_the_ai_is_off_and_nothing_breaks(signed_in: SignedIn) -> None:
    browser = _imported(signed_in)
    status = browser.get("/api/ai/status")
    assert status.status_code == 200, status.text
    assert status.json()["enabled"] is False
    result = browser.post("/api/ai/suggest").json()
    assert result == {
        "suggested": 0, "pending": 3, "message": "A categorização com IA não está ligada neste servidor."
    }  # fmt: skip


def test_only_uncategorized_merchants_are_asked_and_never_about_people(
    signed_in: SignedIn, fake: FakeClassifier
) -> None:
    browser = _imported(signed_in)
    result = browser.post("/api/ai/suggest").json()
    assert result["pending"] == 0
    asked = [item.merchant for item in fake.calls[0]]
    assert sorted(asked) == ["Clinica Sorriso", "Livraria Cultura", "Xpto 12"]
    assert all(item.outflow for item in fake.calls[0])
    # Two Livraria lines, one Clinica: three suggestions; XPTO is "unknown" and gets none.
    assert result["suggested"] == 3


def test_a_suggestion_is_not_a_category_until_accepted(signed_in: SignedIn, fake: FakeClassifier) -> None:
    browser = _imported(signed_in)
    browser.post("/api/ai/suggest")
    books = next(t for t in transactions(browser) if t["description_raw"] == "LIVRARIA CULTURA")
    assert books["category_id"] is None
    assert books["ai_category_id"] == _category_id(browser, "Cursos e livros")
    assert [t["description_raw"] for t in transactions(browser, uncategorized=True)].count(
        "LIVRARIA CULTURA"
    ) == 2

    groups = {g["merchant"]: g for g in browser.get("/api/ai/suggestions").json()}
    assert set(groups) == {"Livraria Cultura", "Clinica Sorriso"}
    assert len(groups["Livraria Cultura"]["transaction_ids"]) == 2
    assert groups["Livraria Cultura"]["total_cents"] == -12490


def test_accepting_with_a_rule_categorizes_the_next_statement_without_asking(
    signed_in: SignedIn, fake: FakeClassifier
) -> None:
    browser = _imported(signed_in)
    browser.post("/api/ai/suggest")
    group = next(g for g in browser.get("/api/ai/suggestions").json() if g["merchant"] == "Livraria Cultura")
    accepted = browser.post(
        "/api/ai/suggestions/accept", json={"transaction_ids": group["transaction_ids"], "create_rule": True}
    )
    assert accepted.json() == {"updated": 2}
    books = [t for t in transactions(browser) if t["description_raw"] == "LIVRARIA CULTURA"]
    assert {(t["category_id"], t["category_source"]) for t in books} == {(group["category_id"], "ai")}

    import_file(
        browser, account(browser, name="Outra"), "Data;Descrição;Valor\n10/12/2026;LIVRARIA CULTURA;-50,00\n"
    )
    newest = transactions(browser, q="livraria")[0]
    assert (newest["category_id"], newest["category_source"]) == (group["category_id"], "rule")
    assert len(fake.calls) == 1


def test_accepting_with_another_category_is_the_persons_choice(
    signed_in: SignedIn, fake: FakeClassifier
) -> None:
    browser = _imported(signed_in)
    browser.post("/api/ai/suggest")
    group = next(g for g in browser.get("/api/ai/suggestions").json() if g["merchant"] == "Clinica Sorriso")
    dentist = browser.post("/api/categories", json={"name": "Dentista", "type": "expense"}).json()["id"]
    browser.post(
        "/api/ai/suggestions/accept",
        json={"transaction_ids": group["transaction_ids"], "category_id": dentist},
    )
    clinic = transactions(browser, q="clinica")[0]
    assert (clinic["category_id"], clinic["category_source"]) == (dentist, "user")


def test_rejected_suggestions_are_not_made_again(signed_in: SignedIn, fake: FakeClassifier) -> None:
    browser = _imported(signed_in)
    browser.post("/api/ai/suggest")
    group = next(g for g in browser.get("/api/ai/suggestions").json() if g["merchant"] == "Clinica Sorriso")
    browser.post("/api/ai/suggestions/reject", json={"transaction_ids": group["transaction_ids"]})
    browser.post("/api/ai/suggest")
    assert "Clinica Sorriso" not in {g["merchant"] for g in browser.get("/api/ai/suggestions").json()}


def test_answers_are_shared_so_the_next_person_costs_nothing(
    signed_in: SignedIn, fake: FakeClassifier
) -> None:
    first = _imported(signed_in)
    first.post("/api/ai/suggest")
    second = _imported(signed_in)  # the same merchants
    # Filled from the cache during the import itself: no request to the model.
    assert len(fake.calls) == 1
    assert {g["merchant"] for g in second.get("/api/ai/suggestions").json()} == {
        "Livraria Cultura",
        "Clinica Sorriso",
    }


def test_fifty_merchants_per_request(signed_in: SignedIn, fake: FakeClassifier) -> None:
    lines = "".join(
        f"01/11/2026;LOJA NUMERO {chr(65 + i // 26)}{chr(65 + i % 26)};-10,00\n" for i in range(120)
    )
    browser = _imported(signed_in, "Data;Descrição;Valor\n" + lines)
    pending = [browser.post("/api/ai/suggest").json()["pending"] for _ in range(3)]
    assert pending == [70, 20, 0]
    assert [len(call) for call in fake.calls] == [50, 50, 20]


def test_the_daily_ceiling_is_enforced(
    signed_in: SignedIn, fake: FakeClassifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_daily_tokens_per_user", service.ESTIMATED_TOKENS_PER_BATCH)
    fake.tokens = service.ESTIMATED_TOKENS_PER_BATCH  # the first batch uses the whole day's allowance
    lines = "".join(f"01/11/2026;LOJA {chr(65 + i // 26)}{chr(65 + i % 26)};-10,00\n" for i in range(60))
    browser = _imported(signed_in, "Data;Descrição;Valor\n" + lines)
    assert browser.post("/api/ai/suggest").json()["pending"] == 10
    refused = browser.post("/api/ai/suggest").json()
    assert refused["message"] == "O limite diário de uso da IA foi atingido. Tente de novo amanhã."
    assert len(fake.calls) == 1
    assert browser.get("/api/ai/status").json()["used_today"] == service.ESTIMATED_TOKENS_PER_BATCH


def test_the_global_ceiling_covers_everyone(
    signed_in: SignedIn, fake: FakeClassifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_daily_tokens_global", service.ESTIMATED_TOKENS_PER_BATCH)
    fake.tokens = service.ESTIMATED_TOKENS_PER_BATCH
    _imported(signed_in).post("/api/ai/suggest")
    other = _imported(signed_in, "Data;Descrição;Valor\n01/11/2026;LOJA DIFERENTE;-10,00\n")
    assert other.post("/api/ai/suggest").json()["message"].startswith("O limite diário")


def test_reserving_is_all_or_nothing(db: Session) -> None:
    assert service._reserve(db, "global", 6_000, cap=10_000)
    assert not service._reserve(db, "global", 6_000, cap=10_000)
    assert service._reserve(db, "global", 4_000, cap=10_000)
    assert not service._reserve(db, "user:1", 20_000, cap=10_000)  # bigger than the cap on its own


class TestWhatLeavesForTheModel:
    @pytest.mark.parametrize(
        ("text", "masked"),
        [
            ("LOJA 12.345.678/0001-90", "LOJA [documento]"),
            ("CPF 123.456.789-00", "CPF [documento]"),
            ("Pix •••.123.456-•• ok", "Pix [documento] ok"),
            ("CONTA 1234567", "CONTA [número]"),
            ("Padaria 24h", "Padaria 24h"),
        ],
    )
    def test_documents_and_account_numbers_are_masked(self, text: str, masked: str) -> None:
        assert privacy.mask(text) == masked

    def test_lines_about_a_person_are_never_sent(self) -> None:
        assert privacy.about_a_person("Pix para Maria S Souza")
        assert privacy.about_a_person("Transferência de Acme Tecnologia Ltda")
        assert not privacy.about_a_person("Pixel Store")


class TestTheAnswer:
    def test_the_schema_limits_categories_to_the_taxonomy(self) -> None:
        properties: Any = schema()["properties"]
        category = properties["suggestions"]["items"]["properties"]["category"]
        assert set(category["enum"]) == {*SLUGS, UNKNOWN}

    def test_only_asked_ids_and_known_slugs_are_kept(self) -> None:
        text = (
            '{"suggestions": [{"id": 1, "category": "pets", "confidence": "high"},'
            '{"id": 2, "category": "invented", "confidence": "high"},'
            '{"id": 9, "category": "pets", "confidence": "high"}]}'
        )
        assert parse(text, {1, 2, 3}) == {1: Answer("pets", "high")}
        assert parse("not json", {1}) == {}


def _response(stop_reason: str, text: str) -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=900, output_tokens=50
    )
    return SimpleNamespace(
        stop_reason=stop_reason, usage=usage, content=[SimpleNamespace(type="text", text=text)]
    )


class TestTheRequest:
    def test_shape_of_the_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        classifier = AnthropicClassifier("sk-test", "claude-haiku-5-5")
        sent: dict[str, Any] = {}

        def create(**kwargs: Any) -> SimpleNamespace:
            sent.update(kwargs)
            return _response(
                "end_turn", '{"suggestions": [{"id": 1, "category": "pets", "confidence": "high"}]}'
            )

        monkeypatch.setattr(classifier.client.messages, "create", create)
        result = classifier.classify([Item(1, "Pet Feliz", True), Item(2, "Salário ACME", False)])
        assert sent["model"] == "claude-haiku-5-5"
        assert sent["output_config"]["effort"] == "low"
        assert sent["output_config"]["format"]["type"] == "json_schema"
        assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert sent["messages"][0]["content"] == "1. Pet Feliz (gasto)\n2. Salário ACME (receita)"
        assert result == Result({1: Answer("pets", "high")}, 1_050)

    def test_a_refusal_suggests_nothing_but_still_counts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        classifier = AnthropicClassifier("sk-test", "claude-haiku-5-5")
        monkeypatch.setattr(classifier.client.messages, "create", lambda **_: _response("refusal", ""))
        assert classifier.classify([Item(1, "X", True)]) == Result({}, 1_050)
