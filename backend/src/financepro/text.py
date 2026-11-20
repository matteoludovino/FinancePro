"""Canonical text: what descriptions are compared by.

Lowercase, accents removed, whitespace collapsed; digits and punctuation kept. Deduplication fingerprints
are built from this form, so it must not change once data exists (fingerprints carry a version).
"""

import unicodedata


def canonical(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(without_accents.casefold().split())
