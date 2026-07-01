# Supabase Local Testing

Status: **validated locally on 2026-07-01**

This plan validates the proposed database migration and RLS policies entirely
on the Mac mini. It must not use `supabase login`, `supabase link`,
`supabase db pull`, or `supabase db push`.

## Current prerequisite status

- Docker Desktop: installed
- Supabase CLI: 2.109.0
- Proposed migration:
  `supabase/migrations/20260701000100_initial_database_contract.sql`

The CLI was installed with the recommended macOS Homebrew command:

```sh
brew install supabase/tap/supabase
```

Installing the CLI globally with `npm install -g supabase` is not supported by
Supabase.

## Initialize the local project

After the CLI installation is approved:

```sh
cd ~/Projects/BulkMint
supabase --version
supabase init
supabase start
```

`supabase start` downloads and starts local Docker images on the first run. It
does not require a Supabase login or remote project link.

Apply all repository migrations to the local database:

```sh
supabase db reset
supabase status
```

`supabase db reset` destroys and recreates the local Supabase database. Never
run it against a database containing data that has not been backed up.

Expected local endpoints include:

- API: `http://127.0.0.1:54321`
- PostgreSQL: `127.0.0.1:54322`
- Studio: `http://127.0.0.1:54323`
- Mailpit: `http://127.0.0.1:54324`

Use the actual endpoints printed by `supabase status` if they differ.

The CLI currently warns that local development services bind to all host
interfaces. Keep the stack running only while testing, retain the macOS
firewall, and stop it immediately afterward.

## Recorded validation

The following checks passed locally with no remote project link:

- The migration applied successfully during initial startup.
- A second `supabase db reset` applied the migration successfully.
- All five domain tables exist and have RLS enabled.
- All 17 expected policies exist.
- The `anon` role has no grants on domain tables.
- Authenticated users have no audit-event write grants.
- `supabase db lint --local --schema public` found no schema errors.
- Anonymous, owner, cross-user, service-role, and audit-event RLS tests passed.

Run the committed end-to-end test with:

```sh
./supabase/tests/rls_local.sh
```

The script refuses non-local API URLs, obtains local keys at runtime, creates
temporary local users, and does not print or persist credentials.

## Schema validation

In local Studio, confirm:

1. `cards`, `card_images`, `analysis_jobs`, `listings`, and `audit_events`
   exist in `public`.
2. Each table has a UUID primary key and `owner_id`.
3. All five tables have RLS enabled.
4. The expected indexes, constraints, policies, and update triggers exist.
5. No remote project appears anywhere in the local CLI configuration.

Repeatability check:

```sh
supabase db reset
supabase status
```

Both resets must complete from the committed migration without manual SQL.

## Local test identities

Create two local-only users through Studio at
`http://127.0.0.1:54323`:

- `owner-a@example.test`
- `owner-b@example.test`

Use local-only test passwords. Do not insert directly into `auth.users`, reuse
real email addresses, or commit credentials.

Record each generated user UUID temporarily as `USER_A_ID` and `USER_B_ID`.
Obtain access tokens by signing each user in through the local Auth API.

Set local shell variables from `supabase status`. Do not save the key values in
tracked files:

```sh
export SUPABASE_URL='http://127.0.0.1:54321'
export SUPABASE_PUBLISHABLE_KEY='<local publishable or anon key>'
export SUPABASE_SECRET_KEY='<local secret or service_role key>'
```

Sign in as each test user:

```sh
TOKEN_A="$(
  curl --fail-with-body --silent \
    "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
    -H "Content-Type: application/json" \
    -d '{"email":"owner-a@example.test","password":"<local-password-a>"}' |
    jq -r '.access_token'
)"

TOKEN_B="$(
  curl --fail-with-body --silent \
    "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
    -H "Content-Type: application/json" \
    -d '{"email":"owner-b@example.test","password":"<local-password-b>"}' |
    jq -r '.access_token'
)"
```

Retrieve and verify the user UUIDs:

```sh
USER_A_ID="$(
  curl --fail-with-body --silent "$SUPABASE_URL/auth/v1/user" \
    -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
    -H "Authorization: Bearer $TOKEN_A" |
    jq -r '.id'
)"

USER_B_ID="$(
  curl --fail-with-body --silent "$SUPABASE_URL/auth/v1/user" \
    -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
    -H "Authorization: Bearer $TOKEN_B" |
    jq -r '.id'
)"
```

Stop if either token or UUID is empty or `null`.

## RLS test matrix

### 1. Anonymous access is denied

Call the Data API with the publishable key but without a user JWT:

```sh
curl --include \
  "$SUPABASE_URL/rest/v1/cards?select=id" \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY"
```

Expected: access is denied. A successful response containing card rows is a
test failure.

### 2. Owner CRUD is allowed

Create a card as user A. `owner_id` should default to user A:

```sh
CARD_A_JSON="$(
  curl --fail-with-body --silent \
    "$SUPABASE_URL/rest/v1/cards" \
    -X POST \
    -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
    -H "Authorization: Bearer $TOKEN_A" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d '{"card_name":"Local RLS test card","status":"draft"}'
)"

CARD_A_ID="$(printf '%s' "$CARD_A_JSON" | jq -r '.[0].id')"
CARD_A_OWNER="$(printf '%s' "$CARD_A_JSON" | jq -r '.[0].owner_id')"
test "$CARD_A_OWNER" = "$USER_A_ID"
```

Read and update it as user A:

```sh
curl --fail-with-body --silent \
  "$SUPABASE_URL/rest/v1/cards?id=eq.$CARD_A_ID&select=id,owner_id,status" \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $TOKEN_A" |
  jq

curl --fail-with-body --silent \
  "$SUPABASE_URL/rest/v1/cards?id=eq.$CARD_A_ID" \
  -X PATCH \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"status":"active"}' |
  jq
```

Repeat equivalent owner tests for `card_images`, `analysis_jobs`, and
`listings`, including their parent foreign keys. Create and retain an
equivalent card for user B so the service-role test has records from both
owners.

### 3. Cross-user access is blocked

User B must not see or modify user A's card:

```sh
curl --fail-with-body --silent \
  "$SUPABASE_URL/rest/v1/cards?id=eq.$CARD_A_ID&select=*" \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $TOKEN_B" |
  jq

curl --fail-with-body --silent \
  "$SUPABASE_URL/rest/v1/cards?id=eq.$CARD_A_ID" \
  -X PATCH \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"status":"archived"}' |
  jq
```

Expected: both responses contain zero rows, and user A still sees the original
card with the expected status.

User B must also be unable to claim user A's ownership:

```sh
curl --include \
  "$SUPABASE_URL/rest/v1/cards" \
  -X POST \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d "{\"owner_id\":\"$USER_A_ID\",\"card_name\":\"Forbidden owner test\"}"
```

Expected: the insert fails an RLS policy.

User A must not be able to transfer a row to user B:

```sh
curl --include \
  "$SUPABASE_URL/rest/v1/cards?id=eq.$CARD_A_ID" \
  -X PATCH \
  -H "apikey: $SUPABASE_PUBLISHABLE_KEY" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d "{\"owner_id\":\"$USER_B_ID\"}"
```

Expected: the update fails the policy's `with check` expression, and ownership
remains unchanged.

Also verify that a user B child record cannot reference a user A parent. The
composite ownership foreign keys must reject it.

### 4. Service-role access bypasses RLS

Use only the local secret or legacy `service_role` key. Never use a remote key
for this test or place this key in a browser:

```sh
curl --fail-with-body --silent \
  "$SUPABASE_URL/rest/v1/cards?select=id,owner_id,status" \
  -H "apikey: $SUPABASE_SECRET_KEY" |
  jq
```

Expected: the trusted service sees rows belonging to both test users.

Use the trusted key to insert one `audit_events` row for user A, then verify:

- User A can select the event.
- User B cannot select it.
- Neither authenticated user can insert, update, or delete audit events.

### 5. Owner deletion works

After all cross-user assertions, delete user A's card with user A's JWT and
confirm its dependent rows follow the documented foreign-key behavior.

## Pass criteria

The local validation passes only when:

- Two consecutive local resets apply cleanly.
- Anonymous access is denied.
- Both users can CRUD only their own mutable records.
- Cross-user reads return no rows.
- Cross-user writes and parent relationships fail.
- `owner_id` cannot be reassigned.
- Audit events are user-readable but server-write-only.
- The service role can inspect all local test records.
- No remote URL, project reference, or credential was used.

## Cleanup

Remove shell credentials and stop the local stack:

```sh
unset TOKEN_A TOKEN_B USER_A_ID USER_B_ID
unset SUPABASE_URL SUPABASE_PUBLISHABLE_KEY SUPABASE_SECRET_KEY
supabase stop
```

To delete local data volumes later, review the destructive implications before
using `supabase stop --no-backup`.

## References

- [Supabase CLI installation and local stack](https://supabase.com/docs/guides/local-development/cli/getting-started)
- [Supabase local migrations](https://supabase.com/docs/guides/local-development/overview)
- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
