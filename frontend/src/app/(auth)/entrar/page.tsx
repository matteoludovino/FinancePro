"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { DemoButton } from "@/components/demo-button";
import { Alert, Button, Field, formValues, Input } from "@/components/ui";
import { api, errorMessage, fieldError } from "@/lib/api";
import { DEMO_MODE } from "@/lib/demo";
import { safeNext } from "@/lib/navigation";
import { ME } from "@/lib/session";
import type { User } from "@/lib/types";

function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const queryClient = useQueryClient();
  const login = useMutation({
    mutationFn: (values: Record<string, string>) => api.post<User>("/auth/login", values),
    onSuccess: (user) => {
      queryClient.setQueryData(ME, user);
      router.replace(next);
    },
  });
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        login.mutate(formValues(event.currentTarget));
      }}
    >
      <h1 className="text-xl font-semibold text-zinc-900">Entrar</h1>
      <Field label="E-mail" error={fieldError(login.error, "email")}>
        {(props) => <Input {...props} name="email" type="email" autoComplete="email" required autoFocus />}
      </Field>
      <Field label="Senha" error={fieldError(login.error, "password")}>
        {(props) => (
          <Input {...props} name="password" type="password" autoComplete="current-password" required />
        )}
      </Field>
      <Alert>{login.error && !fieldError(login.error, "email") ? errorMessage(login.error) : null}</Alert>
      <Button type="submit" busy={login.isPending} className="w-full">
        Entrar
      </Button>
      {DEMO_MODE ? (
        <div className="border-t border-zinc-200 pt-4">
          <DemoButton className="w-full" />
        </div>
      ) : (
        <p className="text-center text-sm text-zinc-600">
          Não tem conta?{" "}
          <Link href="/criar-conta" className="font-medium text-emerald-700 hover:underline">
            Criar conta
          </Link>
        </p>
      )}
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
