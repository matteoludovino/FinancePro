"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CategorySelect } from "@/components/category-select";
import { Alert, Button, Field, formValues, Input, Select } from "@/components/ui";
import { api, errorMessage, fieldError } from "@/lib/api";
import { KIND_LABEL, MATCH_TYPES } from "@/lib/labels";
import { centsToInput, parseCents } from "@/lib/money";
import type { Account, Category, Kind, MatchType, Rule } from "@/lib/types";

export const RULES = ["rules"] as const;

export function RuleForm({
  rule,
  initial,
  categories,
  accounts,
  onDone,
  onSaved,
}: {
  rule: Rule | null;
  /** Prefill for a new rule, e.g. from a transaction: its merchant and category. */
  initial?: Partial<Pick<Rule, "match_type" | "pattern" | "sets_kind" | "category_id">>;
  categories: Category[];
  accounts: Account[];
  onDone: () => void;
  onSaved?: (rule: Rule) => void;
}) {
  const queryClient = useQueryClient();
  const [match, setMatch] = useState<MatchType>(rule?.match_type ?? initial?.match_type ?? "contains");
  const [kind, setKind] = useState<Kind>(rule?.sets_kind ?? initial?.sets_kind ?? "regular");
  const [category, setCategory] = useState(String(rule?.category_id ?? initial?.category_id ?? ""));
  const [amountError, setAmountError] = useState<string | null>(null);
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: RULES });
    onDone();
  };

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      rule ? api.put<Rule>(`/rules/${rule.id}`, body) : api.post<Rule>("/rules", body),
    onSuccess: (saved) => {
      onSaved?.(saved);
      done();
    },
  });
  const remove = useMutation({ mutationFn: () => api.delete(`/rules/${rule!.id}`), onSuccess: done });

  const submit = (values: Record<string, string>) => {
    const amount = (field: string) => (values[field] ? parseCents(values[field]) : null);
    const [min, max] = [amount("min"), amount("max")];
    if ((values.min && min === null) || (values.max && max === null)) {
      setAmountError("Use valores como 30 ou 1.234,56.");
      return;
    }
    setAmountError(null);
    save.mutate({
      match_type: match,
      pattern: values.pattern,
      sets_kind: kind,
      category_id: kind === "regular" ? Number(category) || null : null,
      account_id: Number(values.account_id) || null,
      min_cents: min,
      max_cents: max,
    });
  };

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit(formValues(event.currentTarget));
      }}
    >
      <div className="grid grid-cols-[10rem_1fr] gap-3">
        <Field label="Quando a descrição">
          {(props) => (
            <Select {...props} value={match} onChange={(e) => setMatch(e.target.value as MatchType)}>
              {MATCH_TYPES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Texto" error={fieldError(save.error, "pattern")}>
          {(props) => (
            <Input
              {...props}
              name="pattern"
              defaultValue={rule?.pattern ?? initial?.pattern}
              required
              minLength={2}
              maxLength={100}
            />
          )}
        </Field>
      </div>
      <p className="-mt-2 text-xs text-zinc-500">{MATCH_TYPES.find((m) => m.value === match)?.hint}</p>
      <Field label="Então é">
        {(props) => (
          <Select {...props} value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABEL[k]}
              </option>
            ))}
          </Select>
        )}
      </Field>
      {kind === "regular" && (
        <Field label="Categoria" error={fieldError(save.error, "category_id")}>
          {(props) => (
            <CategorySelect
              {...props}
              categories={categories}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              required
            />
          )}
        </Field>
      )}
      <details
        className="rounded-lg border border-zinc-200 px-3 py-2"
        open={Boolean(rule?.account_id || rule?.min_cents || rule?.max_cents)}
      >
        <summary className="cursor-pointer text-sm text-zinc-700">Restringir (opcional)</summary>
        <div className="mt-3 space-y-3">
          <Field label="Só nesta conta">
            {(props) => (
              <Select {...props} name="account_id" defaultValue={rule?.account_id ?? ""}>
                <option value="">Qualquer conta</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Valor a partir de">
              {(props) => (
                <Input
                  {...props}
                  name="min"
                  inputMode="decimal"
                  placeholder="0,00"
                  defaultValue={rule?.min_cents != null ? centsToInput(rule.min_cents) : ""}
                />
              )}
            </Field>
            <Field label="Valor até">
              {(props) => (
                <Input
                  {...props}
                  name="max"
                  inputMode="decimal"
                  placeholder="0,00"
                  defaultValue={rule?.max_cents != null ? centsToInput(rule.max_cents) : ""}
                />
              )}
            </Field>
          </div>
        </div>
      </details>
      <Alert>
        {amountError ?? ((save.error ?? remove.error) ? errorMessage(save.error ?? remove.error) : null)}
      </Alert>
      <div className="flex items-center justify-between gap-2">
        {rule ? (
          <Button
            variant="ghost"
            className="px-2 text-red-700"
            busy={remove.isPending}
            onClick={() => remove.mutate()}
          >
            Excluir regra
          </Button>
        ) : (
          <span />
        )}
        <Button type="submit" busy={save.isPending}>
          Salvar
        </Button>
      </div>
    </form>
  );
}
