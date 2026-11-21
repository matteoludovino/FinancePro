"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge, Card, Loading, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, monthLabel, shortDate } from "@/lib/dates";
import { formatCents } from "@/lib/money";
import type { Account, Installments, Statement } from "@/lib/types";

const STATUS: Record<Statement["status"], { label: string; tone: "zinc" | "amber" | "emerald" | "red" }> = {
  open: { label: "aberta", tone: "zinc" },
  paid: { label: "paga", tone: "emerald" },
  partial: { label: "paga em parte", tone: "amber" },
  unpaid: { label: "pagamento não importado", tone: "amber" },
};

export default function CardsPage() {
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/accounts") });
  const cards = accounts.data?.filter((a) => a.kind === "credit_card") ?? [];
  const [chosen, setChosen] = useState<number | null>(null);
  const cardId = chosen ?? cards[0]?.id ?? null;

  if (accounts.isPending) return <Loading />;
  return (
    <>
      <PageHeader
        title="Cartões"
        description="Faturas por ciclo de fechamento e as compras parceladas que ainda vão cair."
        action={
          cards.length > 1 ? (
            <Select
              aria-label="Cartão"
              value={cardId ?? ""}
              onChange={(e) => setChosen(Number(e.target.value))}
            >
              {cards.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          ) : undefined
        }
      />
      {cardId === null ? (
        <Card className="text-sm text-zinc-600">
          Nenhum cartão cadastrado.{" "}
          <Link href="/contas" className="font-medium text-emerald-700 hover:underline">
            Cadastre um em Contas
          </Link>
          .
        </Card>
      ) : (
        <div className="space-y-8">
          <Statements cardId={cardId} />
          <InstallmentList accounts={accounts.data ?? []} />
        </div>
      )}
    </>
  );
}

function Statements({ cardId }: { cardId: number }) {
  const statements = useQuery({
    queryKey: ["statements", cardId],
    queryFn: () => api.get<Statement[]>(`/accounts/${cardId}/statements`),
  });
  if (statements.isPending) return <Loading />;
  if (!statements.data?.length) {
    return <Card className="text-sm text-zinc-600">Importe o extrato do cartão para ver as faturas.</Card>;
  }
  return (
    <section aria-labelledby="statements-title">
      <h2 id="statements-title" className="mb-3 text-lg font-semibold text-zinc-900">
        Faturas
      </h2>
      <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 bg-white">
        {statements.data.map((s) => (
          <li key={s.month} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="font-medium text-zinc-900 first-letter:uppercase">
                {monthLabel(s.month.slice(0, 7))}
              </p>
              <p className="text-xs text-zinc-500">
                compras de {shortDate(s.opens)} a {shortDate(s.closes)} · vence {formatDate(s.due)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-right">
                <span className="block font-medium tabular-nums">{formatCents(s.charges_cents)}</span>
                {s.paid_cents > 0 && s.status !== "paid" && (
                  <span className="block text-xs text-zinc-500">pago {formatCents(s.paid_cents)}</span>
                )}
              </span>
              <Badge tone={STATUS[s.status].tone}>{STATUS[s.status].label}</Badge>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function InstallmentList({ accounts }: { accounts: Account[] }) {
  const groups = useQuery({
    queryKey: ["installments"],
    queryFn: () => api.get<Installments[]>("/installments"),
  });
  if (groups.isPending) return <Loading />;
  const running = groups.data?.filter((g) => g.future.length > 0) ?? [];
  const committed = running.reduce((sum, g) => sum + g.future.reduce((s, f) => s + f.amount_cents, 0), 0);
  return (
    <section aria-labelledby="installments-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <h2 id="installments-title" className="text-lg font-semibold text-zinc-900">
          Parcelas em andamento
        </h2>
        {running.length > 0 && (
          <p className="text-sm text-zinc-600">
            Ainda vão cair <span className="font-medium text-zinc-900">{formatCents(-committed)}</span>
          </p>
        )}
      </div>
      {running.length === 0 ? (
        <Card className="text-sm text-zinc-600">Nenhuma compra parcelada em andamento.</Card>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {running.map((g) => {
            const left = g.future.reduce((s, f) => s + f.amount_cents, 0);
            return (
              <li key={g.id}>
                <Card>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-zinc-900">{g.merchant}</p>
                      <p className="text-xs text-zinc-500">
                        {accounts.find((a) => a.id === g.account_id)?.name} · {g.installments}×{" "}
                        {formatCents(-g.amount_cents)}
                      </p>
                    </div>
                    <span className="text-sm whitespace-nowrap text-zinc-700 tabular-nums">
                      {g.paid}/{g.installments}
                    </span>
                  </div>
                  <div
                    className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-100"
                    role="progressbar"
                    aria-label={`${g.paid} de ${g.installments} parcelas`}
                    aria-valuemin={0}
                    aria-valuemax={g.installments}
                    aria-valuenow={g.paid}
                  >
                    <div
                      className="h-full bg-emerald-600"
                      style={{ width: `${(g.paid / g.installments) * 100}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-zinc-500">
                    Faltam {g.future.length} · {formatCents(-left)} · última em{" "}
                    {monthLabel(g.future[g.future.length - 1].month.slice(0, 7))}
                  </p>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
