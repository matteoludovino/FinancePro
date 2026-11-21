"""Bytes → a table of strings: encoding, delimiter and where the header row is.

Brazilian bank exports vary: UTF-8 with or without a BOM, or Windows-1252; `;` (Excel in pt-BR uses the
comma as decimal separator) or `,`; and some put a title block ("Extrato Conta Corrente", period, balance)
before the real header. Nothing here knows about any bank.
"""

import csv
import io
import re
from dataclasses import dataclass

from financepro.text import canonical

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000

# Words that appear in a statement's header row; the title block above it rarely has two of them.
HEADER_WORDS = {
    "data", "date", "dt", "valor", "amount", "value", "quantia", "descricao", "description", "historico",
    "title", "titulo", "lancamento", "estabelecimento", "identificador", "id", "debito", "credito", "saldo",
    "categoria", "category", "documento", "entrada", "saida", "memo", "detalhes",
}  # fmt: skip


class ReadError(ValueError):
    """A file that can't be read as a table; the message is shown to the person as is."""


@dataclass(frozen=True)
class Table:
    encoding: str
    delimiter: str
    header_row: int  # 0-based line of the header in the file
    header: list[str]
    rows: list[list[str]]  # data rows only, each padded to the header's width


def decode(data: bytes) -> tuple[str, str]:
    if not data.strip():
        raise ReadError("O arquivo está vazio.")
    if b"\x00" in data[:4096]:
        raise ReadError("Isto não parece um arquivo CSV (é binário). Exporte o extrato em CSV.")
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        # Windows-1252 decodes any byte sequence; it is what Excel in Portuguese saves as "CSV".
        return data.decode("cp1252", errors="replace"), "cp1252"


def _sniff_delimiter(lines: list[str]) -> str:
    """The delimiter whose count is the same, and highest, on the most lines."""
    best, best_score = ",", -1
    for delimiter in (";", ",", "\t", "|"):
        counts = [len(next(csv.reader([line], delimiter=delimiter))) for line in lines if line.strip()]
        if not counts:
            continue
        widest = max(set(counts), key=lambda width: (counts.count(width), width))
        score = counts.count(widest) * (widest > 1) * widest
        if score > best_score:
            best, best_score = delimiter, score
    return best


_DATE_LIKE = re.compile(r"^\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})")


def _has_date(cells: list[str]) -> bool:
    return any(_DATE_LIKE.match(cell) for cell in cells)


def _named_like_header(cells: list[str]) -> bool:
    words = {canonical(cell).strip(" :") for cell in cells}
    known = len(words & HEADER_WORDS)
    return known >= 2 or (known >= 1 and not _has_date(cells) and all(c.strip()[:1].isalpha() for c in cells))


def _find_header(rows: list[list[str]]) -> int | None:
    """The header is the row right before the data: a row of names followed, within a few rows, by rows
    with dates. Prefer rows named like a statement header; fall back to any row of names before dates
    (a layout we don't know, mapped by hand in the preview)."""

    def followed_by_data(i: int) -> bool:
        return any(_has_date(row) for row in rows[i + 1 : i + 6])

    candidates = [i for i, row in enumerate(rows[:20]) if len(row) >= 2 and followed_by_data(i)]
    named = next((i for i in candidates if _named_like_header(rows[i])), None)
    if named is not None:
        return named
    return next((i for i in candidates if not _has_date(rows[i]) and all(c.strip() for c in rows[i])), None)


def read_table(data: bytes) -> Table:
    if len(data) > MAX_BYTES:
        raise ReadError("O arquivo passa de 2 MB. Exporte um período menor.")
    text, encoding = decode(data)
    lines = text.splitlines()
    delimiter = _sniff_delimiter(lines[:50])
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header_row = _find_header(rows)
    if header_row is None:
        raise ReadError("Não encontrei a linha de cabeçalho (com nomes como Data, Descrição e Valor).")
    header = [cell.strip() for cell in rows[header_row]]
    width = len(header)
    data_rows = [
        (row + [""] * width)[:width] for row in rows[header_row + 1 :] if any(cell.strip() for cell in row)
    ]
    if not data_rows:
        raise ReadError("O arquivo tem cabeçalho, mas nenhum lançamento.")
    if len(data_rows) > MAX_ROWS:
        raise ReadError(
            f"O arquivo tem {len(data_rows)} linhas; o limite é {MAX_ROWS}. Exporte um período menor."
        )
    return Table(encoding, delimiter, header_row, header, data_rows)
