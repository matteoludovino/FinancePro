import type { AccountKind, Kind, MatchType } from "./types";

export const ACCOUNT_KINDS: { value: AccountKind; label: string; hint: string }[] = [
  { value: "checking", label: "Conta corrente", hint: "Onde o salário cai e as contas são pagas." },
  {
    value: "credit_card",
    label: "Cartão de crédito",
    hint: "As compras entram aqui; pagar a fatura é uma transferência.",
  },
  { value: "savings", label: "Poupança", hint: "Dinheiro guardado no banco." },
  { value: "wallet", label: "Carteira", hint: "Dinheiro em espécie." },
  {
    value: "external",
    label: "Fora do app",
    hint: "Investimentos, caixinhas ou conta em outro banco que você não importa. O que vai para lá não conta como gasto.",
  },
];

export const ACCOUNT_KIND_LABEL = Object.fromEntries(ACCOUNT_KINDS.map((k) => [k.value, k.label])) as Record<
  AccountKind,
  string
>;

export const MATCH_TYPES: { value: MatchType; label: string; hint: string }[] = [
  { value: "contains", label: "contém", hint: "A descrição tem este trecho em qualquer posição." },
  { value: "starts_with", label: "começa com", hint: "A descrição começa com este trecho." },
  {
    value: "merchant",
    label: "é o estabelecimento",
    hint: "O estabelecimento reconhecido é exatamente este (ex.: Uber), seja qual for o texto do banco.",
  },
];

export const MATCH_LABEL = Object.fromEntries(MATCH_TYPES.map((m) => [m.value, m.label])) as Record<
  MatchType,
  string
>;

export const KIND_LABEL: Record<Kind, string> = {
  regular: "Categoria",
  transfer: "Transferência entre contas suas",
  ignored: "Ignorar a linha",
};
