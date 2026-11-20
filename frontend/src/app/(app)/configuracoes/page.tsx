"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, Card, Dialog, Field, formValues, Input, PageHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/session";

export default function SettingsPage() {
  const me = useMe();
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <PageHeader title="Configurações" />
      <div className="space-y-6">
        <Card>
          <h2 className="font-medium text-zinc-900">Seus dados</h2>
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-zinc-500">Nome</dt>
            <dd>{me.data?.name}</dd>
            <dt className="text-zinc-500">E-mail</dt>
            <dd>{me.data?.email}</dd>
          </dl>
        </Card>
        <Card className="border-red-200">
          <h2 className="font-medium text-zinc-900">Excluir conta</h2>
          <p className="mt-1 text-sm text-zinc-600">
            Apaga você e tudo o que é seu: contas, lançamentos, regras e orçamentos. Não dá para desfazer.
          </p>
          <Button variant="danger" className="mt-4" onClick={() => setConfirming(true)}>
            Excluir minha conta
          </Button>
        </Card>
      </div>
      <Dialog open={confirming} onClose={() => setConfirming(false)} title="Excluir a conta?">
        <DeleteAccount sandbox={me.data?.is_sandbox ?? false} onCancel={() => setConfirming(false)} />
      </Dialog>
    </>
  );
}

function DeleteAccount({ sandbox, onCancel }: { sandbox: boolean; onCancel: () => void }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const remove = useMutation({
    mutationFn: (values: Record<string, string>) =>
      api.delete("/auth/me", { password: values.password || null }),
    onSuccess: () => {
      queryClient.clear();
      router.replace("/");
    },
  });
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        remove.mutate(formValues(event.currentTarget));
      }}
    >
      {!sandbox && (
        <Field label="Confirme com a sua senha">
          {(props) => (
            <Input
              {...props}
              name="password"
              type="password"
              autoComplete="current-password"
              required
              autoFocus
            />
          )}
        </Field>
      )}
      <Alert>{remove.error && errorMessage(remove.error)}</Alert>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" variant="danger" busy={remove.isPending}>
          Excluir para sempre
        </Button>
      </div>
    </form>
  );
}
