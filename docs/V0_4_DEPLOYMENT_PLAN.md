# BulkMint V0.4 Private Beta Deployment Plan

Status: **Phase 2 deployment foundation prepared locally — no external
resources changed**

Target release: `v0.3.1`

## Approval boundary

The repository configuration described in Phase 2 has been prepared. The
following external actions have **not** been done:

- no Supabase project was created, linked, or modified;
- no remote migration or `supabase db push` was run;
- no Railway or Vercel project was created or deployed;
- no OpenAI key was created, read, copied, or changed;
- no DNS or domain setting was changed;

Every provider account action and every production deployment still requires
a separate confirmation.

## Release baseline

- Latest release tag: `v0.3.1`
- Tag commit: `122c76a25021b94e3a36c66c1e067cafb5dc22f2`
- Remote tag: confirmed on `origin`
- Phase 2 was prepared from `main` after
  `2e03761d6dcb6043843ac6290671b5e40d4646bf`.
- The commit after the tag contains release notes only.

## Target architecture

| Component | Provider | Responsibility |
| --- | --- | --- |
| Frontend | Vercel | Next.js UI and Supabase Auth session handling |
| Backend | Railway | FastAPI, authorization, inventory API, image orchestration, OpenAI calls |
| Data | Supabase | Hosted Postgres, Auth, private Storage, RLS |
| AI | OpenAI API | Card analysis and listing-draft generation, called only by FastAPI |
| Source/CI | GitHub | Source repository and GitHub Actions |

The browser receives only the Supabase publishable key. The Supabase secret
key and OpenAI API key must exist only in Railway.

## Audit results

### Frontend

Ready:

- Next.js production build passes.
- ESLint passes.
- Dependencies are locked with `frontend/package-lock.json`.
- Supabase browser/server clients use `@supabase/ssr`.
- Authenticated API requests attach the user's Supabase access token.
- Missing and stale sessions are handled without exposing credentials.
- The existing `.gitignore` excludes `.env*` except examples.
- `frontend/.env.production.example` documents production values by name.
- `package.json` constrains Node to versions supported locally and by Vercel;
  CI and Vercel use Node 24.

External configuration still required:

- Set Vercel's Root Directory to `frontend`.
- Set all three production variables, including `NEXT_PUBLIC_API_URL`; its
  localhost fallback remains for local development only.
- Confirm the Vercel production URL before finalizing backend CORS and
  Supabase Auth URL settings.
- No `vercel.json` was added because Vercel auto-detects Next.js once the
  project Root Directory is `frontend`; there is no required file-based
  override.

Vercel supports importing one project for a selected directory in a monorepo
and environment variables scoped to Production, Preview, and Development:
[Vercel monorepos](https://vercel.com/docs/monorepos),
[environment variables](https://vercel.com/docs/environment-variables), and
[supported Node.js versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions).

### Backend

Ready:

- All 95 backend tests pass.
- Ruff and mypy pass.
- Dependencies and transitive versions are locked in `backend/uv.lock`.
- Supported Python range is `>=3.11,<3.15`.
- All inventory and listing endpoints require a verified Supabase JWT.
- Data operations use the user's access token and owner-scoped RLS.
- OpenAI is called only from backend code.
- Upload validation limits images to 10 MiB and JPEG, PNG, or WebP.
- Public `GET /health` returns only `{"status": "ok"}`.
- CORS origins are parsed and validated from `CORS_ALLOWED_ORIGINS`;
  development defaults to `http://localhost:3000`.
- `APP_ENV=production` requires explicit HTTPS origins and rejects localhost.
- `/docs`, `/redoc`, and `/openapi.json` are always disabled when
  `APP_ENV=production`.
- The Docker startup command binds Uvicorn to `0.0.0.0:$PORT`.
- Railway health and restart behavior is version-controlled.

Railway injects `PORT`; the application must listen on `0.0.0.0:$PORT`.
Railway can use `/health` during rollout, but that deployment health check is
not continuous monitoring:
[Railway public networking](https://docs.railway.com/public-networking) and
[health checks](https://docs.railway.com/deployments/healthchecks).

### Supabase database, Auth, and Storage

Present:

- Four ordered migrations under `supabase/migrations/`.
- Tables for cards, card images, analysis jobs, listing drafts, pricing
  provenance, and audit events.
- UUID ownership fields, foreign keys, checks, indexes, grants, and RLS.
- Private `card-images` bucket with a 10 MiB limit and JPEG/PNG/WebP allowlist.
- Local RLS, storage-policy, integrity, and cleanup test scripts.
- Local migrations and policy tests were validated before `v0.3.1`.

Remote status:

- **Not applied.**
- The repository has not been linked to a hosted Supabase project.
- No production migration history exists yet.
- Several migration comments still say `PROPOSAL ONLY` or `LOCAL-ONLY`.
  Comments do not prevent execution, but every migration must receive a final
  production review before approval.
- Local Supabase is configured for Postgres 17. The hosted project's database
  major version must be confirmed before linking.

Auth requirements:

- Use a publishable key in Vercel and Railway's user-scoped Supabase requests.
- Use an asymmetric JWT signing key supported by the current verifier
  (`ES256` or `RS256`).
- The backend verifies user JWTs from the hosted JWKS endpoint.
- Set the Supabase Auth Site URL to the final Vercel production URL.
- Add exact production redirect URLs; add preview wildcards only if preview
  authentication is intentionally approved.

Official references:

- [Supabase hosted platform and projects](https://supabase.com/docs/guides/platform)
- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [JWT signing keys](https://supabase.com/docs/guides/auth/signing-keys)
- [Auth redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls)
- [CLI migration dry runs](https://supabase.com/docs/reference/cli/supabase-db-push)

### Supabase secret-key compatibility

The backend audit writer now distinguishes hosted opaque secret keys from
legacy service-role JWTs.

New Supabase `sb_secret_...` keys are opaque API keys, not JWTs. Supabase
documents that they must not be used as bearer JWTs. `sb_secret_...` values
are now sent only as the `apikey`; legacy JWT values retain the bearer header
for local and migration compatibility. Focused tests cover both paths.

User-scoped repositories remain unchanged: publishable key in `apikey`, user
JWT in `Authorization`. Prefer `SUPABASE_SECRET_KEY` for private beta.
Supabase's current key guidance is documented in
[Understanding API keys](https://supabase.com/docs/guides/getting-started/api-keys).

### Docker readiness

Prepared:

- Python 3.12 slim runtime;
- dependency installation from `uv.lock` with development dependencies
  excluded;
- non-root user;
- Uvicorn bound to `0.0.0.0:$PORT`;
- image-level `/health` check;
- no `.env`, tests, caches, or local virtual environment copied into the image;
- Railway health check and `ON_FAILURE` restart policy in
  `backend/railway.toml`.

Railway detects a `Dockerfile` at the service root. For this repository, the
Railway service Root Directory should be `/backend`:
[Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles) and
[Railway monorepos](https://docs.railway.com/deployments/monorepo).

### CI readiness

Prepared in `.github/workflows/ci.yml`:

- Trigger on pull requests and pushes to `main`.
- Backend job: Python 3.12, install `uv`, `uv sync --locked`,
  `uv run pytest`, `uv run ruff check .`, `uv run mypy .`.
- Frontend job: Node 24, `npm ci`, `npm run lint`, `npm run build`.
- Use only example/public values needed for a build; do not add OpenAI or
  Supabase secret keys to CI.
- No deployment job or provider credentials are present.

## Current validation

Run after the Phase 2 backend changes:

- `uv run pytest`: 95 passed; one existing Starlette/httpx deprecation warning.
- `uv run ruff check .`: passed.
- `uv run mypy .`: passed.
- `npm run lint`: passed.
- `npm run build`: passed.
- Docker image build: passed.
- Production container smoke test: `/health`, disabled docs, CORS allow/deny,
  and non-root runtime passed.

## Required accounts and user-owned actions

No account action is required until Phase 2 configuration is approved and
committed.

When requested, the repository owner must perform these actions personally:

### GitHub

- Use the existing `NhanNguyen-SG/BulkMint` repository.
- Approve the Vercel GitHub integration for this repository.
- Approve the Railway GitHub integration for this repository.
- Confirm whether deployments from `main` should be automatic after the first
  successful private-beta deployment.

### Supabase

- Sign in to or create a Supabase account and organization.
- Create one new hosted project, recommended name: `bulkmint-beta`.
- Choose the region nearest the expected private-beta users and Railway
  service.
- Choose a plan and spending limits.
- Create and securely store the database password.
- Do not link the CLI or apply migrations until the separate migration
  approval gate.

### Railway

- Sign in to or create a Railway account/workspace.
- Create one project, recommended name: `BulkMint Private Beta`.
- Create one service, recommended name: `backend`.
- Connect `NhanNguyen-SG/BulkMint`.
- Set Root Directory to `/backend`.
- Do not deploy until all Railway variables have been confirmed by name and
  the owner explicitly approves deployment.

### Vercel

- Sign in to or create a Vercel account/team.
- Import `NhanNguyen-SG/BulkMint` as one project, recommended name:
  `bulkmint-beta`.
- Set Root Directory to `frontend`.
- Set the production branch to `main`.
- Do not deploy until the production variables and Railway URL have been
  confirmed and the owner explicitly approves deployment.

### OpenAI

- Use an OpenAI Platform account and a dedicated project for BulkMint private
  beta.
- Create a restricted project API key for the Railway backend.
- Configure project budget/usage alerts appropriate for a private beta.
- Enter the key directly into Railway; never paste it into chat, source code,
  Vercel, Supabase client settings, or a committed file.

OpenAI requires API keys to remain server-side and recommends loading them from
an environment variable or key-management service:
[OpenAI API authentication](https://platform.openai.com/docs/api-reference/introduction).

### Optional domain

- A custom domain is optional.
- If used, decide the canonical frontend hostname before setting Supabase Auth
  Site URL, redirect URLs, and Railway CORS.
- The API can initially use a Railway-provided HTTPS domain.
- DNS changes require a separate explicit approval.

## Production environment variables

Only variable names and value sources are documented here. Secret values must
never be printed or committed.

### Vercel frontend

Set for the Production environment:

| Variable | Secret | Value source |
| --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | No | Supabase Project URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | No | Supabase publishable key |
| `NEXT_PUBLIC_API_URL` | No | Railway backend HTTPS origin |

Do not set `SUPABASE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, or
`OPENAI_API_KEY` in Vercel. `NEXT_PUBLIC_*` values are embedded into browser
code by design.

### Railway backend

Set on the backend service:

| Variable | Secret | Value source |
| --- | --- | --- |
| `APP_ENV` | No | `production` |
| `ENABLE_API_DOCS` | No | `false`; production disables docs regardless |
| `CORS_ALLOWED_ORIGINS` | No | Exact Vercel production origin |
| `OPENAI_API_KEY` | **Yes** | Dedicated OpenAI project key |
| `OPENAI_LISTING_MODEL` | No | Pin to the approved listing model, currently `gpt-4.1-mini` |
| `SUPABASE_URL` | No | Supabase Project URL |
| `SUPABASE_PUBLISHABLE_KEY` | No | Supabase publishable key |
| `SUPABASE_SECRET_KEY` | **Yes** | Supabase hosted secret key |
| `SUPABASE_JWT_ISSUER` | No | `<SUPABASE_URL>/auth/v1` |
| `SUPABASE_JWT_AUDIENCE` | No | `authenticated` |
| `SUPABASE_JWKS_URL` | No | `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` |

Railway injects `PORT`; do not create or hard-code it. The container start
command must consume it.

Temporary legacy fallback, only if hosted secret-key verification encounters
an unexpected provider compatibility problem:

- `SUPABASE_SERVICE_ROLE_KEY` — secret legacy JWT; do not set it together with
  `SUPABASE_SECRET_KEY`.

Use `SUPABASE_SECRET_KEY` for the normal deployment because Supabase is
deprecating the legacy API keys.

### Supabase production project

BulkMint deploys no Supabase Edge Functions, so no custom application
environment variables need to be added inside Supabase.

Collect these values/settings without putting them in source control:

| Value or setting | Location/use |
| --- | --- |
| Project URL | Connect dialog or Integrations → Data API |
| Publishable key | Settings → API Keys |
| Secret key | Settings → API Keys; Railway only |
| Project reference | Project URL/dashboard; CLI linking only |
| Database password | Created with the project; migration session only |
| JWKS URL | `<project-url>/auth/v1/.well-known/jwks.json` |
| JWT issuer | `<project-url>/auth/v1` |
| Auth Site URL | Final Vercel production URL |
| Auth redirect URLs | Exact production URL; optional approved preview URLs |

Do not use the database connection string in Vercel or Railway for the current
architecture. FastAPI uses the Supabase Data and Storage APIs.

## Phase 2 repository changes

Implemented after explicit approval:

1. Added unauthenticated `GET /health` returning a minimal `200` response
   without testing external dependencies or leaking configuration.
2. Replaced hard-coded CORS with validated `CORS_ALLOWED_ORIGINS`; localhost
   remains the development default.
3. Added `APP_ENV`; production mode requires HTTPS CORS origins, rejects
   localhost, and disables FastAPI docs regardless of `ENABLE_API_DOCS`.
4. Fixed the Supabase secret-key header compatibility issue and added tests
   for opaque and legacy keys.
5. Added `backend/Dockerfile` and `backend/.dockerignore`.
6. Added `backend/railway.toml` with Docker, health-check, and restart settings.
7. Constrained the frontend Node version. No `vercel.json` was necessary
   because framework auto-detection and the dashboard Root Directory are
   sufficient.
8. Added `.github/workflows/ci.yml`.
9. Added production environment examples with placeholders only.
10. Kept local defaults at `http://localhost:3000` and
    `http://localhost:8000`.

No deployment or migration command is included in CI.

Local development must continue using `http://localhost:3000` and
`http://localhost:8000`.

## Phase 3: hosted Supabase setup and migration dry run

Account steps, performed by the owner when requested:

1. Open the [Supabase Dashboard](https://supabase.com/dashboard).
2. Select the intended organization.
3. Create project `bulkmint-beta`.
4. Choose the approved region, plan, and database password.
5. Wait for project provisioning.
6. Record the Project URL, project reference, publishable key, secret key, and
   database major version in the relevant provider secret stores.
7. Enable or confirm asymmetric JWT signing and record only the issuer/JWKS
   URLs, never a private signing key.

Proposed CLI review sequence:

```bash
cd ~/Projects/BulkMint
git status --short
git rev-parse v0.3.1
supabase db reset
./supabase/tests/rls_local.sh
./supabase/tests/card_image_storage_local.sh
./supabase/tests/listing_pricing_local.sh
supabase login
supabase link --project-ref <project-ref>
supabase migration list --linked
supabase db push --dry-run --linked
```

`supabase login` and `supabase link` contact the hosted account and therefore
require explicit approval at execution time. The dry run must be reviewed in
full. Do **not** run `supabase db push` without a second, explicit migration
approval.

Before applying:

- confirm the hosted Postgres major version;
- review all four SQL files and their local-only/proposal comments;
- verify there are no existing production tables or rows;
- verify all RLS grants and policies;
- verify the private bucket definition and storage policies;
- confirm the migration list contains only the expected four migrations;
- capture the empty-project rollback/recreate plan.

## Phase 4: Railway deployment gate

After migrations are separately approved and applied:

1. Owner creates/configures the Railway project and backend service.
2. Owner enters the Railway variables listed above directly in Railway.
3. Owner confirms by variable **name only** that all values are set.
4. Obtain explicit approval to deploy.
5. Deploy the backend.
6. Verify `/health` returns `200` over HTTPS.
7. Confirm `/docs`, `/redoc`, and `/openapi.json` are disabled unless
   explicitly approved.
8. Confirm requests from unapproved origins do not receive CORS access.
9. Confirm the exact Vercel production origin is allowed.
10. Review logs for secret leakage before continuing.

## Phase 5: Vercel deployment gate

1. Owner creates/configures the Vercel project with Root Directory `frontend`.
2. Owner enters the three production variables by name.
3. Owner confirms the Railway HTTPS URL contains no localhost reference.
4. Obtain explicit approval to deploy.
5. Deploy the frontend.
6. Set/confirm Supabase Auth Site URL and exact redirect URL.
7. Verify login, session refresh, frontend-to-backend requests, and CORS.
8. Inspect the browser bundle/network panel to confirm that only the
   publishable key is present.

## Phase 6: private-beta validation

Use a dedicated test user created manually in Supabase Auth because the current
UI provides login but no signup.

Validate:

1. logged-out page and login;
2. card upload and image validation;
3. OpenAI card analysis;
4. inventory save and private image retrieval;
5. listing-draft generation;
6. manual draft editing and version history;
7. title/description/JSON copying;
8. second-user isolation for cards, images, pricing, and listing drafts;
9. anonymous denial;
10. Railway/Vercel/Supabase logs contain no secrets or bearer tokens;
11. no `localhost` URL appears in production HTML, JavaScript, requests, or
    provider configuration.

Delete or clearly label test data after validation.

## Known private-beta risks

Critical before deployment:

- Remote migrations have never been dry-run or applied.
- Provider projects and production environment variables are not configured.

High priority before inviting users:

- `npm audit` currently reports one low and three moderate transitive
  vulnerabilities, including the PostCSS version bundled by the current Next.js
  release. There are no high or critical findings. Do not apply npm's suggested
  Next.js downgrade; reassess when a compatible patched release is available.
- No application-level rate limit or per-user AI usage quota; an authenticated
  user can generate OpenAI cost.
- No continuous uptime monitor; Railway's deployment check is not monitoring.
- No structured logging, error tracking, or explicit sensitive-header
  redaction policy.
- FastAPI's OpenAPI documentation remains available in development but is
  disabled in production mode.
- No tested production backup/restore procedure beyond provider defaults.
- No production email/SMTP decision; beta users must initially be created
  manually.

Scalability/operational:

- Image analysis base64-encodes up to 10 MiB in backend memory.
- The async analysis route calls a synchronous OpenAI client and can block an
  application worker under concurrent load.
- OpenAI retries, timeouts, and user-facing transient-error handling need a
  production review.
- Signed image URLs expire after five minutes, which is appropriate for
  privacy but may require UI refresh during long review sessions.
- Vercel Preview deployments will fail backend CORS unless preview origins are
  explicitly approved and safely supported.

## Approval gates

Required approvals, in order:

1. **Completed:** Phase 2 repository deployment configuration, including the
   Supabase secret-key compatibility fix.
2. Supabase account/project creation.
3. Supabase CLI login/project linking.
4. Hosted migration dry run.
5. Hosted migration application.
6. Railway account/project configuration.
7. Railway deployment.
8. Vercel account/project configuration.
9. Vercel deployment.
10. Supabase production test-user creation and final beta validation.
11. Optional custom-domain and DNS changes.
