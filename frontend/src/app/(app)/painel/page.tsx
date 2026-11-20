"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useMe } from "@/lib/session";
import type { Account } from "@/lib/types";

export default function DashboardPage() {
  const me = useMe();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/accounts") });
  const hasAccounts = (accounts.data?.length ?? 0) > 0;
  return (
    <>
      <PageHeader title={`Olá, ${me.data?.name ?? ""}`} description="Vamos organizar as suas finanças." />
      <Card className="space-y-3">
        <h2 className="font-medium text-zinc-900">Primeiros passos</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-zinc-700">
          <li className={hasAccounts ? "text-zinc-400 line-through" : undefined}>
            <Link href="/contas" className="text-emerald-700 hover:underline">
              Cadastre suas contas
            </Link>{" "}
            — a conta corrente, o cartão de crédito e onde mais o seu dinheiro estiver.
          </li>
          <li>Importe o extrato CSV que o seu banco exporta.</li>
          <li>Confira as categorias e defina o orçamento do mês.</li>
        </ol>
      </Card>
    </>
  );
}
