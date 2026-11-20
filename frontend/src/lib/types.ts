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
