"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { BudgetMeter, CategoryBars, CommitmentColumns, FlowChart, StatTile } from "@/components/charts";
import { Card, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { categoryLabel, useCategories } from "@/lib/categories";
import { addMonths, currentMonth, monthLabel } from "@/lib/dates";
import { formatCents } from "@/lib/money";
import { useMe } from "@/lib/session";
import type {
  Account,
  BudgetStatus,
  CategoryTotal,
  Commitment,
  FlowMonth,
  MerchantTotal,
  Overview,
} from "@/lib/types";

function useReport<T>(path: string, month: string) {
  return useQuery({
    queryKey: ["reports", path, month],
    queryFn: () => api.get<T>(`${path}?month=${month}`),
  });
}

export function Dashboard() {
  const me = useMe();
  const [month, setMonth] = useState(currentMonth);
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/accounts") });
  const overview = useReport<Overview>("/reports/overview", month);
  const flow = useQuery({
    queryKey: ["reports", "flow", month],
    queryFn: () => api.get<FlowMonth[]>(`/reports/flow?until=${month}&count=12`),
  });
  const categories = useReport<CategoryTotal[]>("/reports/categories", month);
  const merchants = useReport<MerchantTotal[]>("/reports/merchants", month);
  const budgets = useReport<BudgetStatus[]>("/budgets", month);
  const commitments = useQuery({
    queryKey: ["reports", "commitments"],
    queryFn: () => api.get<Commitment[]>("/reports/commitments?count=6"),
  });
  const allCategories = useCategories();

  const empty = flow.data?.every((m) => m.income_cents === 0 && m.expense_cents === 0);
  if (accounts.data?.length === 0 || empty)
    return <FirstSteps name={me.data?.name} hasAccounts={!!accounts.data?.length} />;

  const o = overview.data;
  const balance = o ? o.income_cents - o.expense_cents : 0;
  const rate = o && o.income_cents > 0 ? balance / o.income_cents : null;
  return (
    <>
      <PageHeader
        title="Painel"
        action={
          <div className="flex items-center rounded-lg border border-zinc-300 bg-white">
            <button
              type="button"
              aria-label="Mês anterior"
              className="px-3 py-2 text-zinc-600"
              onClick={() => setMonth(addMonths(month, -1))}
            >
              ‹
            </button>
            <span className="min-w-36 text-center text-sm font-medium">{monthLabel(month)}</span>
            <button
              type="button"
              aria-label="Próximo mês"
              className="px-3 py-2 text-zinc-600"
              onClick={() => setMonth(addMonths(month, 1))}
            >
              ›
            </button>
          </div>
        }
      />
      {o && (o.uncategorized > 0 || o.ai_pending > 0) && (
        <div className="mb-4 flex flex-wrap gap-x-6 gap-y-1 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          {o.uncategorized > 0 && (
            <Link href="/lancamentos" className="hover:underline">
              {o.uncategorized} lançamento(s) sem categoria neste mês
            </Link>
          )}
          {o.ai_pending > 0 && (
            <Link href="/sugestoes" className="hover:underline">
              {o.ai_pending} sugestão(ões) da IA para revisar
            </Link>
          )}
        </div>
      )}
      {!o ? (
        <Loading />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Entradas"
            value={o.income_cents}
            previous={o.previous_income_cents}
            goodWhen="up"
          />
          <StatTile
            label="Saídas"
            value={o.expense_cents}
            previous={o.previous_expense_cents}
            goodWhen="down"
          />
          <StatTile label="Saldo do mês" value={balance} />
          <StatTile
            label="Guardado da renda"
            value={rate === null ? 0 : Math.round(rate * 100)}
            format={(v) => (rate === null ? "—" : `${v}%`)}
          />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <h2 className="mb-3 font-medium text-zinc-900">Entradas e saídas, últimos 12 meses</h2>
          {flow.data ? <FlowChart data={flow.data} /> : <Loading />}
        </Card>
        <Card>
          <h2 className="font-medium text-zinc-900">Parcelas por vir</h2>
          <p className="mb-3 text-xs text-zinc-500">
            Compras parceladas que ainda vão cair nos próximos meses.
          </p>
          {commitments.data ? <CommitmentColumns data={commitments.data} /> : <Loading />}
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-medium text-zinc-900">Gastos por categoria</h2>
          {categories.data?.length ? (
            <CategoryBars data={categories.data} />
          ) : (
            <p className="text-sm text-zinc-500">Nenhum gasto neste mês.</p>
          )}
        </Card>
        <Card>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="font-medium text-zinc-900">Orçamento</h2>
            <Link href="/orcamento" className="text-sm text-emerald-700 hover:underline">
              Definir limites
            </Link>
          </div>
          {budgets.data?.length ? (
            <ul className="space-y-4">
              {budgets.data.map((budget) => (
                <li key={budget.category_id}>
                  <BudgetMeter
                    budget={budget}
                    name={categoryLabel(allCategories.data ?? [], budget.category_id)}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-zinc-500">
              Nenhum limite definido. Comece pelas categorias em que você mais gasta.
            </p>
          )}
        </Card>
      </div>

      <Card className="mt-6">
        <h2 className="mb-3 font-medium text-zinc-900">Onde mais saiu dinheiro</h2>
        <ol className="divide-y divide-zinc-100 text-sm">
          {merchants.data?.map((m) => (
            <li key={m.merchant} className="flex items-baseline justify-between gap-3 py-2">
              <span className="truncate text-zinc-700">
                {m.merchant} <span className="text-xs text-zinc-400">· {m.count}×</span>
              </span>
              <span className="font-medium tabular-nums">{formatCents(m.total_cents)}</span>
            </li>
          ))}
        </ol>
      </Card>
    </>
  );
}

function FirstSteps({ name, hasAccounts }: { name?: string; hasAccounts: boolean }) {
  return (
    <>
      <PageHeader title={`Olá, ${name ?? ""}`} description="Vamos organizar as suas finanças." />
      <Card className="space-y-3">
        <h2 className="font-medium text-zinc-900">Primeiros passos</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-zinc-700">
          <li className={hasAccounts ? "text-zinc-400 line-through" : undefined}>
            <Link href="/contas" className="text-emerald-700 hover:underline">
              Cadastre suas contas
            </Link>{" "}
            — a conta corrente, o cartão de crédito e onde mais o seu dinheiro estiver.
          </li>
          <li>
            <Link href="/importar" className="text-emerald-700 hover:underline">
              Importe o extrato
            </Link>{" "}
            CSV que o seu banco exporta (ou um dos exemplos).
          </li>
          <li>Confira as categorias e defina o orçamento do mês. O painel aparece aqui.</li>
        </ol>
      </Card>
    </>
  );
}
