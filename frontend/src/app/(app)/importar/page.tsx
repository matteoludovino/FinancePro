"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { MappingEditor } from "@/components/mapping-editor";
import { Alert, Badge, Button, Card, Field, Loading, PageHeader, Select } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { categoryLabel, useCategories } from "@/lib/categories";
import { formatDate, shortDate } from "@/lib/dates";
import { formatCents } from "@/lib/money";
import type { Account, Batch, Category, Mapping, PreviewRow, RowStatus } from "@/lib/types";

const IMPORTS = ["imports"] as const;

const STATUS: Record<RowStatus, { label: string; tone: "emerald" | "zinc" | "amber" | "red" }> = {
  new: { label: "novo", tone: "emerald" },
  duplicate: { label: "já importado", tone: "zinc" },
  possible_duplicate: { label: "possível duplicado", tone: "amber" },
  error: { label: "com erro", tone: "red" },
};

const SAMPLES = [
  { file: "nubank-conta.csv", label: "Conta Nubank" },
  { file: "nubank-conta-atualizado.csv", label: "Conta Nubank, extrato mais recente" },
  { file: "nubank-cartao.csv", label: "Cartão Nubank" },
];

export default function ImportPage() {
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get<Account[]>("/accounts") });
  const [batch, setBatch] = useState<Batch | null>(null);

  if (accounts.isPending) return <Loading />;
  const active = accounts.data?.filter((a) => !a.is_archived) ?? [];
  const accountName = (id: number) => accounts.data?.find((a) => a.id === id)?.name ?? "";

  return (
    <>
      <PageHeader
        title="Importar extrato"
        description="Envie o CSV que o seu banco exporta. Nada é gravado antes de você conferir a prévia."
      />
      {active.length === 0 ? (
        <Card className="text-sm text-zinc-600">
          Cadastre uma conta antes de importar.{" "}
          <Link href="/contas" className="font-medium text-emerald-700 hover:underline">
            Ir para Contas
          </Link>
        </Card>
      ) : batch === null ? (
        <>
          <UploadForm accounts={active} onUploaded={setBatch} />
          <History accountName={accountName} />
        </>
      ) : batch.status === "preview" ? (
        <Preview batch={batch} accountName={accountName(batch.account_id)} onChange={setBatch} />
      ) : (
        <Result batch={batch} onAgain={() => setBatch(null)} onUndone={() => setBatch(null)} />
      )}
    </>
  );
}

function UploadForm({ accounts, onUploaded }: { accounts: Account[]; onUploaded: (batch: Batch) => void }) {
  const [accountId, setAccountId] = useState(String(accounts[0].id));
  const [dragging, setDragging] = useState(false);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("account_id", accountId);
      form.append("file", file);
      return api.upload<Batch>("/imports", form);
    },
    onSuccess: onUploaded,
  });
  const pick = (files: FileList | null) => {
    if (files?.[0]) upload.mutate(files[0]);
  };

  return (
    <Card className="space-y-5">
      <Field label="Para qual conta é este extrato?">
        {(props) => (
          <Select {...props} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center ${
          dragging ? "border-emerald-600 bg-emerald-50" : "border-zinc-300 hover:border-emerald-600"
        }`}
      >
        <span className="font-medium text-zinc-900">
          {upload.isPending ? "Lendo o arquivo…" : "Arraste o arquivo CSV aqui ou clique para escolher"}
        </span>
        <span className="text-sm text-zinc-500">Até 2 MB e 5 mil linhas.</span>
        <input
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          disabled={upload.isPending}
          onChange={(e) => {
            pick(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
      <Alert>{upload.error && errorMessage(upload.error)}</Alert>
      <p className="text-sm text-zinc-600">
        Sem um extrato à mão? Baixe um exemplo fictício:{" "}
        {SAMPLES.map((sample, i) => (
          <span key={sample.file}>
            {i > 0 && " · "}
            <a href={`/api/samples/${sample.file}`} download className="text-emerald-700 hover:underline">
              {sample.label}
            </a>
          </span>
        ))}
      </p>
    </Card>
  );
}

function Preview({
  batch,
  accountName,
  onChange,
}: {
  batch: Batch;
  accountName: string;
  onChange: (batch: Batch | null) => void;
}) {
  const queryClient = useQueryClient();
  const categories = useCategories();
  const [filter, setFilter] = useState<RowStatus | "all">("all");
  const [include, setInclude] = useState<Set<number>>(new Set());
  const [showMapping, setShowMapping] = useState(batch.mapping === null || batch.warnings.length > 0);

  const remap = useMutation({
    mutationFn: (mapping: Mapping) => api.put<Batch>(`/imports/${batch.id}/mapping`, mapping),
    onSuccess: onChange,
  });
  const confirm = useMutation({
    mutationFn: () => api.post<Batch>(`/imports/${batch.id}/confirm`, { include_lines: [...include] }),
    onSuccess: (done) => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: IMPORTS });
      onChange(done);
    },
  });
  const cancel = useMutation({
    mutationFn: () => api.delete(`/imports/${batch.id}`),
    onSettled: () => onChange(null),
  });

  const summary = batch.summary;
  const toImport = (summary.new ?? 0) + include.size;
  const rows = filter === "all" ? batch.rows : batch.rows.filter((r) => r.status === filter);

  return (
    <div className="space-y-5">
      <Card className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-medium text-zinc-900">{batch.filename}</p>
            <p className="text-sm text-zinc-500">para {accountName}</p>
          </div>
          <Badge tone={batch.mapping ? "emerald" : "amber"}>{batch.label}</Badge>
        </div>
        {batch.warnings.map((warning) => (
          <p key={warning} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {warning}
          </p>
        ))}
        <button
          type="button"
          onClick={() => setShowMapping((v) => !v)}
          className="text-sm font-medium text-emerald-700 hover:underline"
          aria-expanded={showMapping}
        >
          {showMapping ? "Esconder as colunas" : "Conferir as colunas"}
        </button>
        {showMapping && (
          <MappingEditor
            key={JSON.stringify(batch.mapping)}
            header={batch.header}
            sample={batch.sample}
            mapping={batch.mapping}
            busy={remap.isPending}
            onApply={(mapping) => remap.mutate(mapping)}
          />
        )}
        <Alert>{remap.error && errorMessage(remap.error)}</Alert>
      </Card>

      {batch.mapping && (
        <>
          <div role="tablist" aria-label="Filtrar linhas" className="flex flex-wrap gap-2">
            {(["all", "new", "duplicate", "possible_duplicate", "error"] as const).map((key) => {
              const count = key === "all" ? summary.total : summary[key];
              if (key !== "all" && !count) return null;
              return (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={filter === key}
                  onClick={() => setFilter(key)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    filter === key
                      ? "border-emerald-700 bg-emerald-50 text-emerald-900"
                      : "border-zinc-300 text-zinc-700"
                  }`}
                >
                  {key === "all" ? "Todas" : STATUS[key].label} · {count ?? 0}
                </button>
              );
            })}
          </div>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Linha</th>
                  <th className="px-3 py-2 font-medium">Data</th>
                  <th className="px-3 py-2 font-medium">Descrição</th>
                  <th className="px-3 py-2 font-medium">Categoria</th>
                  <th className="px-3 py-2 text-right font-medium">Valor</th>
                  <th className="px-3 py-2 font-medium">Situação</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <PreviewLine
                    key={row.line}
                    row={row}
                    categories={categories.data ?? []}
                    included={include.has(row.line)}
                    onInclude={(on) =>
                      setInclude((current) => {
                        const next = new Set(current);
                        if (on) next.add(row.line);
                        else next.delete(row.line);
                        return next;
                      })
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Alert>{(confirm.error ?? cancel.error) && errorMessage(confirm.error ?? cancel.error)}</Alert>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" busy={cancel.isPending} onClick={() => cancel.mutate()}>
          Cancelar
        </Button>
        <Button
          disabled={!batch.mapping || toImport === 0}
          busy={confirm.isPending}
          onClick={() => confirm.mutate()}
        >
          {toImport === 0
            ? "Nada novo para importar"
            : `Importar ${toImport} lançamento${toImport === 1 ? "" : "s"}`}
        </Button>
      </div>
    </div>
  );
}

function PreviewLine({
  row,
  categories,
  included,
  onInclude,
}: {
  row: PreviewRow;
  categories: Category[];
  included: boolean;
  onInclude: (on: boolean) => void;
}) {
  const status = STATUS[row.status];
  const muted = row.status === "duplicate" || row.status === "error";
  return (
    <tr className={`border-t border-zinc-100 align-top ${muted ? "text-zinc-400" : ""}`}>
      <td className="px-3 py-2 text-xs tabular-nums">{row.line}</td>
      <td className="px-3 py-2 whitespace-nowrap">{row.date ? shortDate(row.date) : "—"}</td>
      <td className="max-w-80 px-3 py-2">
        <p className="truncate font-medium">{row.merchant || row.description}</p>
        {row.merchant && row.merchant !== row.description && (
          <p className="truncate text-xs text-zinc-500">{row.description}</p>
        )}
        {row.message && <p className="text-xs text-red-700">{row.message}</p>}
        {row.match && (
          <div className="mt-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">
            Parecido com {formatDate(row.match.date)} · {row.match.description} ·{" "}
            {formatCents(row.match.amount_cents)}
            <label className="mt-1 flex items-center gap-1.5">
              <input type="checkbox" checked={included} onChange={(e) => onInclude(e.target.checked)} />
              Importar mesmo assim
            </label>
          </div>
        )}
      </td>
      <td className="px-3 py-2 text-xs">
        {muted ? (
          ""
        ) : row.kind === "transfer" ? (
          "Transferência"
        ) : row.kind === "ignored" ? (
          "Ignorada"
        ) : row.category_id === null ? (
          <span className="text-zinc-400">sem categoria</span>
        ) : (
          categoryLabel(categories, row.category_id)
        )}
      </td>
      <td
        className={`px-3 py-2 text-right whitespace-nowrap tabular-nums ${
          !muted && (row.amount_cents ?? 0) > 0 ? "text-emerald-700" : ""
        }`}
      >
        {row.amount_cents === null ? "—" : formatCents(row.amount_cents)}
      </td>
      <td className="px-3 py-2">
        <Badge tone={status.tone}>{status.label}</Badge>
      </td>
    </tr>
  );
}

function Result({ batch, onAgain, onUndone }: { batch: Batch; onAgain: () => void; onUndone: () => void }) {
  const inserted = batch.summary.inserted ?? 0;
  const duplicate = batch.summary.duplicate ?? 0;
  return (
    <Card className="space-y-4">
      <h2 className="text-lg font-semibold text-zinc-900">
        {inserted === 1 ? "1 lançamento importado" : `${inserted} lançamentos importados`}
      </h2>
      <p className="text-sm text-zinc-600">
        {duplicate > 0 && `${duplicate} já estavam no app e ficaram de fora. `}
        Confira as categorias na tela de lançamentos.
      </p>
      <div className="flex flex-wrap gap-2">
        <Link
          href="/lancamentos"
          className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
        >
          Ver lançamentos
        </Link>
        <Button variant="secondary" onClick={onAgain}>
          Importar outro arquivo
        </Button>
        <UndoButton batch={batch} onUndone={onUndone} />
      </div>
    </Card>
  );
}

function UndoButton({ batch, onUndone }: { batch: Batch; onUndone: () => void }) {
  const queryClient = useQueryClient();
  const [needsConfirmation, setNeedsConfirmation] = useState<string | null>(null);
  const undo = useMutation({
    mutationFn: (discardEdits: boolean) =>
      api.post<Batch>(`/imports/${batch.id}/undo`, { discard_edits: discardEdits }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: IMPORTS });
      onUndone();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) setNeedsConfirmation(error.detail);
    },
  });
  if (needsConfirmation) {
    return (
      <span className="flex flex-wrap items-center gap-2 text-sm text-amber-900">
        {needsConfirmation}
        <Button
          variant="danger"
          className="px-3 py-1"
          busy={undo.isPending}
          onClick={() => undo.mutate(true)}
        >
          Desfazer mesmo assim
        </Button>
      </span>
    );
  }
  return (
    <Button variant="ghost" className="text-red-700" busy={undo.isPending} onClick={() => undo.mutate(false)}>
      Desfazer esta importação
    </Button>
  );
}

function History({ accountName }: { accountName: (id: number) => string }) {
  const history = useQuery({ queryKey: IMPORTS, queryFn: () => api.get<Batch[]>("/imports") });
  if (!history.data?.length) return null;
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-lg font-semibold text-zinc-900">Importações anteriores</h2>
      <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 bg-white">
        {history.data.map((batch) => (
          <li key={batch.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
            <div>
              <p className="font-medium text-zinc-900">{batch.filename}</p>
              <p className="text-xs text-zinc-500">
                {accountName(batch.account_id)} · {batch.summary.inserted ?? 0} importados
                {batch.committed_at && ` em ${new Date(batch.committed_at).toLocaleDateString("pt-BR")}`}
              </p>
            </div>
            {batch.status === "undone" ? (
              <Badge>desfeita</Badge>
            ) : (
              <UndoButton batch={batch} onUndone={() => void history.refetch()} />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
