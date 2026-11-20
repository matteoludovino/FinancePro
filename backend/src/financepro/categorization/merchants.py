"""Known merchants and keywords: the knowledge that categorizes common Brazilian purchases with no AI.

Each entry is (display name or None, taxonomy slug, regex over the canonical description). With a name,
the purchase is shown as that merchant ("IFD*BURGER KING 123" → "iFood"); without one, the cleaned
description is kept and only the category is suggested ("POSTO BOA VIAGEM" → fuel). First match wins,
so specific merchants come before generic keywords.
"""

import re
from typing import NamedTuple


class Known(NamedTuple):
    name: str | None
    slug: str
    pattern: re.Pattern[str]


def _k(name: str | None, slug: str, pattern: str) -> Known:
    return Known(name, slug, re.compile(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])"))


KNOWN: tuple[Known, ...] = (
    # Delivery before transport: "uber eats" is food, "uber" is a ride.
    _k("iFood", "delivery", r"ifood|ifd\*?"),
    _k("Uber Eats", "delivery", r"uber ?\*? ?eats"),
    _k("Rappi", "delivery", r"rappi"),
    _k("Zé Delivery", "delivery", r"ze ?delivery"),
    _k("Uber", "apps-transporte", r"uber|uber \*trip|uber\*trip"),
    _k("99", "apps-transporte", r"99 ?app|99 ?pop|99 ?taxis?|99 tecnologia"),
    _k("Netflix", "streaming", r"netflix(?:\.com)?"),
    _k("Spotify", "streaming", r"spotify"),
    _k("Disney+", "streaming", r"disney ?plus|disneyplus"),
    _k("Prime Video", "streaming", r"prime ?video|primevideo"),
    _k("Max", "streaming", r"hbo ?max|max\.com"),
    _k("Globoplay", "streaming", r"globoplay"),
    _k("YouTube Premium", "streaming", r"youtube ?premium|google ?youtube"),
    _k("Apple", "streaming", r"apple\.com(?:/bill)?"),
    _k("Amazon", "compras-online", r"amazon(?:\.com)?(?:\.br)?|amzn"),
    _k("Mercado Livre", "compras-online", r"mercado ?livre|mercadolivre"),
    _k("Shopee", "compras-online", r"shopee"),
    _k("Magalu", "compras-online", r"magalu|magazine ?luiza"),
    _k("AliExpress", "compras-online", r"aliexpress"),
    _k("Shein", "vestuario", r"shein"),
    _k("Renner", "vestuario", r"lojas ?renner|renner"),
    _k("C&A", "vestuario", r"c ?& ?a|cea modas"),
    _k("Riachuelo", "vestuario", r"riachuelo"),
    _k("Zara", "vestuario", r"zara"),
    _k("Centauro", "vestuario", r"centauro"),
    _k("Netshoes", "vestuario", r"netshoes"),
    _k("Carrefour", "mercado", r"carrefour"),
    _k("Pão de Açúcar", "mercado", r"pao de acucar|paodeacucar"),
    _k("Assaí", "mercado", r"assai(?: atacadista)?"),
    _k("Atacadão", "mercado", r"atacadao"),
    _k("Oxxo", "mercado", r"oxxo"),
    _k("Hortifruti", "mercado", r"hortifruti"),
    _k("Drogasil", "farmacia", r"drogasil"),
    _k("Droga Raia", "farmacia", r"droga ?raia|drogaraia"),
    _k("Pague Menos", "farmacia", r"pague ?menos"),
    _k("Drogaria São Paulo", "farmacia", r"drogaria sao paulo"),
    _k("Panvel", "farmacia", r"panvel"),
    _k("Shell", "combustivel", r"shell|raizen"),
    _k("Ipiranga", "combustivel", r"ipiranga"),
    _k("Petrobras", "combustivel", r"petrobras|posto br"),
    _k("Sem Parar", "estacionamento-pedagio", r"sem ?parar"),
    _k("ConectCar", "estacionamento-pedagio", r"conectcar"),
    _k("Veloe", "estacionamento-pedagio", r"veloe"),
    _k("Smart Fit", "academia", r"smart ?fit"),
    _k("Wellhub", "academia", r"wellhub|gympass"),
    _k("Vivo", "telefone", r"vivo|telefonica"),
    _k("Claro", "telefone", r"claro"),
    _k("TIM", "telefone", r"tim celular|tim s\.?a\.?"),
    _k("McDonald's", "restaurantes", r"mc ?donald'?s?|mcdonalds"),
    _k("Burger King", "restaurantes", r"burger ?king|bk brasil"),
    _k("Outback", "restaurantes", r"outback"),
    _k("Subway", "restaurantes", r"subway"),
    _k("Habib's", "restaurantes", r"habib'?s"),
    _k("Starbucks", "padaria-cafe", r"starbucks"),
    _k("Airbnb", "viagens", r"airbnb"),
    _k("Booking.com", "viagens", r"booking(?:\.com)?"),
    _k("LATAM", "viagens", r"latam(?: airlines)?"),
    _k("GOL", "viagens", r"gol linhas|voegol"),
    _k("Azul", "viagens", r"azul linhas|voeazul"),
    _k("Decolar", "viagens", r"decolar"),
    _k("Steam", "jogos", r"steam(?:games|powered)?"),
    _k("PlayStation", "jogos", r"playstation|psn"),
    _k("Xbox", "jogos", r"xbox"),
    _k("Nintendo", "jogos", r"nintendo"),
    _k("Udemy", "cursos", r"udemy"),
    _k("Alura", "cursos", r"alura"),
    _k("Coursera", "cursos", r"coursera"),
    _k("Petz", "pets", r"petz"),
    _k("Cobasi", "pets", r"cobasi"),
    _k("Leroy Merlin", "casa-decoracao", r"leroy ?merlin"),
    _k("Tok&Stok", "casa-decoracao", r"tok ?& ?stok|tokstok"),
    _k("Kabum", "eletronicos", r"kabum"),
    _k("Fast Shop", "eletronicos", r"fast ?shop"),
    _k("Enel", "contas-casa", r"enel"),
    _k("Sabesp", "contas-casa", r"sabesp"),
    _k("Comgás", "contas-casa", r"comgas"),
    _k("CPFL", "contas-casa", r"cpfl"),
    _k("Cemig", "contas-casa", r"cemig"),
    _k("Copel", "contas-casa", r"copel"),
    _k("Unimed", "plano-saude", r"unimed"),
    _k("Amil", "plano-saude", r"amil"),
    _k("SulAmérica", "plano-saude", r"sul ?america(?: saude)?"),
    _k("Hapvida", "plano-saude", r"hapvida"),
    _k("SPTrans", "transporte-publico", r"sptrans|bilhete unico"),
    # Generic keywords: suggest a category, keep the merchant's own name.
    _k(None, "combustivel", r"posto|auto posto|combustiveis"),
    _k(None, "farmacia", r"farmacia|drogaria"),
    _k(None, "padaria-cafe", r"padaria|panificadora|cafeteria"),
    _k(None, "restaurantes", r"restaurante|churrascaria|pizzaria|lanchonete|hamburgueria|sushi"),
    _k(None, "mercado", r"supermercados?|hipermercado|mercado|mercearia|hortifruti|sacolao|atacarejo"),
    _k(None, "estacionamento-pedagio", r"estacionamento|estapar|parking|pedagio"),
    _k(None, "academia", r"academia"),
    _k(None, "pets", r"pet ?shop|veterinari[ao]"),
    _k(None, "tarifas-bancarias", r"tarifa|anuidade|cesta de servicos"),
    _k(None, "iof", r"iof"),
    _k(None, "juros-multas", r"juros|multa|encargos"),
    _k(None, "salario", r"salario|folha de pagamento|pagto salario"),
)


def find(canonical_text: str) -> Known | None:
    return next((known for known in KNOWN if known.pattern.search(canonical_text)), None)
