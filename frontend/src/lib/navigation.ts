/**
 * Where to go after signing in. Only paths inside this app: following any URL in `?next=` would turn
 * the sign-in page into an open redirect (a link that lands on a look-alike site after a real login).
 */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/painel";
  return next;
}
