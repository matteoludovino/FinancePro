"""Sample statements to try the import with, generated for today so they never go stale.

`nubank-conta-atualizado.csv` overlaps `nubank-conta.csv` by a month and adds the last two weeks: importing
both shows deduplication at work.
"""

from collections.abc import Callable
from datetime import date, timedelta

from financepro import clock
from financepro.demo import generator


def _checking(today: date, start: date, end: date) -> str:
    _, bills = generator.card(today, months=4)
    lines = generator.checking(today, months=4, card_bills=bills)
    return generator.nubank_checking_csv([line for line in lines if start <= line.date <= end])


def _card(today: date) -> str:
    lines, _ = generator.card(today, months=4)
    return generator.nubank_card_csv([line for line in lines if line.date >= today - timedelta(days=90)])


SAMPLES: dict[str, Callable[[date], str]] = {
    "nubank-conta.csv": lambda t: _checking(t, t - timedelta(days=90), t - timedelta(days=15)),
    "nubank-conta-atualizado.csv": lambda t: _checking(t, t - timedelta(days=45), t),
    "nubank-cartao.csv": _card,
}


def sample(name: str) -> str | None:
    make = SAMPLES.get(name)
    return make(clock.today()) if make else None
