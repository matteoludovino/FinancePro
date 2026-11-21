"""Which column is what, how to read it, and how it was decided: a bank preset, a profile saved from a
previous import, or detection from header names and content."""

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from financepro.accounts.models import AccountKind
from financepro.importers.parsing import (
    DateFormat,
    Decimals,
    ParseError,
    detect_date_format,
    detect_decimals,
    parse_cents,
)
from financepro.importers.reader import Table
from financepro.text import canonical


class Sign(StrEnum):
    AS_IS = "as_is"
    # Card statements list purchases as positive numbers; stored, a purchase is money leaving (negative).
    INVERTED = "inverted"


class Mapping(BaseModel):
    date: int = Field(ge=0)
    description: list[int] = Field(min_length=1)
    amount: int | None = Field(default=None, ge=0)
    debit: int | None = Field(default=None, ge=0)
    credit: int | None = Field(default=None, ge=0)
    external_id: int | None = Field(default=None, ge=0)
    date_format: DateFormat
    decimals: Decimals
    sign: Sign = Sign.AS_IS
    # Which date the file gives installments 2..n: the statement's ("billing") or the purchase's.
    installment_dates: Literal["auto", "billing", "purchase"] = "auto"

    @model_validator(mode="after")
    def one_way_to_read_amounts(self) -> Self:
        if (self.amount is None) == (self.debit is None and self.credit is None):
            raise ValueError("Indique a coluna de valor, ou as de débito e crédito.")
        return self

    def columns(self) -> set[int]:
        used = {self.date, *self.description, self.amount, self.debit, self.credit, self.external_id}
        return {c for c in used if c is not None}


@dataclass(frozen=True)
class Detection:
    mapping: Mapping | None
    detected_by: str  # "preset:<name>", "profile" or "auto"
    label: str
    warnings: list[str] = field(default_factory=list)


def signature(table: Table) -> str:
    """Identifies a file layout (not its content): same bank, same export, same signature."""
    key = table.delimiter + "|" + "|".join(canonical(cell) for cell in table.header)
    return hashlib.sha256(key.encode()).hexdigest()


# Presets follow the public format of Nubank's exports. They were not checked against real files; anything
# they get wrong is fixed in the preview's mapping, and the fix is remembered as a profile.
@dataclass(frozen=True)
class Preset:
    name: str
    label: str
    header: tuple[str, ...]
    mapping: Mapping


PRESETS: tuple[Preset, ...] = (
    Preset(
        "nubank_conta",
        "Nubank — conta",
        ("data", "valor", "identificador", "descricao"),
        Mapping(
            date=0, amount=1, external_id=2, description=[3], date_format=DateFormat.BR, decimals=Decimals.DOT
        ),
    ),
    Preset(
        "nubank_cartao",
        "Nubank — cartão de crédito",
        ("date", "title", "amount"),
        Mapping(
            date=0,
            description=[1],
            amount=2,
            date_format=DateFormat.ISO,
            decimals=Decimals.DOT,
            sign=Sign.INVERTED,
        ),
    ),
    Preset(
        "nubank_cartao",
        "Nubank — cartão de crédito",
        ("date", "category", "title", "amount"),
        Mapping(
            date=0,
            description=[2],
            amount=3,
            date_format=DateFormat.ISO,
            decimals=Decimals.DOT,
            sign=Sign.INVERTED,
        ),
    ),
)


def find_preset(table: Table) -> Preset | None:
    header = tuple(canonical(cell) for cell in table.header)
    return next((preset for preset in PRESETS if preset.header == header), None)


_ROLES: dict[str, re.Pattern[str]] = {
    "date": re.compile(r"^(data|date|dt)\b(?!.*(compensa|vencimento))"),
    "description": re.compile(
        r"^(descri|description|historico|title|titulo|lancamento$|estabelecimento|detalhe|memo)"
    ),
    "amount": re.compile(r"^(valor|amount|value|quantia)\b(?!.*(debito|credito))"),
    "debit": re.compile(r"^(debito|saida|valor debito)"),
    "credit": re.compile(r"^(credito|entrada|valor credito)"),
    "external_id": re.compile(r"^(identificador|id|codigo|fitid|id transacao|numero documento)$"),
}


def _clean_header(cell: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", canonical(cell)).strip()


def _column(table: Table, index: int) -> list[str]:
    return [row[index] for row in table.rows]


def detect(table: Table, account_kind: AccountKind) -> Detection:
    """Best effort from header names, then from content. Never silent: what wasn't found is a warning and
    the preview asks for it."""
    warnings: list[str] = []
    found: dict[str, list[int]] = {role: [] for role in _ROLES}
    for index, cell in enumerate(table.header):
        name = _clean_header(cell)
        for role, pattern in _ROLES.items():
            if pattern.search(name):
                found[role].append(index)
                break

    date_col = next(iter(found["date"]), None)
    if date_col is None:
        date_col = next((i for i in range(len(table.header)) if detect_date_format(_column(table, i))), None)
    date_format = detect_date_format(_column(table, date_col)) if date_col is not None else None

    amount_col = next(iter(found["amount"]), None)
    debit_col, credit_col = next(iter(found["debit"]), None), next(iter(found["credit"]), None)
    if amount_col is None and debit_col is None and credit_col is None:
        amount_col = next((i for i in range(len(table.header)) if i != date_col and _numeric(table, i)), None)
    amount_cells = [
        c for col in (amount_col, debit_col, credit_col) if col is not None for c in _column(table, col)
    ]
    decimals = detect_decimals([c for c in amount_cells if c.strip()])
    if decimals is None:
        warnings.append(
            "Os valores misturam vírgula e ponto como separador decimal; confira a coluna de valor."
        )
        decimals = Decimals.COMMA

    description_cols = found["description"] or _longest_text(table, exclude={date_col, amount_col})
    no_amount = amount_col is None and debit_col is None and credit_col is None
    if date_col is None or date_format is None:
        warnings.append("Não reconheci a coluna de data.")
    if no_amount:
        warnings.append("Não reconheci a coluna de valor.")
    if not description_cols:
        warnings.append("Não reconheci a coluna de descrição.")
    if date_col is None or date_format is None or no_amount or not description_cols:
        return Detection(None, "auto", "Formato não reconhecido", warnings)

    mapping = Mapping(
        date=date_col,
        description=description_cols,
        amount=amount_col,
        debit=debit_col if amount_col is None else None,
        credit=credit_col if amount_col is None else None,
        external_id=next(iter(found["external_id"]), None),
        date_format=date_format,
        decimals=decimals,
        sign=_guess_sign(table, amount_col, decimals, account_kind),
    )
    if mapping.sign is Sign.INVERTED:
        warnings.append(
            "Neste cartão as compras vêm como valores positivos; elas serão gravadas como saídas."
        )
    return Detection(mapping, "auto", "Detectado pelas colunas", warnings)


def _numeric(table: Table, index: int) -> bool:
    cells = [c for c in _column(table, index) if c.strip()]
    decimals = detect_decimals(cells) or Decimals.COMMA
    try:
        for cell in cells:
            parse_cents(cell, decimals)
    except ParseError:
        return False
    return bool(cells)


def _longest_text(table: Table, exclude: set[int | None]) -> list[int]:
    candidates = [i for i in range(len(table.header)) if i not in exclude and not _numeric(table, i)]
    if not candidates:
        return []
    return [max(candidates, key=lambda i: sum(len(c) for c in _column(table, i)))]


def _guess_sign(table: Table, amount_col: int | None, decimals: Decimals, account_kind: AccountKind) -> Sign:
    if account_kind is not AccountKind.CREDIT_CARD or amount_col is None:
        return Sign.AS_IS
    values = []
    for cell in _column(table, amount_col):
        try:
            values.append(parse_cents(cell, decimals))
        except ParseError:
            continue
    positive = sum(v > 0 for v in values)
    return Sign.INVERTED if values and positive / len(values) > 0.6 else Sign.AS_IS
