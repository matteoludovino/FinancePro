"""Months as the first day of the month ("2026-11" ↔ date(2026, 11, 1))."""

import re
from datetime import date

from fastapi import HTTPException

from financepro.cards.installments import add_months

_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


def parse(month: str) -> date:
    found = _MONTH.match(month)
    if not found or not 1 <= int(found.group(2)) <= 12:
        raise HTTPException(status_code=422, detail="Mês inválido; use AAAA-MM.")
    return date(int(found.group(1)), int(found.group(2)), 1)


def following(month: date) -> date:
    return add_months(month, 1)


def label(month: date) -> str:
    return f"{month:%Y-%m}"
