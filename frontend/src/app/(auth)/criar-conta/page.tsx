"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Button, Field, formValues, Input } from "@/components/ui";
import { api, ApiError, errorMessage, fieldError } from "@/lib/api";
import { ME } from "@/lib/session";
import type { User } from "@/lib/types";

export default function SignupPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const signup = useMutation({
    mutationFn: (values: Record<string, string>) => api.post<User>("/auth/signup", values),
    onSuccess: (user) => {
      queryClient.setQueryData(ME, user);
      router.replace("/painel");
    },
  });
  const formLevelError =
    signup.error instanceof ApiError && Object.keys(signup.error.errors).some((f) => f !== "_")
      ? null
      : signup.error && errorMessage(signup.error);
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        signup.mutate(formValues(event.currentTarget));
      }}
    >
      <h1 className="text-xl font-semibold text-zinc-900">Criar conta</h1>
      <Field label="Nome" error={fieldError(signup.error, "name")}>
        {(props) => (
          <Input {...props} name="name" autoComplete="given-name" required autoFocus maxLength={80} />
        )}
      </Field>
      <Field label="E-mail" error={fieldError(signup.error, "email")}>
        {(props) => <Input {...props} name="email" type="email" autoComplete="email" required />}
      </Field>
      <Field label="Senha" hint="Pelo menos 10 caracteres." error={fieldError(signup.error, "password")}>
        {(props) => (
          <Input
            {...props}
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
          />
        )}
      </Field>
      <Alert>{formLevelError}</Alert>
      <Button type="submit" busy={signup.isPending} className="w-full">
        Criar conta
      </Button>
      <p className="text-center text-sm text-zinc-600">
        Já tem conta?{" "}
        <Link href="/entrar" className="font-medium text-emerald-700 hover:underline">
          Entrar
        </Link>
      </p>
    </form>
  );
}
