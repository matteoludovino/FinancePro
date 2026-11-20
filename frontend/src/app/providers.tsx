"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { ME } from "@/lib/session";

function makeClient(): QueryClient {
  // The session expired mid-use: forget the user, and the app shell sends them to the sign-in page.
  const signedOut = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) client.setQueryData(ME, null);
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: signedOut }),
    mutationCache: new MutationCache({ onError: signedOut }),
    defaultOptions: {
      queries: {
        // 4xx answers won't change by asking again; network hiccups and 5xx might.
        retry: (count, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
    },
  });
  return client;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
