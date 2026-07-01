# Authentication Architecture

Status: **design only — authentication is not implemented**

This document defines the target Supabase Auth architecture for BulkMint. It
does not authorize applying the proposed database migration or changing the
remote Supabase project.

## Current state

BulkMint currently has no authentication boundary:

- `frontend/lib/supabase.ts` creates one browser client with the project URL
  and legacy anonymous key.
- `frontend/app/page.tsx` reads and inserts `cards` directly without a session
  or `owner_id`.
- The browser calls `POST /analyze-card` without an `Authorization` header.
- `backend/main.py` accepts every request and does not validate a user.
- The backend has no Supabase or JWT dependency.
- No sign-in, sign-out, callback, protected route, or session-refresh code
  exists.

Applying the proposed RLS policies in this state would deny the inventory read
and insert operations. That is the expected secure behavior.

## Trust boundaries

| Component | Responsibility | Must not do |
|---|---|---|
| Supabase Auth | Authenticate users and issue/refresh access-token JWTs | Grant row ownership independently of RLS |
| Next.js frontend | Manage the browser session, gate protected UI, and send the access token to FastAPI | Store tokens manually or expose privileged keys |
| FastAPI backend | Verify every bearer token and derive the current user from verified claims | Trust `owner_id` supplied by a client |
| Supabase Data API/PostgreSQL | Enforce table grants, foreign keys, and RLS using the authenticated user's JWT | Treat the publishable key as user identity |
| Trusted worker/admin code | Perform narrowly defined privileged operations when required | Share a secret/service key with browser code |

Authentication proves identity. Authorization remains enforced at every
resource boundary, with PostgreSQL RLS as the final database control.

## Frontend session design

Use `@supabase/ssr` with separate browser and server clients:

- The browser client handles interactive sign-in, sign-out, and client-side
  Auth calls.
- The server client reads the session cookies in Server Components, Server
  Actions, and Route Handlers.
- A Next.js 16 `proxy.ts` refreshes expired tokens and writes refreshed cookies
  to both the request and response.
- Protected server code validates claims with `supabase.auth.getClaims()`.
  It must not trust `getSession()` as an authorization check on the server.
- Tokens remain in the Supabase-managed cookie/session mechanism. BulkMint
  must not copy them into local storage, custom cookies, URLs, logs, or
  application state.

The initial sign-in method should be email and password because it has the
smallest configuration surface. The architecture is provider-neutral, so a
magic link or OAuth provider can be added later without changing ownership.
Email confirmation and redirect URLs must be configured separately for local,
preview, and production environments before deployment.

The inventory route should render only after the server has validated the
session. A client-side loading check alone is not a security boundary.

Supabase's current SSR guidance requires browser and server clients, cookie
refresh through Next.js Proxy, and verified claims for protected server code:
[Supabase SSR client guidance](https://supabase.com/docs/guides/auth/server-side/creating-a-client).

## JWT verification in FastAPI

Every protected FastAPI endpoint accepts:

```text
Authorization: Bearer <supabase-access-token>
```

FastAPI should expose one reusable authentication dependency that:

1. Requires the Bearer scheme and rejects missing or malformed headers.
2. Reads the untrusted JWT header only to select a key and allowed algorithm.
3. Resolves the signing key from:
   `SUPABASE_URL/auth/v1/.well-known/jwks.json`.
4. Verifies the signature with a maintained JWT library and an explicit
   algorithm allowlist.
5. Validates `exp`, `iss`, and `aud`.
6. Requires `role` to be `authenticated`.
7. Parses `sub` as a UUID and returns it as the authenticated user ID.
8. Returns `401 Unauthorized` for an invalid token and `403 Forbidden` only
   when a valid user lacks permission.

The JWKS client should cache keys, retry discovery once when a token has an
unknown `kid`, and use bounded network timeouts. Logs may include the request
ID and rejection category, but never the token.

The project should use asymmetric Supabase signing keys. The JWKS endpoint does
not expose a verification key for a legacy symmetric signing secret. If the
remote project still issues legacy HS256 tokens, the temporary safe fallback is
server-side validation through Supabase Auth's user endpoint using the
publishable key. Do not distribute the legacy JWT secret to application code.

Supabase documents both the JWKS endpoint and the requirement to verify tokens
with a maintained library:
[Supabase JWT verification](https://supabase.com/docs/guides/auth/jwts) and
[Supabase signing keys](https://supabase.com/docs/guides/auth/signing-keys).

## Identity and `owner_id`

`owner_id` is exactly the authenticated Supabase user's UUID:

```text
verified JWT sub == auth.users.id == owner_id
```

The application must not maintain a second user identifier for ownership.
Email is mutable and must never be used as a foreign key.

For user-scoped inserts:

- The database default `owner_id default auth.uid()` assigns ownership when
  the user's JWT reaches the Data API.
- FastAPI derives the user UUID from the verified `sub`.
- Request schemas omit `owner_id`, or ignore and reject it if supplied.
- RLS `with check ((select auth.uid()) = owner_id)` prevents forged ownership.

Child records retain the composite `(resource_id, owner_id)` foreign keys from
the proposed migration, preventing cross-owner relationships.

Deleting an `auth.users` row currently cascades to owned records. Retention and
account-deletion requirements must be approved before the migration is applied.

## Authenticated API request flow

The target request flow is:

1. Supabase Auth establishes or refreshes the browser session.
2. Next.js validates the session before rendering protected inventory UI.
3. The browser obtains the current access token from the Supabase-managed
   session immediately before a FastAPI request.
4. The browser sends the token in the `Authorization` header.
5. FastAPI verifies the JWT and derives `current_user_id` from `sub`.
6. For user-owned database work, FastAPI calls Supabase with:
   - the project's publishable key as `apikey`; and
   - the user's access token as `Authorization: Bearer ...`.
7. PostgreSQL evaluates RLS using the same authenticated user.
8. FastAPI returns only data permitted for that user.

The access token is not a refresh token. FastAPI does not accept browser Auth
cookies, refresh sessions, or issue its own user token.

Using the user's token for normal database work preserves defense in depth:
FastAPI checks identity and RLS checks ownership. A secret key bypasses RLS and
must be isolated to explicit administrative or worker operations. It must
never be the default database client.

Supabase distinguishes the public application key from the user's JWT and
recommends publishable keys for public clients:
[Supabase API key guidance](https://supabase.com/docs/guides/getting-started/api-keys).

## API and browser security

- Permit only explicit frontend origins in FastAPI CORS configuration.
- Permit the `Authorization` header and required methods; do not broaden
  origins to `*` when credentials are enabled.
- Use HTTPS outside localhost. Tailscale transport does not remove the need
  for correct application authentication.
- Set a conservative upload-size limit and request timeout before exposing the
  analysis endpoint remotely.
- Never put access tokens, refresh tokens, publishable keys, or secret keys in
  URLs.
- Redact authorization headers and Auth payloads from logs and error tracking.
- Treat XSS as token/session compromise; keep dependencies current and avoid
  rendering untrusted HTML.
- Add rate limiting by verified user and source address before production
  exposure.

Bearer authentication avoids relying on cross-origin cookies for FastAPI, so
the API is not vulnerable to ordinary cookie-based CSRF. The Next.js Auth
callback and any future cookie-authenticated mutations still require the
framework's normal origin and redirect protections.

## Environment contract

Names only are defined here. Values remain uncommitted.

Frontend:

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
NEXT_PUBLIC_API_URL
```

Backend:

```text
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_JWT_ISSUER
SUPABASE_JWT_AUDIENCE
SUPABASE_JWKS_URL
```

`SUPABASE_JWT_AUDIENCE` should be `authenticated`. The issuer and JWKS URL
should be derived from and checked against `SUPABASE_URL`, while remaining
explicitly testable settings.

Add `SUPABASE_SECRET_KEY` only if a reviewed privileged operation actually
requires it. Never use the `NEXT_PUBLIC_` prefix for a secret or service-role
key.

## Required work before applying RLS

RLS must not be applied remotely until all of these gates pass:

1. Inspect the remote Auth signing-key mode and plan asymmetric-key use.
2. Implement and test SSR session creation, refresh, sign-in, and sign-out.
3. Protect inventory routes with server-verified claims.
4. Protect FastAPI endpoints with verified JWTs.
5. Send bearer tokens on every authenticated FastAPI request.
6. Make FastAPI the authoritative persistence boundary; remove direct browser
   writes that can diverge from analysis results.
7. Adopt the normalized cards, images, jobs, and listings API contract.
8. Inventory the remote `cards` schema and map every existing row to a verified
   `auth.users.id`.
9. Backfill `owner_id` and convert legacy price/listing fields in a separately
   reviewed migration.
10. Test anonymous denial, owner CRUD, cross-user denial, token expiry,
    sign-out, and key rotation locally and in a non-production environment.
11. Coordinate deployment of compatible application code with migration/RLS
    activation and define rollback steps.

No remote migration should run until the owner mapping is complete and the
user can sign in through the deployed application.

## Deliberate exclusions

- No Auth provider is enabled by this document.
- No frontend or backend dependency is added.
- No sign-in UI, API middleware, or session code is implemented.
- No database migration or remote Supabase setting is changed.
- No OpenAI prompt, analysis behavior, or marketplace code is changed.
