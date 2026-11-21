from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from financepro.importers.parsing import (
    DateFormat,
    Decimals,
    ParseError,
    detect_date_format,
    detect_decimals,
    parse_cents,
)
from financepro.transactions.dedup import fingerprint


def _brazilian(cents: int) -> str:
    units, rest = divmod(abs(cents), 100)
    grouped = f"{units:,}".replace(",", ".")
    return f"{'-' if cents < 0 else ''}{grouped},{rest:02d}"


@given(st.integers(min_value=-(10**11), max_value=10**11).filter(bool))
def test_brazilian_amounts_round_trip(cents: int) -> None:
    assert parse_cents(_brazilian(cents), Decimals.COMMA) == cents


@given(st.integers(min_value=-(10**11), max_value=10**11).filter(bool))
def test_dot_decimal_amounts_round_trip(cents: int) -> None:
    assert parse_cents(f"{cents / 100:.2f}", Decimals.DOT) == cents


@pytest.mark.parametrize(
    ("cell", "decimals", "cents"),
    [
        ("(12,34)", Decimals.COMMA, -1234),
        ("12,34-", Decimals.COMMA, -1234),
        ("12,34 D", Decimals.COMMA, -1234),
        ("12,34 C", Decimals.COMMA, 1234),
        ("- R$ 9,90", Decimals.COMMA, -990),
        ("R$ 1.000", Decimals.COMMA, 100000),
        ("1,234.50", Decimals.DOT, 123450),
        ("+15", Decimals.DOT, 1500),
    ],
)
def test_the_ways_banks_write_amounts(cell: str, decimals: Decimals, cents: int) -> None:
    assert parse_cents(cell, decimals) == cents


@pytest.mark.parametrize("cell", ["", "abc", "1,234", "12.345,6789", "5,5,5"])
def test_what_is_not_an_amount(cell: str) -> None:
    with pytest.raises(ParseError):
        parse_cents(cell, Decimals.COMMA)


def test_the_decimal_separator_is_decided_by_the_column() -> None:
    # "1.234" alone is ambiguous; next to "10,50" it is one thousand two hundred and thirty-four.
    assert detect_decimals(["1.234", "10,50"]) is Decimals.COMMA
    assert detect_decimals(["-45.90", "12.00", "3"]) is Decimals.DOT
    assert detect_decimals(["1.234", "10"]) is Decimals.COMMA  # Brazilian default
    assert detect_decimals(["1,5", "2.50"]) is None  # contradictory: the person decides


def test_two_digit_years_are_not_read_as_year_26() -> None:
    assert detect_date_format(["03/11/26", "31/12/26"]) is DateFormat.BR_SHORT
    assert detect_date_format(["03/11/2026", "31/02/2026", "01/12/2026"]) is DateFormat.BR


def test_fingerprints_are_pinned() -> None:
    """Changing how fingerprints are computed would make every re-import duplicate a whole history.
    A change must bump FP_VERSION and ship a backfill; this test makes that impossible to miss."""
    assert fingerprint(date(2026, 11, 3), -500, "PADARIA  Real", 0) == fingerprint(
        date(2026, 11, 3), -500, "padaria real", 0
    )
    assert fingerprint(date(2026, 11, 3), -500, "PADARIA REAL", 0) == (
        # sha256("v1|2026-11-03|-500|padaria real|0")
        "d44f57265eb344964127a711f2707cd0863bd513cdb4c02fece816c6c02de9cc"
    )
