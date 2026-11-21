"""Cell → value. Dates and amounts are parsed by format decided for the whole column, never per cell:
"1.234" alone could be one thousand or one real and 234 thousandths; a column with "1.234,56" in it
settles it."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class DateFormat(StrEnum):
    BR = "%d/%m/%Y"
    BR_SHORT = "%d/%m/%y"
    ISO = "%Y-%m-%d"
    BR_DASH = "%d-%m-%Y"
    BR_DOT = "%d.%m.%Y"


class Decimals(StrEnum):
    COMMA = ","  # 1.234,56
    DOT = "."  # 1234.56 or 1,234.56


class ParseError(ValueError):
    pass


# The shape of each format, checked first: strptime alone reads "03/11/26" as the year 26 under %Y.
_DATE_SHAPES = {
    DateFormat.BR: re.compile(r"\d{1,2}/\d{1,2}/\d{4}"),
    DateFormat.BR_SHORT: re.compile(r"\d{1,2}/\d{1,2}/\d{2}"),
    DateFormat.ISO: re.compile(r"\d{4}-\d{2}-\d{2}"),
    DateFormat.BR_DASH: re.compile(r"\d{1,2}-\d{1,2}-\d{4}"),
    DateFormat.BR_DOT: re.compile(r"\d{1,2}\.\d{1,2}\.\d{4}"),
}


def parse_date(cell: str, fmt: DateFormat) -> date:
    # A trailing time ("2026-11-03 14:22:00", "03/11/2026 14:22") is dropped: the day is what counts.
    text = cell.strip().split(" ")[0].split("T")[0]
    if not _DATE_SHAPES[fmt].fullmatch(text):
        raise ParseError(f"Data inválida: “{cell.strip()}”.")
    try:
        return datetime.strptime(text, fmt.value).date()  # noqa: DTZ007  # a calendar date, no time zone
    except ValueError:
        raise ParseError(f"Data inválida: “{cell.strip()}”.") from None


def detect_date_format(cells: list[str]) -> DateFormat | None:
    """The format that reads the most cells, if it reads more than half: one bad date (31/02) shouldn't
    hide a whole column; that line is reported as an error instead."""
    values = [c for c in cells if c.strip()]
    best, best_count = None, 0
    for fmt in (DateFormat.ISO, DateFormat.BR, DateFormat.BR_DASH, DateFormat.BR_DOT, DateFormat.BR_SHORT):
        count = 0
        for value in values:
            try:
                parse_date(value, fmt)
            except ParseError:
                continue
            count += 1
        if count > best_count:
            best, best_count = fmt, count
    return best if values and best_count * 2 > len(values) else None


_NEGATIVE_MARKS = re.compile(r"^\((.*)\)$|^-(.*)$|^(.*)-$|^(.*?)\s*[dD]$")
_POSITIVE_MARK = re.compile(r"^(.*?)\s*[cC]$")
_CLEAN = re.compile(r"[R$\s ]")


def _strip_sign(cell: str) -> tuple[str, int]:
    text = _CLEAN.sub("", cell.strip()) if cell.strip() else ""
    if found := _NEGATIVE_MARKS.match(text):
        return next(group for group in found.groups() if group is not None).strip("-"), -1
    if found := _POSITIVE_MARK.match(text):
        return found.group(1), 1
    return text.lstrip("+"), 1


def parse_cents(cell: str, decimals: Decimals) -> int:
    """'-1.234,56' → -123456, with the column's decimal separator. Also '(12,34)', '12,34-', '12,34 D'."""
    number, sign = _strip_sign(cell)
    if not number:
        raise ParseError("Valor vazio.")
    thousands = "." if decimals is Decimals.COMMA else ","
    normalized = number.replace(thousands, "").replace(decimals.value, ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", normalized):
        raise ParseError(f"Valor inválido: “{cell.strip()}”.")
    try:
        cents = Decimal(normalized) * 100
    except InvalidOperation:
        raise ParseError(f"Valor inválido: “{cell.strip()}”.") from None
    return sign * int(cents)


def detect_decimals(cells: list[str]) -> Decimals | None:
    """Votes from cells that are unambiguous: two digits after a comma means comma decimals, after a dot
    means dot decimals. Neither (whole numbers, '1.234') defaults to the Brazilian comma. Both: None."""
    comma = dot = False
    for cell in cells:
        number, _ = _strip_sign(cell)
        if re.search(r",\d{1,2}$", number):
            comma = True
        elif re.search(r"\.\d{1,2}$", number):
            dot = True
    if comma and dot:
        return None
    return Decimals.DOT if dot else Decimals.COMMA
