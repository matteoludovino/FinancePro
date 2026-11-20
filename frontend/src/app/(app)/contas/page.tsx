"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
  Select,
} from "@/components/ui";
import { api, errorMessage, fieldError } from "@/lib/api";
import { ACCOUNT_KIND_LABEL, ACCOUNT_KINDS } from "@/lib/labels";
import type { Account, AccountKind } from "@/lib/types";

const ACCOUNTS = ["accounts"] as const;

export default function AccountsPage() {
  const accounts = useQuery({ queryKey: ACCOUNTS, queryFn: () => api.get<Account[]>("/accounts") });
  const [editing, setEditing] = useState<Account | "new" | null>(null);
  return (
    <>
      <PageHeader
        title="Contas"
        description="Onde o seu dinheiro está. Cada extrato importado pertence a uma conta."
        action={<Button onClick={() => setEditing("new")}>Nova conta</Button>}
      />
      {accounts.isPending ? (
        <Loading />
      ) : accounts.isError ? (
        <Alert>{errorMessage(accounts.error)}</Alert>
      ) : accounts.data.length === 0 ? (
        <Card className="text-center text-sm text-zinc-600">
          Nenhuma conta ainda. Comece pela conta corrente e pelo cartão de crédito.
        </Card>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {accounts.data.map((account) => (
            <li key={account.id}>
              <Card className={account.is_archived ? "opacity-60" : undefined}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-zinc-900">{account.name}</p>
                    <p className="text-sm text-zinc-500">
                      {ACCOUNT_KIND_LABEL[account.kind]}
                      {account.institution && ` · ${account.institution}`}
                    </p>
                    {account.kind === "credit_card" && (
                      <p className="mt-1 text-xs text-zinc-500">
                        Fecha dia {account.closing_day} · vence dia {account.due_day}
                      </p>
                    )}
                  </div>
                  {account.is_archived && <Badge>arquivada</Badge>}
                </div>
                <Button variant="ghost" className="mt-3 -ml-2 px-2 py-1" onClick={() => setEditing(account)}>
                  Editar
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === "new" ? "Nova conta" : "Editar conta"}
      >
        {editing !== null && (
          <AccountForm account={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
        )}
      </Dialog>
    </>
  );
}

function AccountForm({ account, onDone }: { account: Account | null; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<AccountKind>(account?.kind ?? "checking");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ACCOUNTS });

  const save = useMutation({
    mutationFn: (values: Record<string, string>) => {
      const days =
        kind === "credit_card"
          ? { closing_day: Number(values.closing_day) || null, due_day: Number(values.due_day) || null }
          : {};
      const body = { name: values.name, institution: values.institution, ...days };
      return account
        ? api.patch<Account>(`/accounts/${account.id}`, body)
        : api.post<Account>("/accounts", { ...body, kind });
    },
    onSuccess: () => {
      void refresh();
      onDone();
    },
  });
  const archive = useMutation({
    mutationFn: () => api.patch<Account>(`/accounts/${account!.id}`, { is_archived: !account!.is_archived }),
    onSuccess: () => {
      void refresh();
      onDone();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/accounts/${account!.id}`),
    onSuccess: () => {
      void refresh();
      onDone();
    },
  });

  const hint = ACCOUNT_KINDS.find((k) => k.value === kind)?.hint;
  const error = save.error ?? archive.error ?? remove.error;
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate(formValues(event.currentTarget));
      }}
    >
      {account ? (
        <p className="text-sm text-zinc-600">{ACCOUNT_KIND_LABEL[account.kind]}</p>
      ) : (
        <Field label="Tipo" hint={hint}>
          {(props) => (
            <Select {...props} value={kind} onChange={(e) => setKind(e.target.value as AccountKind)}>
              {ACCOUNT_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <Field label="Nome" error={fieldError(save.error, "name")}>
        {(props) => (
          <Input
            {...props}
            name="name"
            defaultValue={account?.name}
            required
            maxLength={60}
            placeholder="Ex.: Nubank"
            autoFocus
          />
        )}
      </Field>
      <Field label="Banco ou instituição (opcional)" error={fieldError(save.error, "institution")}>
        {(props) => (
          <Input {...props} name="institution" defaultValue={account?.institution} maxLength={60} />
        )}
      </Field>
      {kind === "credit_card" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Fecha no dia" error={fieldError(save.error, "closing_day")}>
            {(props) => (
              <Input
                {...props}
                name="closing_day"
                type="number"
                min={1}
                max={31}
                required
                defaultValue={account?.closing_day ?? ""}
              />
            )}
          </Field>
          <Field label="Vence no dia" error={fieldError(save.error, "due_day")}>
            {(props) => (
              <Input
                {...props}
                name="due_day"
                type="number"
                min={1}
                max={31}
                required
                defaultValue={account?.due_day ?? ""}
              />
            )}
          </Field>
        </div>
      )}
      <Alert>{error && !fieldError(error, "name") ? errorMessage(error) : null}</Alert>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {account ? (
          confirmDelete ? (
            <span className="flex items-center gap-2 text-sm">
              Excluir mesmo?
              <Button
                variant="danger"
                className="px-3 py-1"
                busy={remove.isPending}
                onClick={() => remove.mutate()}
              >
                Sim, excluir
              </Button>
            </span>
          ) : (
            <span className="flex gap-1">
              <Button
                variant="ghost"
                className="px-2"
                busy={archive.isPending}
                onClick={() => archive.mutate()}
              >
                {account.is_archived ? "Desarquivar" : "Arquivar"}
              </Button>
              <Button variant="ghost" className="px-2 text-red-700" onClick={() => setConfirmDelete(true)}>
                Excluir
              </Button>
            </span>
          )
        ) : (
          <span />
        )}
        <Button type="submit" busy={save.isPending}>
          Salvar
        </Button>
      </div>
    </form>
  );
}
