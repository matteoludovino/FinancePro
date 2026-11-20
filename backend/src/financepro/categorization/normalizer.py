"""From a bank's description to a merchant people recognize.

"IFD*BURGER KING 4421 SAO PAULO BR" → iFood; "Transferência enviada pelo Pix - MARIA S SOUZA - •••.123.456-••
- NU PAGAMENTOS" → "Pix para Maria S Souza". The result feeds rules, the AI and reports. It never feeds
deduplication: the normalizer improves over time, and fingerprints must not move when it does.
"""

import re
import unicodedata
from dataclasses import dataclass

from financepro.categorization import merchants


@dataclass(frozen=True)
class Merchant:
    name: str
    # A taxonomy slug suggested by built-in knowledge, if any.
    slug: str | None = None


# Nubank account lines (public format; see the README on bank presets).
_PIX_SENT = re.compile(r"^transferencia enviada pelo pix - (.+?)(?: - |$)")
_PIX_RECEIVED = re.compile(r"^transferencia recebida pelo pix - (.+?)(?: - |$)")
_TED_SENT = re.compile(r"^transferencia enviada - (.+?)(?: - |$)")
_TED_RECEIVED = re.compile(r"^transferencia recebida - (.+?)(?: - |$)")
_BOLETO = re.compile(r"^pagamento de boleto efetuado - (.+)$")
_DEBIT = re.compile(r"^compra no debito(?: via nupay)? - (.+)$")
_BILL = re.compile(r"^(?:pagamento (?:de fatura|recebido|efetuado)|pagamento da fatura)\b")

_INSTALLMENT = re.compile(
    r"\s*(?:-\s*)?(?:parcela|parc\.?)\s*\d{1,2}\s*(?:/|de)\s*\d{1,2}\s*$|\s+\d{1,2}/\d{1,2}$"
)
# Card-processor prefixes: "PAG*", "MP*", "SUMUP *", "EC *", "DL*GOOGLE".
_GATEWAY = re.compile(
    r"^(?:pag|pagseguro|pg|mp|mercadopago|sumup|ec|picpay|ebn|dl|paypal|pp|zp|cielo|stone|ame|pagarme)\s*\*\s*"
)
_PLACE = re.compile(
    r"(?:\s+(?:sao paulo|rio de janeiro|belo horizonte|curitiba|porto alegre|brasilia|salvador|recife"
    r"|fortaleza|campinas|osasco|barueri|santo andre|guarulhos|niteroi|sp|rj|mg|pr|rs|br|bra|brasil))+\s*$"
)
_LONG_NUMBERS = re.compile(r"\b\d{4,}\b")
_NOISE = re.compile(r"[*#_]+")
_SPACES = re.compile(r"\s+")
_SMALL_WORDS = {"de", "da", "do", "das", "dos", "e", "em", "com"}


class _Text:
    """The description twice, kept aligned: `folded` (lowercase, no accents) is what patterns match, and
    `shown` (the original letters) is what is displayed. Folding maps each character to exactly one, so
    a span found in one is the same span in the other."""

    def __init__(self, description: str) -> None:
        self.shown = description
        self.folded = "".join(_fold(ch) for ch in description)
        self.collapse()

    def sub(self, pattern: re.Pattern[str], repl: str = " ") -> None:
        folded, shown, last = [], [], 0
        for match in pattern.finditer(self.folded):
            folded += [self.folded[last : match.start()], repl]
            shown += [self.shown[last : match.start()], repl]
            last = match.end()
        self.folded = "".join([*folded, self.folded[last:]])
        self.shown = "".join([*shown, self.shown[last:]])

    def collapse(self) -> None:
        self.sub(_SPACES)
        start = len(self.folded) - len(self.folded.lstrip(" -.,/"))
        end = len(self.folded.rstrip(" -.,/"))
        self.folded, self.shown = self.folded[start:end], self.shown[start:end]

    def slice(self, start: int, end: int) -> _Text:
        part = _Text("")
        part.folded, part.shown = self.folded[start:end], self.shown[start:end]
        part.collapse()
        return part


def _fold(ch: str) -> str:
    base = unicodedata.normalize("NFKD", ch)[:1] or ch
    return base.lower()


def _title(text: str) -> str:
    """Shouting (ALL CAPS) or all-lowercase text becomes Title Case; text a person already cased, like
    "IOF de compra internacional", keeps its casing."""
    if not (text.isupper() or text.islower()):
        return text[:1].upper() + text[1:]
    words = text.lower().split()
    return " ".join(w if i and w in _SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _clean(text: _Text) -> str:
    for pattern in (_INSTALLMENT, _GATEWAY, _NOISE, _LONG_NUMBERS):
        text.sub(pattern)
        text.collapse()
    text.sub(_PLACE, "")
    text.collapse()
    return text.shown


def merchant_of(description: str) -> Merchant:
    text = _Text(description)
    if _BILL.match(text.folded):
        return Merchant("Pagamento de fatura")
    named = (
        (_PIX_SENT, "Pix para"),
        (_PIX_RECEIVED, "Pix de"),
        (_TED_SENT, "Transferência para"),
        (_TED_RECEIVED, "Transferência de"),
    )
    for pattern, label in named:
        if found := pattern.match(text.folded):
            return Merchant(f"{label} {_title(text.slice(*found.span(1)).shown)}"[:60])
    for pattern in (_BOLETO, _DEBIT):
        if found := pattern.match(text.folded):
            text = text.slice(*found.span(1))
            break
    known = merchants.find(text.folded)
    if known and known.name:
        return Merchant(known.name, known.slug)
    name = _title(_clean(text))[:60] or " ".join(description.split())[:60]
    return Merchant(name, known.slug if known else None)
