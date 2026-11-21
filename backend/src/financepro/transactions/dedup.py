"""Recognizing a transaction already imported (ADR 0003).

The fingerprint hashes the date, the amount, the canonical description and the occurrence number: the
n-th identical line of a file. Two R$ 5 coffees at the same bakery on the same day are two transactions
(n = 0 and 1); importing an overlapping statement matches them one to one instead of collapsing them.
It never uses the normalized merchant, which changes as the normalizer improves.
"""

import hashlib
from collections import Counter
from datetime import date

from financepro.text import canonical

FP_VERSION = 1


def fingerprint(day: date, amount_cents: int, description: str, occurrence_n: int) -> str:
    key = f"v{FP_VERSION}|{day.isoformat()}|{amount_cents}|{canonical(description)}|{occurrence_n}"
    return hashlib.sha256(key.encode()).hexdigest()


class Occurrences:
    """Numbers identical lines in file order: 0 for the first, 1 for the second..."""

    def __init__(self) -> None:
        self._seen: Counter[tuple[date, int, str]] = Counter()

    def next(self, day: date, amount_cents: int, description: str) -> int:
        key = (day, amount_cents, canonical(description))
        n = self._seen[key]
        self._seen[key] += 1
        return n
