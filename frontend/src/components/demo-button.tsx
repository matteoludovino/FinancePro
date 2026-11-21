"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Button } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { ME } from "@/lib/session";
import type { User } from "@/lib/types";

/** Creates the visitor's own sandbox and signs them in. On the free plan the API may be asleep: after a
 * few seconds, say so instead of looking frozen. */
export function DemoButton({ className }: { className?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [slow, setSlow] = useState(false);
  const start = useMutation({
    mutationFn: () => api.post<User>("/demo/start"),
    onMutate: () => setSlow(false),
    onSuccess: (user) => {
      queryClient.setQueryData(ME, user);
      router.replace("/painel");
    },
  });
  useEffect(() => {
    if (!start.isPending) return;
    const timer = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(timer);
  }, [start.isPending]);
  return (
    <div className="space-y-2">
      <Button className={className} busy={start.isPending} onClick={() => start.mutate()}>
        Experimentar a demo
      </Button>
      {start.isPending && slow && (
        <p role="status" className="text-sm text-zinc-500">
          Acordando o servidor e preparando seus dados de exemplo… pode levar até um minuto na primeira
          visita.
        </p>
      )}
      <Alert>{start.error && errorMessage(start.error)}</Alert>
    </div>
  );
}
