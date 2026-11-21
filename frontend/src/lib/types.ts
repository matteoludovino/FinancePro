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

export type DateFormat = "%d/%m/%Y" | "%d/%m/%y" | "%Y-%m-%d" | "%d-%m-%Y" | "%d.%m.%Y";

export type Mapping = {
  date: number;
  description: number[];
  amount: number | null;
  debit: number | null;
  credit: number | null;
  external_id: number | null;
  date_format: DateFormat;
  decimals: "," | ".";
  sign: "as_is" | "inverted";
  installment_dates: "auto" | "billing" | "purchase";
};

export type RowStatus = "new" | "duplicate" | "possible_duplicate" | "error";

export type PreviewRow = {
  line: number;
  status: RowStatus;
  description: string;
  date: string | null;
  effective_date: string | null;
  installment_k: number | null;
  installment_n: number | null;
  amount_cents: number | null;
  external_id: string | null;
  message: string | null;
  match: { id: number; date: string; description: string; amount_cents: number } | null;
  merchant: string;
  kind: Kind;
  category_id: number | null;
  category_source: string | null;
};

export type Batch = {
  id: number;
  account_id: number;
  status: "preview" | "committed" | "undone";
  filename: string;
  detected_by: string;
  label: string;
  warnings: string[];
  header: string[];
  sample: string[][];
  mapping: Mapping | null;
  summary: Partial<Record<RowStatus | "total" | "inserted", number>>;
  rows: PreviewRow[];
  created_at: string;
  committed_at: string | null;
  undone_at: string | null;
};

export type Transaction = {
  id: number;
  account_id: number;
  date: string;
  effective_date: string;
  amount_cents: number;
  description_raw: string;
  merchant: string;
  kind: Kind;
  category_id: number | null;
  category_source: "rule" | "merchant" | "ai" | "user" | null;
  notes: string;
  edited_at: string | null;
  transfer_pair_id: number | null;
  installment_group_id: number | null;
  installment_k: number | null;
  installment_n: number | null;
  ai_category_id: number | null;
  ai_confidence: "low" | "medium" | "high" | null;
};

export type AiStatus = { enabled: boolean; used_today: number; daily_limit: number };

export type AiGroup = {
  merchant: string;
  category_id: number;
  confidence: "low" | "medium" | "high";
  transaction_ids: number[];
  total_cents: number;
  example: string;
};

export type Statement = {
  month: string;
  opens: string;
  closes: string;
  due: string;
  charges_cents: number;
  paid_cents: number;
  status: "open" | "paid" | "partial" | "unpaid";
};

export type Installments = {
  id: number;
  account_id: number;
  merchant: string;
  installments: number;
  paid: number;
  amount_cents: number;
  last_month: string;
  future: { month: string; amount_cents: number }[];
};

export type TransferPair = { outflow: Transaction; inflow: Transaction };

export type Overview = {
  month: string;
  income_cents: number;
  expense_cents: number;
  previous_income_cents: number;
  previous_expense_cents: number;
  uncategorized: number;
  ai_pending: number;
};

export type FlowMonth = { month: string; income_cents: number; expense_cents: number };

export type CategoryTotal = {
  category_id: number | null;
  name: string;
  total_cents: number;
  children: CategoryTotal[];
};

export type MerchantTotal = { merchant: string; total_cents: number; count: number };

export type Commitment = { month: string; amount_cents: number };

export type BudgetStatus = {
  category_id: number;
  limit_cents: number;
  spent_cents: number;
  committed_cents: number;
  status: "ok" | "warning" | "over";
};
