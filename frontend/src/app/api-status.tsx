"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "up" | "down";

const LABEL: Record<Status, string> = {
  checking: "Verificando a API…",
  up: "API no ar",
  down: "API fora do ar",
};

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");
  useEffect(() => {
    fetch("/api/health")
      .then((response) => setStatus(response.ok ? "up" : "down"))
      .catch(() => setStatus("down"));
  }, []);
  return (
    <p role="status" className="text-sm text-zinc-500">
      {LABEL[status]}
    </p>
  );
}
