# 2. Server-side sessions behind a same-origin rewrite

## Context

The web app (Next.js on Vercel) and the API (FastAPI on Render) live on different hosts. Tokens in `localStorage` are readable by any script that runs on the page; cross-site cookies are being phased out by browsers.

## Decision

- The web app reaches the API at `/api` on its own origin, through a rewrite. The session cookie is first-party: `HttpOnly`, `SameSite=Lax`, and `__Host-` prefixed in production.
- Sessions live in the database. The cookie holds a random token; the table holds only its SHA-256, so a leaked table signs no one in. Signing out deletes the row: an old copy of the cookie stops working.
- Every state-changing request must carry the app's own `Origin` (or `Sec-Fetch-Site: same-origin`). SameSite already keeps the cookie off most cross-site posts; this check also covers `multipart/form-data` uploads, which a form on any site can send without a preflight.
- Passwords use Argon2id at OWASP's minimum profile (19 MiB). A semaphore allows two hashes at a time: FastAPI runs synchronous endpoints on up to 40 threads, and 40 concurrent hashes would not fit in the 512 MB instance.
- Sign-in attempts are limited per e-mail, plus a global ceiling. Behind the rewrite every visitor arrives from Vercel's addresses, so a per-IP limit would lock everyone out together.

## Consequences

Every request costs one indexed lookup. All data is fetched by the browser through the rewrite (Server Components would have to forward cookies by hand, can't set them, and would wait on the API's cold start at every navigation).
