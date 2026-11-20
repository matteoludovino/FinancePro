import pytest
from hypothesis import given
from hypothesis import strategies as st

from financepro.categorization.normalizer import merchant_of
from financepro.text import canonical


@pytest.mark.parametrize(
    ("description", "name", "slug"),
    [
        # Card processors and marketplaces put their own prefix before the merchant.
        ("IFD*BURGER KING 4421 SAO PAULO BR", "iFood", "delivery"),
        ("UBER *TRIP HELP.UBER.COM", "Uber", "apps-transporte"),
        ("Uber Eats", "Uber Eats", "delivery"),
        ("MERCADOLIVRE*VENDEDOR", "Mercado Livre", "compras-online"),
        ("DL*GOOGLE YOUTUBE", "YouTube Premium", "streaming"),
        ("NETFLIX.COM", "Netflix", "streaming"),
        # Nubank account lines: the person on the other side of a Pix, not the bank's boilerplate.
        (
            "Transferência enviada pelo Pix - MARIA S SOUZA - •••.123.456-•• - NU PAGAMENTOS - IP (0260) "
            "Agência: 1 Conta: 1234-5",
            "Pix para Maria S Souza",
            None,
        ),
        (
            "Transferência recebida pelo Pix - JOÃO PEDRO LIMA - •••.987.654-•• - BCO DO BRASIL",
            "Pix de João Pedro Lima",
            None,
        ),
        ("Compra no débito - PADARIA REAL", "Padaria Real", "padaria-cafe"),
        ("Pagamento de boleto efetuado - ENEL DISTRIBUICAO SP", "Enel", "contas-casa"),
        ("Pagamento recebido", "Pagamento de fatura", None),
        # Noise around unknown merchants: store numbers, city, installment counter.
        ("POSTO BOA VIAGEM 0012 SAO PAULO", "Posto Boa Viagem", "combustivel"),
        ("Loja Fulana - Parcela 3/10", "Loja Fulana", None),
        ("CASAS BAHIA 12/12", "Casas Bahia", None),
        # Accents survive; a person's own casing is kept, shouting is not.
        ("Açaí da Esquina", "Açaí da Esquina", None),
        ("Aplicação RDB", "Aplicação RDB", None),
        ("SUPERMERCADO DIA", "Supermercado Dia", "mercado"),
    ],
)
def test_merchants_people_recognize(description: str, name: str, slug: str | None) -> None:
    merchant = merchant_of(description)
    assert (merchant.name, merchant.slug) == (name, slug)


def test_delivery_is_not_mistaken_for_a_ride() -> None:
    assert merchant_of("UBER *EATS PENDING").slug == "delivery"
    assert merchant_of("UBER *TRIP").slug == "apps-transporte"


def test_short_names_need_a_word_boundary() -> None:
    # "zara" inside another word is not Zara; "claro" inside "Esclarecimento" is not the phone company.
    assert merchant_of("BAZARAMA").slug is None
    assert merchant_of("ESCLARECIMENTO LTDA").slug is None


@given(st.text(min_size=1, max_size=120).filter(lambda s: s.strip()))
def test_any_description_yields_a_name(description: str) -> None:
    merchant = merchant_of(description)
    assert merchant.name
    assert len(merchant.name) <= 60


@given(st.text(max_size=200))
def test_canonical_form_is_stable(text: str) -> None:
    once = canonical(text)
    assert canonical(once) == once
    assert once == once.strip()
    assert "  " not in once
