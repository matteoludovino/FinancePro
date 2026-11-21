"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BudgetMeter } from "@/components/charts";
import { Alert, Button, Card, Input, Loading, PageHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { categoryTree, useCategories } from "@/lib/categories";
import { centsToInput, parseCents } from "@/lib/money";
import type { BudgetStatus, Category } from "@/lib/types";

const BUDGETS = ["reports", "/budgets"] as const;

export default function BudgetPage() {
  const categories = useCategories();
  const budgets = useQuery({
    queryKey: [...BUDGETS, "current"],
    queryFn: () => api.get<BudgetStatus[]>("/budgets"),
  });
  if (categories.isPending || budgets.isPending) return <Loading />;
  const byCategory = new Map((budgets.data ?? []).map((b) => [b.category_id, b]));
  const tree = categoryTree((categories.data ?? []).filter((c) => c.type === "expense" && !c.is_archived));
  return (
    <>
      <PageHeader
        title="Orçamento"
        description="Um limite por mês para as categorias que você quer acompanhar. Um novo valor vale deste mês em diante; os meses passados mantêm o limite que tinham."
      />
      <ul className="space-y-3">
        {tree.map(({ parent, children }) => (
          <li key={parent.id}>
            <Card className="space-y-3">
              <BudgetRow category={parent} budget={byCategory.get(parent.id)} strong />
              {children.map((child) => (
                <BudgetRow key={child.id} category={child} budget={byCategory.get(child.id)} />
              ))}
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}

function BudgetRow({
  category,
  budget,
  strong = false,
}: {
  category: Category;
  budget?: BudgetStatus;
  strong?: boolean;
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(budget ? centsToInput(budget.limit_cents) : "");
  const [invalid, setInvalid] = useState(false);
  const save = useMutation({
    mutationFn: (limit: number | null) => api.put(`/budgets/${category.id}`, { limit_cents: limit }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["reports"] }),
  });
  const submit = () => {
    const cents = value.trim() ? parseCents(value) : null;
    setInvalid(value.trim() !== "" && cents === null);
    if (value.trim() === "" || cents) save.mutate(cents);
  };
  return (
    <div className={strong ? "" : "border-t border-zinc-100 pt-3 pl-4"}>
      <div className="grid items-center gap-3 sm:grid-cols-[1fr_12rem]">
        {budget ? (
          <BudgetMeter budget={budget} name={category.name} />
        ) : (
          <p className={`text-sm ${strong ? "font-medium text-zinc-900" : "text-zinc-700"}`}>
            {category.name}
          </p>
        )}
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <Input
            aria-label={`Limite mensal de ${category.name}`}
            aria-invalid={invalid || undefined}
            inputMode="decimal"
            placeholder="Sem limite"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="py-1 text-sm"
          />
          <Button type="submit" variant="secondary" className="py-1" busy={save.isPending}>
            Salvar
          </Button>
        </form>
      </div>
      {(invalid || save.error) && (
        <Alert>{invalid ? "Use valores como 500 ou 1.234,56." : errorMessage(save.error)}</Alert>
      )}
    </div>
  );
}
