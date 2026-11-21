"""A fictional person's statements, deterministic for a given seed and "today".

The same generator feeds the tests, the sample CSVs the site offers and the public demo, so all three
describe the same life: salary, rent, a savings box, utilities, Pix to friends, a credit card with
delivery, rides, subscriptions, installments and the bill paid from the checking account. Everything is
fictional: names, companies, documents (masked like the bank masks them) and amounts.
"""

import itertools
import random
import uuid
import zlib
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Line:
    date: date
    amount_cents: int  # signed, as the account sees it: negative leaves the account
    description: str
    external_id: str | None = None


def _months_back(today: date, months: int) -> list[date]:
    """First day of each month, oldest first, ending with today's month."""
    firsts = []
    year, month = today.year, today.month
    for _ in range(months):
        firsts.append(date(year, month, 1))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return firsts[::-1]


def _day(first: date, day: int, today: date) -> date | None:
    try:
        result = first.replace(day=day)
    except ValueError:
        result = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return result if result <= today else None


def _cents(rng: random.Random, low: float, high: float) -> int:
    return round(rng.uniform(low, high) * 100)


PIX_FRIENDS = ["MARIA S SOUZA", "JOAO P LIMA", "BEATRIZ COSTA", "RAFAEL M ALVES", "LUCAS FERREIRA"]
BANK_TAIL = "NU PAGAMENTOS - IP (0260) Agência: 1 Conta: {}-{}"


def _pix(rng: random.Random, sent: bool, name: str) -> str:
    # The same person always has the same (masked) document and account, as in a real statement.
    digits = f"{zlib.crc32(name.encode()):010d}"
    masked = f"•••.{digits[:3]}.{digits[3:6]}-••"
    tail = BANK_TAIL.format(digits[3:10], digits[0])
    verb = "enviada" if sent else "recebida"
    return f"Transferência {verb} pelo Pix - {name} - {masked} - {tail}"


def checking(
    today: date, months: int = 6, seed: int = 7, card_bills: dict[date, int] | None = None
) -> list[Line]:
    """The checking account. `card_bills` maps a due date to the bill total paid that day."""
    rng = random.Random(seed)
    lines: list[Line] = []

    def add(day: date | None, cents: int, description: str) -> None:
        if day is not None:
            lines.append(Line(day, cents, description, str(uuid.UUID(int=rng.getrandbits(128), version=4))))

    for first in _months_back(today, months):
        add(
            _day(first, 5, today),
            685000,
            "Transferência Recebida - ACME TECNOLOGIA LTDA - 12.345.678/0001-90 - "
            "ITAÚ UNIBANCO S.A. (0341) Agência: 1500 Conta: 12345-6",
        )
        add(_day(first, 6, today), -220000, _pix(rng, True, "IMOBILIARIA LAR FELIZ LTDA"))
        add(_day(first, 6, today), -50000, "Aplicação RDB")
        add(
            _day(first, rng.randint(8, 12), today),
            -_cents(rng, 170, 260),
            "Pagamento de boleto efetuado - ENEL DISTRIBUICAO SAO PAULO",
        )
        add(
            _day(first, rng.randint(12, 16), today),
            -_cents(rng, 85, 125),
            "Pagamento de boleto efetuado - SABESP",
        )
        add(_day(first, 15, today), -11999, "Pagamento de boleto efetuado - VIVO FIBRA")
        for _ in range(rng.randint(2, 4)):
            add(
                _day(first, rng.randint(1, 28), today),
                -_cents(rng, 30, 250),
                _pix(rng, True, rng.choice(PIX_FRIENDS)),
            )
        if rng.random() < 0.6:
            add(
                _day(first, rng.randint(1, 28), today),
                _cents(rng, 40, 300),
                _pix(rng, False, rng.choice(PIX_FRIENDS)),
            )
        for _ in range(rng.randint(3, 6)):
            shop = rng.choice(["PADARIA REAL", "SUPERMERCADO DIA", "FARMACIA POPULAR", "ACOUGUE BOM CORTE"])
            add(_day(first, rng.randint(1, 28), today), -_cents(rng, 8, 90), f"Compra no débito - {shop}")
        if rng.random() < 0.3:
            add(_day(first, rng.randint(20, 27), today), 30000, "Resgate RDB")
    for due, total in (card_bills or {}).items():
        if due <= today:
            add(due, -total, "Pagamento de fatura")
    return sorted(lines, key=lambda line: line.date)


CARD_SHOPS: list[tuple[str, float, float, int, int]] = [
    # description, min, max, times per month (min, max)
    ("IFD*IFOOD", 28, 95, 6, 11),
    ("UBER *TRIP", 12, 48, 5, 10),
    ("Carrefour", 120, 420, 1, 3),
    ("Pao de Acucar", 60, 260, 1, 3),
    ("Drogasil", 25, 140, 0, 2),
    ("Posto Shell", 150, 260, 1, 2),
    ("Restaurante Sabor da Casa", 45, 160, 1, 4),
    ("Amazon", 40, 300, 0, 2),
    ("Starbucks", 18, 35, 0, 3),
]
SUBSCRIPTIONS = [("Netflix.com", 5590), ("Spotify", 2190), ("Smart Fit", 12990)]
# description, installment value, number of installments, months before today of the first one
INSTALLMENTS = [("Magalu", 28990, 10, 4), ("Samsung Store", 41658, 12, 2), ("Decolar", 31200, 6, 7)]


def card(
    today: date, months: int = 6, seed: int = 11, closing_day: int = 3
) -> tuple[list[Line], dict[date, int]]:
    """The credit card, as the account sees it (purchases negative), and the bill total due each month.

    Statement for month M closes on `closing_day` and is due 7 days later; the bill paid from checking
    is the sum of that statement's lines.
    """
    rng = random.Random(seed)
    lines: list[Line] = []
    firsts = _months_back(today, months)
    for index, first in enumerate(firsts):
        for description, low, high, n_min, n_max in CARD_SHOPS:
            for _ in range(rng.randint(n_min, n_max)):
                day = _day(first, rng.randint(1, 28), today)
                if day:
                    lines.append(Line(day, -_cents(rng, low, high), description))
        for description, cents in SUBSCRIPTIONS:
            if day := _day(first, 9, today):
                lines.append(Line(day, -cents, description))
        months_from_end = len(firsts) - 1 - index
        for description, cents, total, started in INSTALLMENTS:
            k = started - months_from_end + 1
            if 1 <= k <= total and (day := _day(first, 2, today)):
                lines.append(Line(day, -cents, f"{description} - Parcela {k}/{total}"))
        if rng.random() < 0.25 and (day := _day(first, rng.randint(1, 28), today)):
            lines.append(Line(day, -_cents(rng, 2, 9), "IOF de compra internacional"))

    bills: dict[date, int] = {}
    purchases = list(lines)
    for previous, first in itertools.pairwise(firsts):
        opening, closing = previous.replace(day=closing_day), first.replace(day=closing_day)
        total = -sum(line.amount_cents for line in purchases if opening <= line.date < closing)
        due = closing + timedelta(days=7)
        if total > 0 and due <= today:
            bills[due] = total
            lines.append(Line(due, total, "Pagamento recebido"))
    return sorted(lines, key=lambda line: line.date), bills


def nubank_checking_csv(lines: list[Line]) -> str:
    rows = ["Data,Valor,Identificador,Descrição"]
    for line in lines:
        description = line.description.replace('"', "'")
        amount = f"{line.amount_cents / 100:.2f}"
        rows.append(f'{line.date:%d/%m/%Y},{amount},{line.external_id},"{description}"')
    return "\n".join(rows) + "\n"


def nubank_card_csv(lines: list[Line]) -> str:
    """The card export lists purchases as positive amounts and payments as negative ones."""
    rows = ["date,title,amount"]
    for line in lines:
        rows.append(f'{line.date.isoformat()},"{line.description}",{-line.amount_cents / 100:.2f}')
    return "\n".join(rows) + "\n"
