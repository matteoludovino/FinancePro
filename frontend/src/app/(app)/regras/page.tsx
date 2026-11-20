"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CategorySelect } from "@/components/category-select";
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  Field,
  formValues,
  Input,
  Loading,
  PageHeader,
  Select,
} from "@/components/ui";
import { api, errorMessage, fieldError } from "@/lib/api";
import { categoryLabel, useCategories } from "@/lib/categories";
import { KIND_LABEL, MATCH_LABEL, MATCH_TYPES } from "@/lib/labels";
import { centsToInput, formatCents, parseCents } from "@/lib/money";
import type { Account, Category, Decision, Kind, MatchType, Rule } from "@/lib/types";

const RULES = ["rules"] as const;

function outcome(rule: Pick<Rule, "sets_kind" | "category_id">, categories: Category[]): string {
  return rule.sets_kind === "regular"
    ? categoryLabel(categories, rule.category_id)
    : KIND_LABEL[rule.sets_kind];
}

export default function RulesPage() {
  const rules = useQuery({ queryKey: RULES, queryFn: () => api.get<Rule[]>("/rules") });
  const categories = useCategories();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/accounts") });
  const [editing, setEditing] = useState<Rule | "new" | null>(null);

  const ready = rules.data && categories.data && accounts.data;
  return (
    <>
      <PageHeader
        title="Regras"
        description="Como os lançamentos importados são categorizados. Quando várias regras servem, vale a mais específica."
        action={<Button onClick={() => setEditing("new")}>Nova regra</Button>}
      />
      {!ready ? (
        <Loading />
      ) : (
        <div className="space-y-6">
          <Tester categories={categories.data} />
          {rules.data.length === 0 ? (
            <Card className="text-center text-sm text-zinc-600">Nenhuma regra ainda.</Card>
          ) : (
            <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 bg-white">
              {rules.data.map((rule) => (
                <li key={rule.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0 text-sm">
                    <p className="text-zinc-900">
                      Quando a descrição <span className="text-zinc-500">{MATCH_LABEL[rule.match_type]}</span>{" "}
                      <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">{rule.pattern}</code> →{" "}
                      <span className="font-medium">{outcome(rule, categories.data)}</span>
                    </p>
                    <Conditions rule={rule} accounts={accounts.data} />
                  </div>
                  <div className="flex items-center gap-2">
                    {rule.is_default && <Badge>padrão</Badge>}
                    <Button variant="ghost" className="px-2 py-1" onClick={() => setEditing(rule)}>
                      Editar
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === "new" ? "Nova regra" : "Editar regra"}
      >
        {editing !== null && ready && (
          <RuleForm
            rule={editing === "new" ? null : editing}
            categories={categories.data}
            accounts={accounts.data}
            onDone={() => setEditing(null)}
          />
        )}
      </Dialog>
    </>
  );
}

function Conditions({ rule, accounts }: { rule: Rule; accounts: Account[] }) {
  const parts: string[] = [];
  if (rule.account_id !== null) parts.push(`só em ${accounts.find((a) => a.id === rule.account_id)?.name}`);
  if (rule.min_cents !== null) parts.push(`a partir de ${formatCents(rule.min_cents)}`);
  if (rule.max_cents !== null) parts.push(`até ${formatCents(rule.max_cents)}`);
  return parts.length ? <p className="mt-0.5 text-xs text-zinc-500">{parts.join(" · ")}</p> : null;
}

function Tester({ categories }: { categories: Category[] }) {
  const test = useMutation({
    mutationFn: (values: Record<string, string>) =>
      api.post<Decision>("/rules/preview", {
        description: values.description,
        amount_cents: -(parseCents(values.amount) ?? 1),
      }),
  });
  const decision = test.data;
  return (
    <Card>
      <h2 className="font-medium text-zinc-900">Testar uma descrição</h2>
      <p className="mt-1 text-sm text-zinc-600">Cole uma linha do extrato e veja o que acontece com ela.</p>
      <form
        className="mt-4 grid gap-3 sm:grid-cols-[1fr_9rem_auto] sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          test.mutate(formValues(event.currentTarget));
        }}
      >
        <Field label="Descrição">
          {(props) => (
            <Input {...props} name="description" required placeholder="Ex.: IFD*PIZZARIA BELLA 991" />
          )}
        </Field>
        <Field label="Valor (opcional)">
          {(props) => <Input {...props} name="amount" inputMode="decimal" placeholder="0,00" />}
        </Field>
        <Button type="submit" variant="secondary" busy={test.isPending}>
          Testar
        </Button>
      </form>
      <Alert>{test.error && errorMessage(test.error)}</Alert>
      {decision && (
        <dl className="mt-4 grid gap-1 rounded-lg bg-zinc-50 p-3 text-sm sm:grid-cols-[9rem_1fr]">
          <dt className="text-zinc-500">Estabelecimento</dt>
          <dd className="font-medium">{decision.merchant}</dd>
          <dt className="text-zinc-500">Resultado</dt>
          <dd className="font-medium">
            {decision.kind === "regular" && decision.category_id === null
              ? "Sem categoria (a IA vai sugerir uma)"
              : outcome({ sets_kind: decision.kind, category_id: decision.category_id }, categories)}
          </dd>
          <dt className="text-zinc-500">Por quê</dt>
          <dd>
            {decision.source === "rule"
              ? "Uma regra sua."
              : decision.source === "merchant"
                ? "Estabelecimento conhecido."
                : "Nenhuma regra serviu."}
          </dd>
        </dl>
      )}
    </Card>
  );
}

function RuleForm({
  rule,
  categories,
  accounts,
  onDone,
}: {
  rule: Rule | null;
  categories: Category[];
  accounts: Account[];
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [match, setMatch] = useState<MatchType>(rule?.match_type ?? "contains");
  const [kind, setKind] = useState<Kind>(rule?.sets_kind ?? "regular");
  const [category, setCategory] = useState(rule?.category_id ? String(rule.category_id) : "");
  const [amountError, setAmountError] = useState<string | null>(null);
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: RULES });
    onDone();
  };

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      rule ? api.put<Rule>(`/rules/${rule.id}`, body) : api.post<Rule>("/rules", body),
    onSuccess: done,
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
              defaultValue={rule?.pattern}
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
