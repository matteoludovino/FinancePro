"""What leaves for the model: a merchant name and whether money came in or went out. Nothing else.

Even merchant names can carry personal data (a CPF or an account number pasted by the bank), so
documents and long numbers are masked. Lines that are about a person (Pix and transfers to someone) are
never sent at all: a model can't know what a payment to "Maria Souza" was for, and her name isn't
the app's to share (LGPD).
"""

import re

_CPF = re.compile(r"(?:\d|•){3}\.?(?:\d|•){3}\.?(?:\d|•){3}-?(?:\d|•){2}")
_CNPJ = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
_LONG_NUMBER = re.compile(r"\d{5,}")
_ABOUT_A_PERSON = re.compile(
    r"^(pix (para|de)|transferência (para|de)|transferencia (para|de))\b", re.IGNORECASE
)


def about_a_person(merchant: str) -> bool:
    return bool(_ABOUT_A_PERSON.match(merchant))


def mask(text: str) -> str:
    text = _CNPJ.sub("[documento]", text)
    text = _CPF.sub("[documento]", text)
    return _LONG_NUMBER.sub("[número]", text)
