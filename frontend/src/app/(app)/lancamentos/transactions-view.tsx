"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useDeferredValue, useState } from "react";
import { CategorySelect } from "@/components/category-select";
import { RuleForm } from "@/components/rule-form";
import { Alert, Badge, Button, Card, Dialog, Input, Loading, PageHeader, Select } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCategories } from "@/lib/categories";
import { addMonths, currentMonth, monthLabel, shortDate } from "@/lib/dates";
import { formatCents } from "@/lib/money";
import type { Account, Category, Rule, Transaction } from "@/lib/types";

const PAGE = 50;

type Filters = { month: string; account: string; category: string; q: string };

export function TransactionsView() {
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/accounts") });
  const categories = useCategories();
  const [filters, setFilters] = useState<Filters>({
    month: currentMonth(),
    account: "",
    category: "",
    q: "",
  });
  const search = useDeferredValue(filters.q);
  const [limit, setLimit] = useState(PAGE);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [ruleFrom, setRuleFrom] = useState<Transaction | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const params = new URLSearchParams({ limit: String(limit) });
  if (filters.month) params.set("month", filters.month);
  if (filters.account) params.set("account_id", filters.account);
  if (filters.category === "none") params.set("uncategorized", "true");
  else if (filters.category) params.set("category_id", filters.category);
  if (search.trim()) params.set("q", search.trim());

  const page = useQuery({
    queryKey: ["transactions", params.toString()],
    queryFn: () => api.get<{ items: Transaction[]; total: number }>(`/transactions?${params}`),
    placeholderData: (previous) => previous,
  });
  const change = (update: Partial<Filters>) => {
    setFilters((current) => ({ ...current, ...update }));
    setLimit(PAGE);
    setSelected(new Set());
  };

  const ready = accounts.data && categories.data;
  return (
    <>
      <PageHeader
        title="Lançamentos"
        action={
          <Link
            href="/importar"
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
          >
            Importar extrato
          </Link>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex items-center rounded-lg border border-zinc-300 bg-white">
          <button
            type="button"
            aria-label="Mês anterior"
            className="px-3 py-2 text-zinc-600 hover:text-zinc-900"
            onClick={() => change({ month: addMonths(filters.month || currentMonth(), -1) })}
          >
            ‹
          </button>
          <span className="min-w-36 text-center text-sm font-medium text-zinc-900">
            {filters.month ? monthLabel(filters.month) : "Todos os meses"}
          </span>
          <button
            type="button"
            aria-label="Próximo mês"
            className="px-3 py-2 text-zinc-600 hover:text-zinc-900"
            onClick={() => change({ month: addMonths(filters.month || currentMonth(), 1) })}
          >
            ›
          </button>
        </div>
        <Button
          variant="ghost"
          className="px-2 text-xs"
          onClick={() => change({ month: filters.month ? "" : currentMonth() })}
        >
          {filters.month ? "Ver todos os meses" : "Só este mês"}
        </Button>
        <Select
          aria-label="Conta"
          className="sm:w-44"
          value={filters.account}
          onChange={(e) => change({ account: e.target.value })}
        >
          <option value="">Todas as contas</option>
          {accounts.data?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </Select>
        <CategoryFilter
          categories={categories.data ?? []}
          value={filters.category}
          onChange={(category) => change({ category })}
        />
        <Input
          aria-label="Buscar"
          placeholder="Buscar"
          className="sm:w-48"
          value={filters.q}
          onChange={(e) => change({ q: e.target.value })}
        />
      </div>

      {notice && <Alert tone="info">{notice}</Alert>}

      {!ready || page.isPending ? (
        <Loading />
      ) : page.isError ? (
        <Alert>{errorMessage(page.error)}</Alert>
      ) : page.data.items.length === 0 ? (
        <Card className="text-center text-sm text-zinc-600">
          Nenhum lançamento aqui.{" "}
          <Link href="/importar" className="font-medium text-emerald-700 hover:underline">
            Importe um extrato
          </Link>
          .
        </Card>
      ) : (
        <>
          {selected.size > 0 && (
            <BulkBar
              ids={[...selected]}
              categories={categories.data}
              onDone={(message) => {
                setSelected(new Set());
                setNotice(message);
              }}
            />
          )}
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="w-10 px-3 py-2">
                    <input
                      type="checkbox"
                      aria-label="Selecionar todos"
                      checked={selected.size === page.data.items.length}
                      onChange={(e) =>
                        setSelected(new Set(e.target.checked ? page.data.items.map((t) => t.id) : []))
                      }
                    />
                  </th>
                  <th className="px-3 py-2 font-medium">Data</th>
                  <th className="px-3 py-2 font-medium">Descrição</th>
                  <th className="px-3 py-2 font-medium">Categoria</th>
                  <th className="px-3 py-2 text-right font-medium">Valor</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {page.data.items.map((transaction) => (
                  <Row
                    key={transaction.id}
                    transaction={transaction}
                    account={accounts.data.find((a) => a.id === transaction.account_id)}
                    categories={categories.data}
                    selected={selected.has(transaction.id)}
                    onSelect={(on) =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (on) next.add(transaction.id);
                        else next.delete(transaction.id);
                        return next;
                      })
                    }
                    onCreateRule={() => setRuleFrom(transaction)}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex items-center justify-between text-sm text-zinc-500">
            <span>
              {page.data.items.length} de {page.data.total}
            </span>
            {page.data.items.length < page.data.total && (
              <Button variant="secondary" onClick={() => setLimit((l) => l + PAGE)}>
                Carregar mais
              </Button>
            )}
          </div>
        </>
      )}

      <Dialog open={ruleFrom !== null} onClose={() => setRuleFrom(null)} title="Nova regra">
        {ruleFrom && ready && (
          <CreateRule
            transaction={ruleFrom}
            categories={categories.data}
            accounts={accounts.data}
            onDone={(message) => {
              setRuleFrom(null);
              if (message) setNotice(message);
            }}
          />
        )}
      </Dialog>
    </>
  );
}

function CategoryFilter({
  categories,
  value,
  onChange,
}: {
  categories: Category[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <CategorySelect
      aria-label="Categoria"
      className="sm:w-56"
      categories={categories}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      emptyLabel="Todas as categorias"
      extra={<option value="none">Sem categoria</option>}
    />
  );
}

function useTransactionUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.patch<Transaction>(`/transactions/${id}`, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["transactions"] }),
  });
}

function Row({
  transaction,
  account,
  categories,
  selected,
  onSelect,
  onCreateRule,
}: {
  transaction: Transaction;
  account: Account | undefined;
  categories: Category[];
  selected: boolean;
  onSelect: (on: boolean) => void;
  onCreateRule: () => void;
}) {
  const update = useTransactionUpdate();
  const regular = transaction.kind === "regular";
  return (
    <tr className={`border-t border-zinc-100 ${selected ? "bg-emerald-50/50" : ""}`}>
      <td className="px-3 py-2">
        <input
          type="checkbox"
          aria-label={`Selecionar ${transaction.merchant}`}
          checked={selected}
          onChange={(e) => onSelect(e.target.checked)}
        />
      </td>
      <td className="px-3 py-2 whitespace-nowrap text-zinc-600">{shortDate(transaction.date)}</td>
      <td className="max-w-72 px-3 py-2">
        <p className="truncate font-medium text-zinc-900">{transaction.merchant}</p>
        <p className="truncate text-xs text-zinc-500">
          {account?.name} · {transaction.description_raw}
        </p>
      </td>
      <td className="px-3 py-2">
        {regular ? (
          <CategorySelect
            aria-label={`Categoria de ${transaction.merchant}`}
            className={`py-1 text-xs sm:w-52 ${transaction.category_id === null ? "border-amber-400" : ""}`}
            categories={categories}
            value={transaction.category_id ?? ""}
            emptyLabel="Sem categoria"
            onChange={(e) =>
              update.mutate({
                id: transaction.id,
                body: { category_id: e.target.value ? Number(e.target.value) : null },
              })
            }
          />
        ) : (
          <span className="flex items-center gap-2">
            <Badge>{transaction.kind === "transfer" ? "Transferência" : "Ignorada"}</Badge>
            <button
              type="button"
              className="text-xs text-zinc-500 hover:text-zinc-900"
              onClick={() => update.mutate({ id: transaction.id, body: { kind: "regular" } })}
            >
              é um gasto/receita
            </button>
          </span>
        )}
      </td>
      <td
        className={`px-3 py-2 text-right whitespace-nowrap tabular-nums ${
          transaction.amount_cents > 0 ? "text-emerald-700" : "text-zinc-900"
        } ${regular ? "" : "text-zinc-400"}`}
      >
        {formatCents(transaction.amount_cents)}
      </td>
      <td className="px-3 py-2 text-right whitespace-nowrap">
        <Button variant="ghost" className="px-2 py-1 text-xs" onClick={onCreateRule}>
          Criar regra
        </Button>
      </td>
    </tr>
  );
}

function BulkBar({
  ids,
  categories,
  onDone,
}: {
  ids: number[];
  categories: Category[];
  onDone: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState("");
  const bulk = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<{ updated: number }>("/transactions/bulk", { ids, ...body }),
    onSuccess: ({ updated }) => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      onDone(`${updated} lançamento(s) atualizados.`);
    },
  });
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm">
      <span className="font-medium text-emerald-900">{ids.length} selecionado(s)</span>
      <CategorySelect
        aria-label="Categoria para os selecionados"
        className="py-1 text-xs sm:w-56"
        categories={categories}
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      />
      <Button
        variant="secondary"
        className="py-1"
        disabled={!category}
        onClick={() => bulk.mutate({ action: "categorize", category_id: Number(category) })}
      >
        Aplicar
      </Button>
      <Button variant="ghost" className="py-1" onClick={() => bulk.mutate({ action: "transfer" })}>
        Transferência
      </Button>
      <Button variant="ghost" className="py-1" onClick={() => bulk.mutate({ action: "ignore" })}>
        Ignorar
      </Button>
      <Button variant="ghost" className="py-1 text-red-700" onClick={() => bulk.mutate({ action: "delete" })}>
        Excluir
      </Button>
      {bulk.error && <span className="text-red-700">{errorMessage(bulk.error)}</span>}
    </div>
  );
}

function CreateRule({
  transaction,
  categories,
  accounts,
  onDone,
}: {
  transaction: Transaction;
  categories: Category[];
  accounts: Account[];
  onDone: (message?: string) => void;
}) {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState<Rule | null>(null);
  const apply = useMutation({
    mutationFn: (rule: Rule) => api.post<{ updated: number }>(`/rules/${rule.id}/apply`),
    onSuccess: ({ updated }) => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      onDone(`Regra criada e aplicada a ${updated} lançamento(s).`);
    },
  });
  if (saved) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-zinc-700">
          Regra criada. Os próximos extratos já vêm categorizados. Aplicar também aos lançamentos que você já
          tem? (Os que você categorizou à mão não mudam.)
        </p>
        <Alert>{apply.error && errorMessage(apply.error)}</Alert>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => onDone("Regra criada.")}>
            Só os próximos
          </Button>
          <Button busy={apply.isPending} onClick={() => apply.mutate(saved)}>
            Aplicar aos existentes
          </Button>
        </div>
      </div>
    );
  }
  return (
    <RuleForm
      rule={null}
      initial={{
        match_type: "merchant",
        pattern: transaction.merchant,
        sets_kind: transaction.kind,
        category_id: transaction.category_id,
      }}
      categories={categories}
      accounts={accounts}
      onDone={() => undefined}
      onSaved={setSaved}
    />
  );
}
