"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CategorySelect } from "@/components/category-select";
import { Alert, Badge, Button, Card, Loading, PageHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCategories } from "@/lib/categories";
import { formatCents } from "@/lib/money";
import type { AiGroup, AiStatus } from "@/lib/types";

const SUGGESTIONS = ["ai-suggestions"] as const;

const CONFIDENCE: Record<AiGroup["confidence"], { label: string; tone: "emerald" | "amber" | "zinc" }> = {
  high: { label: "confiança alta", tone: "emerald" },
  medium: { label: "confiança média", tone: "amber" },
  low: { label: "palpite", tone: "zinc" },
};

export default function SuggestionsPage() {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["ai-status"], queryFn: () => api.get<AiStatus>("/ai/status") });
  const groups = useQuery({ queryKey: SUGGESTIONS, queryFn: () => api.get<AiGroup[]>("/ai/suggestions") });
  const [progress, setProgress] = useState<string | null>(null);

  // One batch of up to 50 merchants per request; keep asking while some remain, so no request runs long.
  const ask = useMutation({
    mutationFn: async () => {
      let total = 0;
      for (let round = 0; round < 20; round++) {
        const step = await api.post<{ suggested: number; pending: number; message: string | null }>(
          "/ai/suggest",
        );
        total += step.suggested;
        if (step.message) return { total, message: step.message };
        if (step.pending === 0) return { total, message: null };
        setProgress(`Analisando… faltam ${step.pending} estabelecimentos.`);
      }
      return { total, message: null };
    },
    onSettled: () => {
      setProgress(null);
      void queryClient.invalidateQueries({ queryKey: SUGGESTIONS });
      void queryClient.invalidateQueries({ queryKey: ["ai-status"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const highConfidence = groups.data?.filter((g) => g.confidence === "high") ?? [];
  return (
    <>
      <PageHeader
        title="Sugestões da IA"
        description="Para o que as suas regras e os estabelecimentos conhecidos não categorizaram. Nada muda até você aceitar."
      />
      <Card className="mb-6 space-y-3">
        <p className="text-sm text-zinc-600">
          {status.data && !status.data.enabled
            ? "A IA não está ligada neste servidor: só respostas que ela já deu para estes estabelecimentos são usadas."
            : "A IA recebe só o nome do estabelecimento e se o dinheiro entrou ou saiu: nunca valores, datas, contas ou nomes de pessoas."}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button busy={ask.isPending} onClick={() => ask.mutate()}>
            Pedir sugestões
          </Button>
          {progress && <span className="text-sm text-zinc-600">{progress}</span>}
          {status.data?.enabled && (
            <span className="text-xs text-zinc-500">
              Uso hoje: {Math.round((status.data.used_today / status.data.daily_limit) * 100)}% do limite
              diário
            </span>
          )}
        </div>
        {ask.data && (
          <Alert tone="info">
            {ask.data.total > 0
              ? `${ask.data.total} lançamento(s) receberam sugestão.`
              : (ask.data.message ?? "Nada novo para sugerir.")}
          </Alert>
        )}
        <Alert>{ask.error && errorMessage(ask.error)}</Alert>
      </Card>

      {groups.isPending ? (
        <Loading />
      ) : groups.data?.length === 0 ? (
        <Card className="text-center text-sm text-zinc-600">Nenhuma sugestão esperando por você.</Card>
      ) : (
        <>
          {highConfidence.length > 1 && <AcceptAll groups={highConfidence} />}
          <ul className="space-y-3">
            {groups.data?.map((group) => (
              <SuggestionRow key={`${group.merchant}-${group.category_id}`} group={group} />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function useDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accept,
      ...body
    }: {
      accept: boolean;
      transaction_ids: number[];
      category_id?: number;
      create_rule?: boolean;
    }) => api.post(accept ? "/ai/suggestions/accept" : "/ai/suggestions/reject", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SUGGESTIONS });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });
}

function SuggestionRow({ group }: { group: AiGroup }) {
  const categories = useCategories();
  const decide = useDecision();
  const [category, setCategory] = useState(String(group.category_id));
  const [rule, setRule] = useState(true);
  const count = group.transaction_ids.length;
  return (
    <li>
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-medium text-zinc-900">
            <span className="truncate">{group.merchant}</span>
            <Badge tone={CONFIDENCE[group.confidence].tone}>{CONFIDENCE[group.confidence].label}</Badge>
          </p>
          <p className="truncate text-xs text-zinc-500">
            {count} lançamento{count === 1 ? "" : "s"} · {formatCents(group.total_cents)} · {group.example}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CategorySelect
            aria-label={`Categoria para ${group.merchant}`}
            className="py-1 text-xs sm:w-60"
            categories={categories.data ?? []}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
          <label className="inline-flex items-center gap-1.5 text-xs text-zinc-600">
            <input type="checkbox" checked={rule} onChange={(e) => setRule(e.target.checked)} />
            criar regra
          </label>
          <Button
            className="py-1"
            busy={decide.isPending}
            disabled={!category}
            onClick={() =>
              decide.mutate({
                accept: true,
                transaction_ids: group.transaction_ids,
                category_id: Number(category),
                create_rule: rule,
              })
            }
          >
            Aceitar
          </Button>
          <Button
            variant="ghost"
            className="py-1"
            busy={decide.isPending}
            onClick={() => decide.mutate({ accept: false, transaction_ids: group.transaction_ids })}
          >
            Recusar
          </Button>
        </div>
        {decide.error && <Alert>{errorMessage(decide.error)}</Alert>}
      </Card>
    </li>
  );
}

function AcceptAll({ groups }: { groups: AiGroup[] }) {
  const decide = useDecision();
  const ids = groups.flatMap((g) => g.transaction_ids);
  return (
    <div className="mb-3 flex justify-end">
      <Button
        variant="secondary"
        busy={decide.isPending}
        onClick={() => decide.mutate({ accept: true, transaction_ids: ids, create_rule: true })}
      >
        Aceitar as {groups.length} de confiança alta (e criar regras)
      </Button>
    </div>
  );
}
