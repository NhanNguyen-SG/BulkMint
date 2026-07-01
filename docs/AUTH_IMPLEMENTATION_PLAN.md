# Authentication Implementation Plan

Status: **planned work — no implementation is authorized by this document**

Implement authentication as small, reviewable commits. Each commit should keep
the application buildable and must not include schema activation unless that
step receives separate approval.

## Preconditions

Before implementation:

- Confirm local Supabase remains the test target.
- Confirm the remote project's signing-key mode without changing it.
- Select the first sign-in method; email/password is the recommended baseline.
- Define local, preview, and production site URLs and redirect allowlists.
- Keep the proposed migration unapplied to the remote database.

## Commit sequence

### 1. Add authentication dependencies

Suggested commit:

```text
chore: add Supabase authentication dependencies
```

- Add `@supabase/ssr` to the frontend.
- Add a maintained Python JWT library with cryptographic support and an HTTP
  client or JWKS facility to the backend.
- Update lockfiles only.

Validation: clean frontend install/build and backend `uv sync`, Ruff, mypy, and
tests.

### 2. Define the environment contract

Suggested commit:

```text
chore: define authentication environment variables
```

- Replace the legacy frontend anonymous-key name with
  `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
- Add `NEXT_PUBLIC_API_URL`.
- Add the backend Supabase URL, publishable key, issuer, audience, and JWKS
  variable names.
- Add startup validation that reports missing names without printing values.
- Update examples and local-development documentation.

Validation: no values or secrets committed; both applications fail clearly
when required configuration is absent.

### 3. Add browser and server Supabase clients

Suggested commit:

```text
refactor: add Supabase SSR client boundaries
```

- Replace the singleton browser-only helper with browser and server factories.
- Add Next.js Proxy session refresh using verified claims.
- Preserve existing page behavior; do not enable RLS or change persistence.

Validation: session cookies refresh locally; frontend lint and build pass.

### 4. Add the minimal sign-in flow

Suggested commit:

```text
feat: add Supabase sign-in and sign-out
```

- Add sign-in, callback/error handling if required by the chosen provider, and
  sign-out.
- Avoid account-management features in this phase.
- Keep redirects restricted to configured application URLs.

Validation: successful sign-in, failed credentials, refresh, sign-out, and
browser restart restoration against local Supabase.

### 5. Protect the inventory route

Suggested commit:

```text
feat: require authentication for inventory
```

- Validate claims on the server before rendering inventory.
- Redirect unauthenticated requests to sign-in.
- Delay inventory queries until authentication is resolved.
- Display an explicit expired-session state.

Validation: anonymous access denied, authenticated route works, and sign-out
removes access without relying only on client state.

### 6. Verify Supabase JWTs in FastAPI

Suggested commit:

```text
feat: verify Supabase access tokens in FastAPI
```

- Add a reusable `current_user` dependency.
- Verify signature, allowed algorithm, issuer, audience, expiry, role, and UUID
  subject.
- Cache JWKS safely and retry once for an unknown key ID.
- Protect `/analyze-card` without changing its OpenAI prompt or response.
- Add unit tests for missing, malformed, expired, wrong-audience,
  wrong-issuer, wrong-role, invalid-signature, and valid tokens.

Validation: backend quality checks plus token tests using local signing keys.

### 7. Authenticate frontend-to-FastAPI requests

Suggested commit:

```text
feat: authenticate analysis API requests
```

- Read the current Supabase access token immediately before the request.
- Send it as a Bearer token to the configured API URL.
- Handle `401` by refreshing once or requiring sign-in; do not loop retries.
- Remove the hard-coded localhost API URL.

Validation: anonymous request rejected; authenticated request succeeds; expired
and signed-out sessions fail cleanly.

### 8. Put persistence behind FastAPI

Suggested commit:

```text
refactor: centralize card persistence in FastAPI
```

- Stop direct browser inserts.
- Use the verified user's token for user-scoped Supabase operations.
- Derive ownership from JWT `sub`; omit `owner_id` from public request models.
- Persist analysis results transactionally where the data contract allows.
- Do not use a secret key as the normal client.

Validation: forged ownership is impossible; failed writes do not create
optimistic phantom cards; RLS integration tests remain green.

### 9. Adopt the normalized database contract

Suggested commits:

```text
refactor: adopt normalized card and listing contracts
refactor: add authenticated inventory reads
```

- Introduce typed API models for cards, images, jobs, and listings.
- Replace legacy price and eBay fields with the proposed destinations.
- Use UUIDs, explicit fields, owner-scoped pagination, and statuses.
- Keep OpenAI prompt and marketplace behavior unchanged.

Validation: contract tests plus local two-user RLS tests.

### 10. Reconcile existing remote data

Suggested commit:

```text
chore: plan legacy card ownership backfill
```

- Read-only inventory of the remote schema requires separate approval and must
  precede any write.
- Create a reviewed migration for existing data rather than editing the initial
  fresh-schema proposal blindly.
- Map each existing row to an actual Supabase Auth user UUID.
- Define backup, dry-run, verification, and rollback procedures.

Validation: migration succeeds from a production-like snapshot locally; no
unowned or malformed rows remain.

### 11. Add end-to-end authorization tests

Suggested commit:

```text
test: add authenticated application coverage
```

Cover:

- anonymous frontend and API denial;
- owner inventory CRUD;
- cross-user read and write denial;
- forged `owner_id`;
- token expiry, refresh, and sign-out;
- unknown/revoked signing key behavior;
- service/secret-key isolation;
- audit-event visibility.

Validation: deterministic local run from a clean database reset.

### 12. Deploy compatible code, then activate RLS

This is an operational change, not part of the preceding implementation
commits. It requires explicit approval.

1. Back up and verify the remote database.
2. Deploy authentication-compatible application code.
3. Create or confirm the intended production user.
4. Apply the reviewed reconciliation migration.
5. Apply grants and RLS.
6. Run production-safe anonymous, owner, and cross-user checks.
7. Monitor authorization failures and data integrity.

Stop and roll back if the authenticated user cannot read/write owned records,
if anonymous access succeeds, or if remote data lacks a verified owner.

## Review gates

The following changes require separate review:

- enabling or configuring a remote Auth provider;
- rotating Supabase signing keys;
- introducing a secret/service-role key;
- applying any remote migration;
- changing the OpenAI prompt;
- changing marketplace behavior;
- deleting or rewriting existing card data.

## Recommended order

Implement commits 1–7 first to establish identity end to end. Then complete
commits 8–9 so application persistence matches the RLS contract. Only after
commit 11 passes should remote data reconciliation and RLS activation be
considered.
