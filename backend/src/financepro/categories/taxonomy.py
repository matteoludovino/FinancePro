"""The fixed category taxonomy every new person starts with.

Each category carries a stable `slug`. People may rename, archive or add categories freely; the slug is
how built-in knowledge (known merchants, default rules, the AI's answers) finds "their" Restaurants
whatever they called it. Changing a slug here is a data migration, so slugs never change; add new ones.
"""

from dataclasses import dataclass
from enum import StrEnum


class CategoryType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


@dataclass(frozen=True)
class Node:
    slug: str
    name: str
    children: tuple[Node, ...] = ()


def _n(slug: str, name: str, *children: tuple[str, str]) -> Node:
    return Node(slug, name, tuple(Node(s, n) for s, n in children))


EXPENSES: tuple[Node, ...] = (
    _n(
        "moradia",
        "Moradia",
        ("aluguel", "Aluguel e financiamento"),
        ("condominio", "Condomínio"),
        ("contas-casa", "Luz, água, gás e internet"),
        ("manutencao-casa", "Manutenção e reformas"),
    ),
    _n(
        "alimentacao",
        "Alimentação",
        ("mercado", "Mercado"),
        ("restaurantes", "Restaurantes e bares"),
        ("delivery", "Delivery"),
        ("padaria-cafe", "Padaria e café"),
    ),
    _n(
        "transporte",
        "Transporte",
        ("combustivel", "Combustível"),
        ("apps-transporte", "Apps de transporte"),
        ("transporte-publico", "Transporte público"),
        ("estacionamento-pedagio", "Estacionamento e pedágio"),
        ("manutencao-veiculo", "Manutenção do veículo"),
    ),
    _n(
        "saude",
        "Saúde",
        ("farmacia", "Farmácia"),
        ("plano-saude", "Plano de saúde"),
        ("consultas-exames", "Consultas e exames"),
        ("academia", "Academia e esportes"),
    ),
    _n(
        "educacao",
        "Educação",
        ("mensalidade-escolar", "Escola e faculdade"),
        ("cursos", "Cursos e livros"),
    ),
    _n(
        "lazer",
        "Lazer",
        ("streaming", "Streaming e assinaturas"),
        ("jogos", "Jogos"),
        ("eventos", "Cinema, shows e eventos"),
        ("viagens", "Viagens e hospedagem"),
    ),
    _n(
        "compras",
        "Compras",
        ("vestuario", "Roupas e calçados"),
        ("eletronicos", "Eletrônicos"),
        ("casa-decoracao", "Casa e decoração"),
        ("compras-online", "Compras online"),
    ),
    _n("cuidados-pessoais", "Cuidados pessoais"),
    _n("pets", "Pets"),
    _n("telefone", "Celular e telefone"),
    _n(
        "taxas",
        "Impostos e taxas",
        ("impostos", "Impostos"),
        ("tarifas-bancarias", "Tarifas bancárias"),
        ("juros-multas", "Juros e multas"),
        ("iof", "IOF"),
    ),
    _n("doacoes-presentes", "Doações e presentes"),
    _n("outros-gastos", "Outros gastos"),
)

INCOME: tuple[Node, ...] = (
    _n("salario", "Salário"),
    _n("renda-extra", "Renda extra e freelas"),
    _n("rendimentos", "Rendimentos"),
    _n("reembolsos", "Reembolsos"),
    _n("outras-receitas", "Outras receitas"),
)


def all_slugs() -> dict[str, CategoryType]:
    found: dict[str, CategoryType] = {}
    for kind, roots in ((CategoryType.EXPENSE, EXPENSES), (CategoryType.INCOME, INCOME)):
        for root in roots:
            for node in (root, *root.children):
                found[node.slug] = kind
    return found


SLUGS = all_slugs()
