// Shapes returned by the API (backend/src/financepro/*/schemas.py).

export type User = {
  id: number;
  name: string;
  email: string;
  is_sandbox: boolean;
};

export type AccountKind = "checking" | "savings" | "wallet" | "credit_card" | "external";

export type Account = {
  id: number;
  name: string;
  kind: AccountKind;
  institution: string;
  closing_day: number | null;
  due_day: number | null;
  is_archived: boolean;
};

export type CategoryType = "expense" | "income";

export type Category = {
  id: number;
  name: string;
  type: CategoryType;
  parent_id: number | null;
  slug: string | null;
  is_archived: boolean;
};

export type MatchType = "contains" | "starts_with" | "merchant";
export type Kind = "regular" | "transfer" | "ignored";

export type Rule = {
  id: number;
  match_type: MatchType;
  pattern: string;
  sets_kind: Kind;
  category_id: number | null;
  account_id: number | null;
  min_cents: number | null;
  max_cents: number | null;
  is_default: boolean;
};

export type Decision = {
  merchant: string;
  kind: Kind;
  category_id: number | null;
  source: "rule" | "merchant" | null;
  rule_id: number | null;
};
