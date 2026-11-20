// The API lives at /api on this origin (a rewrite to FastAPI), so the session cookie is first-party.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    /** Field name → message, for forms. */
    readonly errors: Record<string, string> = {},
  ) {
    super(detail);
  }
}

const GENERIC = "Algo deu errado. Tente de novo em instantes.";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "Sem conexão com o servidor. Verifique sua internet.");
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const payload = (data ?? {}) as { detail?: unknown; errors?: Record<string, string> };
    const detail = typeof payload.detail === "string" ? payload.detail : GENERIC;
    throw new ApiError(response.status, detail, payload.errors ?? {});
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  delete: <T = void>(path: string, body?: unknown) => request<T>("DELETE", path, body),
};

/** The message to show for any error a query or mutation throws. */
export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.detail : GENERIC;
}

/** One field's message, if the API rejected that field. */
export function fieldError(error: unknown, field: string): string | undefined {
  return error instanceof ApiError ? error.errors[field] : undefined;
}
