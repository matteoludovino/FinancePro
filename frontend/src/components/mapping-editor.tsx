"use client";

import { useState } from "react";
import { Button, Field, type FieldProps, Select } from "@/components/ui";
import type { DateFormat, Mapping } from "@/lib/types";

const DATE_FORMATS: { value: DateFormat; label: string }[] = [
  { value: "%d/%m/%Y", label: "31/12/2026" },
  { value: "%d/%m/%y", label: "31/12/26" },
  { value: "%Y-%m-%d", label: "2026-12-31" },
  { value: "%d-%m-%Y", label: "31-12-2026" },
  { value: "%d.%m.%Y", label: "31.12.2026" },
];

const EMPTY: Mapping = {
  date: 0,
  description: [1],
  amount: 2,
  debit: null,
  credit: null,
  external_id: null,
  date_format: "%d/%m/%Y",
  decimals: ",",
  sign: "as_is",
  installment_dates: "auto",
};

/** Which column is what, shown next to the file's first rows. */
export function MappingEditor({
  header,
  sample,
  mapping,
  busy,
  onApply,
}: {
  header: string[];
  sample: string[][];
  mapping: Mapping | null;
  busy: boolean;
  onApply: (mapping: Mapping) => void;
}) {
  const [draft, setDraft] = useState<Mapping>(mapping ?? EMPTY);
  const [split, setSplit] = useState(draft.amount === null);
  const set = (change: Partial<Mapping>) => setDraft((current) => ({ ...current, ...change }));
  const column = (
    props: FieldProps,
    value: number | null,
    onChange: (value: number | null) => void,
    optional = false,
  ) => (
    <Select
      {...props}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
    >
      {optional && <option value="">Nenhuma</option>}
      {header.map((name, index) => (
        <option key={index} value={index}>
          {name || `Coluna ${index + 1}`}
        </option>
      ))}
    </Select>
  );

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border border-zinc-200">
        <table className="w-full text-left text-xs">
          <thead className="bg-zinc-50 text-zinc-500">
            <tr>
              {header.map((name, index) => (
                <th key={index} className="px-3 py-2 font-medium whitespace-nowrap">
                  {name || `Coluna ${index + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sample.map((row, i) => (
              <tr key={i} className="border-t border-zinc-100">
                {row.map((cell, j) => (
                  <td key={j} className="max-w-56 truncate px-3 py-1.5 whitespace-nowrap text-zinc-700">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Data">{(props) => column(props, draft.date, (v) => set({ date: v ?? 0 }))}</Field>
        <Field label="Formato da data">
          {(props) => (
            <Select
              {...props}
              value={draft.date_format}
              onChange={(e) => set({ date_format: e.target.value as DateFormat })}
            >
              {DATE_FORMATS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Descrição">
          {(props) =>
            column(props, draft.description[0] ?? null, (v) =>
              set({ description: v === null ? draft.description : [v, ...draft.description.slice(1)] }),
            )
          }
        </Field>
        <Field label="Descrição complementar (opcional)">
          {(props) =>
            column(
              props,
              draft.description[1] ?? null,
              (v) => set({ description: v === null ? [draft.description[0]] : [draft.description[0], v] }),
              true,
            )
          }
        </Field>
        {split ? (
          <>
            <Field label="Débito (saídas)">
              {(props) => column(props, draft.debit, (v) => set({ debit: v }), true)}
            </Field>
            <Field label="Crédito (entradas)">
              {(props) => column(props, draft.credit, (v) => set({ credit: v }), true)}
            </Field>
          </>
        ) : (
          <Field label="Valor">{(props) => column(props, draft.amount, (v) => set({ amount: v }))}</Field>
        )}
        <Field label="Separador decimal">
          {(props) => (
            <Select
              {...props}
              value={draft.decimals}
              onChange={(e) => set({ decimals: e.target.value as "," | "." })}
            >
              <option value=",">Vírgula (1.234,56)</option>
              <option value=".">Ponto (1234.56)</option>
            </Select>
          )}
        </Field>
        <Field label="Parcelas vêm com a data">
          {(props) => (
            <Select
              {...props}
              value={draft.installment_dates}
              onChange={(e) => set({ installment_dates: e.target.value as Mapping["installment_dates"] })}
            >
              <option value="auto">Detectar</option>
              <option value="billing">Da fatura</option>
              <option value="purchase">Da compra original</option>
            </Select>
          )}
        </Field>
        <Field label="Identificador do banco (opcional)">
          {(props) => column(props, draft.external_id, (v) => set({ external_id: v }), true)}
        </Field>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-zinc-700">
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={split}
            onChange={(e) => {
              setSplit(e.target.checked);
              set(
                e.target.checked
                  ? { amount: null, debit: draft.amount, credit: null }
                  : { amount: draft.debit ?? 0, debit: null, credit: null },
              );
            }}
          />
          Valores em colunas separadas de débito e crédito
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={draft.sign === "inverted"}
            onChange={(e) => set({ sign: e.target.checked ? "inverted" : "as_is" })}
          />
          Compras aparecem como valores positivos (comum em cartão)
        </label>
      </div>
      <Button variant="secondary" busy={busy} onClick={() => onApply(draft)}>
        Reler o arquivo com estas colunas
      </Button>
    </div>
  );
}
