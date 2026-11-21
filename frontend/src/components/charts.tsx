"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { shortMonth } from "@/lib/dates";
import { formatCents, formatCompact, formatRounded } from "@/lib/money";
import type { BudgetStatus, CategoryTotal, Commitment, FlowMonth } from "@/lib/types";

// Chart rules (dataviz skill): one axis, thin bars with 4px rounded ends square at the baseline, a 2px
// surface gap between neighbours, recessive grid, a legend for two series, hover tooltips, and a table
// view so nothing depends on color or hover alone.

export function StatTile({
  label,
  value,
  previous,
  goodWhen,
  format = formatCents,
}: {
  label: string;
  value: number;
  previous?: number;
  /** Whether a rise is good news ("up") or bad news ("down", e.g. spending). */
  goodWhen?: "up" | "down";
  format?: (value: number) => string;
}) {
  const delta = previous === undefined || previous === 0 ? null : (value - previous) / Math.abs(previous);
  const good = delta === null || goodWhen === undefined ? null : delta >= 0 === (goodWhen === "up");
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <p className="text-sm text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-zinc-900">{format(value)}</p>
      {delta !== null && (
        <p
          className={`mt-1 text-xs ${good === null ? "text-zinc-500" : good ? "text-[#006300]" : "text-red-700"}`}
        >
          <span aria-hidden>{delta >= 0 ? "▲" : "▼"}</span> {Math.abs(Math.round(delta * 100))}% vs. mês
          anterior
        </p>
      )}
    </div>
  );
}

export function FlowChart({ data }: { data: FlowMonth[] }) {
  const [table, setTable] = useState(false);
  const rows = data.map((m) => ({ ...m, label: shortMonth(m.month) }));
  return (
    <div>
      {table ? (
        <table className="w-full text-sm">
          <thead className="text-xs text-zinc-500">
            <tr>
              <th className="py-1 text-left font-medium">Mês</th>
              <th className="py-1 text-right font-medium">Entradas</th>
              <th className="py-1 text-right font-medium">Saídas</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {rows.map((m) => (
              <tr key={m.month} className="border-t border-zinc-100">
                <td className="py-1">{m.label}</td>
                <td className="py-1 text-right">{formatCents(m.income_cents)}</td>
                <td className="py-1 text-right">{formatCents(m.expense_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="h-64" role="img" aria-label="Entradas e saídas por mês">
          <ResponsiveContainer>
            <BarChart
              data={rows}
              barGap={2}
              barCategoryGap="28%"
              margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: "var(--chart-grid)" }}
                fontSize={12}
                stroke="var(--chart-axis)"
              />
              <YAxis
                tickFormatter={(v: number) => formatCompact(v)}
                tickLine={false}
                axisLine={false}
                fontSize={12}
                width={72}
                stroke="var(--chart-axis)"
              />
              <Tooltip
                cursor={{ fill: "rgba(11,11,11,0.04)" }}
                formatter={(value) => formatCents(Number(value))}
                labelClassName="font-medium"
              />
              <Legend
                iconType="square"
                iconSize={10}
                wrapperStyle={{ fontSize: 12 }}
                // Legend text stays in neutral ink; the swatch carries the series color.
                formatter={(value) => <span className="text-zinc-700">{value}</span>}
              />
              <Bar
                dataKey="income_cents"
                name="Entradas"
                fill="var(--series-1)"
                radius={[4, 4, 0, 0]}
                maxBarSize={20}
              />
              <Bar
                dataKey="expense_cents"
                name="Saídas"
                fill="var(--series-2)"
                radius={[4, 4, 0, 0]}
                maxBarSize={20}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <button
        type="button"
        onClick={() => setTable((t) => !t)}
        className="mt-2 text-xs text-zinc-500 hover:text-zinc-900"
      >
        {table ? "Ver gráfico" : "Ver em tabela"}
      </button>
    </div>
  );
}

/** Ranked horizontal bars, one hue, largest first; a top-level category opens to its subcategories. */
export function CategoryBars({ data }: { data: CategoryTotal[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const max = Math.max(...data.map((c) => c.total_cents), 1);
  return (
    <ul className="space-y-3">
      {data.map((category) => {
        const key = category.category_id ?? -1;
        const expanded = open === key && category.children.length > 0;
        return (
          <li key={key}>
            <button
              type="button"
              className="w-full text-left"
              aria-expanded={category.children.length ? expanded : undefined}
              onClick={() => setOpen(expanded ? null : key)}
              disabled={!category.children.length}
            >
              <Meter
                label={category.name}
                value={category.total_cents}
                max={max}
                muted={category.category_id === null}
                chevron={category.children.length ? (expanded ? "▾" : "▸") : undefined}
              />
            </button>
            {expanded && (
              <ul className="mt-2 space-y-2 border-l border-zinc-200 pl-4">
                {category.children.map((child) => (
                  <li key={child.category_id ?? child.name}>
                    <Meter label={child.name} value={child.total_cents} max={max} small />
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Meter({
  label,
  value,
  max,
  muted = false,
  small = false,
  chevron,
}: {
  label: string;
  value: number;
  max: number;
  muted?: boolean;
  small?: boolean;
  chevron?: string;
}) {
  return (
    <div>
      <div className={`flex items-baseline justify-between gap-3 ${small ? "text-xs" : "text-sm"}`}>
        <span className="truncate text-zinc-700">
          {chevron && <span className="mr-1 text-zinc-400">{chevron}</span>}
          {label}
        </span>
        <span className="font-medium whitespace-nowrap text-zinc-900 tabular-nums">{formatCents(value)}</span>
      </div>
      <div className={`mt-1 overflow-hidden rounded-r ${small ? "h-1.5" : "h-2"}`}>
        <div
          className="h-full rounded-r-[4px]"
          style={{
            width: `${Math.max((value / max) * 100, 1)}%`,
            background: muted ? "var(--chart-axis)" : "var(--series-1)",
          }}
        />
      </div>
    </div>
  );
}

const BUDGET_STATUS = {
  ok: { label: "dentro", icon: "✓", color: "text-[#006300]" },
  warning: { label: "atenção", icon: "!", color: "text-amber-700" },
  over: { label: "estourou", icon: "✕", color: "text-red-700" },
} as const;

/** Spent (solid) plus committed installments (soft) against the limit (the full track). */
export function BudgetMeter({ budget, name }: { budget: BudgetStatus; name: string }) {
  const { limit_cents: limit, spent_cents: spent, committed_cents: committed } = budget;
  const scale = Math.max(limit, spent + committed);
  const status = BUDGET_STATUS[budget.status];
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="truncate text-zinc-700">{name}</span>
        <span className={`text-xs font-medium whitespace-nowrap ${status.color}`}>
          <span aria-hidden>{status.icon}</span> {status.label}
        </span>
      </div>
      <div className="relative mt-1 flex h-2 gap-[2px] overflow-hidden rounded-full bg-zinc-100">
        <div className="h-full bg-[var(--series-1)]" style={{ width: `${(spent / scale) * 100}%` }} />
        {committed > 0 && (
          <div
            className="h-full bg-[var(--series-1-soft)]"
            style={{ width: `${(committed / scale) * 100}%` }}
          />
        )}
        {scale > limit && (
          <div
            className="absolute inset-y-0 w-0.5 bg-zinc-900"
            style={{ left: `${(limit / scale) * 100}%` }}
            aria-hidden
          />
        )}
      </div>
      <p className="mt-1 text-xs text-zinc-500 tabular-nums">
        {formatCents(spent)} gastos
        {committed > 0 && ` + ${formatCents(committed)} em parcelas`} de {formatCents(limit)}
      </p>
    </div>
  );
}

/** A handful of months: columns with the value on the cap, one hue, no legend (one series). */
export function CommitmentColumns({ data }: { data: Commitment[] }) {
  const max = Math.max(...data.map((c) => c.amount_cents), 1);
  if (data.every((c) => c.amount_cents === 0)) {
    return <p className="text-sm text-zinc-500">Nenhuma parcela por vir.</p>;
  }
  return (
    <ol className="flex h-40 items-end gap-2">
      {data.map((c, i) => (
        <li key={c.month} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
          {/* Labels only where the story is: next month and the last one shown. The rest is one hover away. */}
          <span className="text-[11px] text-zinc-600 tabular-nums">
            {c.amount_cents && (i === 0 || i === data.length - 1) ? formatRounded(c.amount_cents) : "\u00a0"}
          </span>
          <div
            className="w-full max-w-6 rounded-t-[4px] bg-[var(--series-1)]"
            style={{ height: `${(c.amount_cents / max) * 75}%` }}
            title={`${shortMonth(c.month)}: ${formatCents(c.amount_cents)}`}
          />
          <span className="text-xs text-zinc-500">{shortMonth(c.month)}</span>
        </li>
      ))}
    </ol>
  );
}
