"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { RULES, RuleForm } from "@/components/rule-form";
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
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { categoryLabel, useCategories } from "@/lib/categories";
import { KIND_LABEL, MATCH_LABEL } from "@/lib/labels";
import { formatCents, parseCents } from "@/lib/money";
import type { Account, Category, Decision, Rule } from "@/lib/types";

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
