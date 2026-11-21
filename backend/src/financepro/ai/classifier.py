"""Asking Claude which category a merchant belongs to.

One request classifies up to 50 merchants. The answer is constrained by a JSON schema whose category
field is an enum of the fixed taxonomy slugs plus "unknown": the model can't invent a category, and the
schema is the same for everyone, so it is cached by the API. Each item is referred to by a short number;
an item missing from the answer simply stays uncategorized.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from financepro.categories.taxonomy import EXPENSES, INCOME, SLUGS

Confidence = Literal["low", "medium", "high"]
UNKNOWN = "unknown"
BATCH_SIZE = 50
# Bump when the taxonomy or the prompt changes: cached answers keyed by the old values stop being used.
TAXONOMY_VERSION = 1
PROMPT_VERSION = 1


@dataclass(frozen=True)
class Item:
    id: int
    merchant: str
    outflow: bool


@dataclass(frozen=True)
class Answer:
    slug: str
    confidence: Confidence


@dataclass(frozen=True)
class Result:
    answers: dict[int, Answer]
    tokens: int


class Classifier(Protocol):
    model: str

    def classify(self, items: list[Item]) -> Result: ...


class AiUnavailableError(RuntimeError):
    """The model couldn't be reached or declined; the items stay uncategorized and the person can retry."""


def _taxonomy() -> str:
    lines = []
    for kind, roots in (("gasto", EXPENSES), ("receita", INCOME)):
        for root in roots:
            lines.append(f"- {root.slug}: {root.name} ({kind})")
            lines.extend(f"  - {child.slug}: {root.name} › {child.name}" for child in root.children)
    return "\n".join(lines)


# The instructions live in prompt.md (Portuguese: the merchants are Brazilian). They and the taxonomy form
# the cached prefix of every request, so nothing in them may vary per call.
SYSTEM = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8").format(taxonomy=_taxonomy())


class _Suggestion(BaseModel):
    id: int
    category: str
    confidence: Confidence


class _Answer(BaseModel):
    suggestions: list[_Suggestion]


def schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "category": {"type": "string", "enum": [*sorted(SLUGS), UNKNOWN]},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["id", "category", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["suggestions"],
        "additionalProperties": False,
    }


def render(items: list[Item]) -> str:
    return "\n".join(
        f"{item.id}. {item.merchant} ({'gasto' if item.outflow else 'receita'})" for item in items
    )


def parse(text: str, asked: set[int]) -> dict[int, Answer]:
    """Keeps only answers for ids that were asked, with a known slug; anything else is dropped."""
    try:
        answer = _Answer.model_validate_json(text)
    except ValidationError:
        return {}
    return {
        s.id: Answer(s.category, s.confidence)
        for s in answer.suggestions
        if s.id in asked and (s.category in SLUGS or s.category == UNKNOWN)
    }


class AnthropicClassifier:
    def __init__(self, api_key: str, model: str) -> None:
        # Short timeout and one retry: the request is per click, a person is waiting.
        self.client = anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=1)
        self.model = model

    def classify(self, items: list[Item]) -> Result:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                # The instructions and taxonomy are the same on every call: cached after the first.
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": render(items)}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema()}},
            )
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError) as error:
            raise AiUnavailableError(str(error)) from error
        usage = response.usage
        tokens = (
            usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0)
            + usage.output_tokens
        )
        if response.stop_reason != "end_turn":
            # A refusal or a cut-off answer: nothing is trusted, the tokens still count.
            return Result({}, tokens)
        text = next((block.text for block in response.content if block.type == "text"), "")
        return Result(parse(text, {item.id for item in items}), tokens)
