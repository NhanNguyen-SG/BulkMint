# RLS Frontend Impact

Status: **analysis only — frontend behavior is unchanged**

Applying the proposed migration and RLS policies before an authenticated
frontend migration would break the current inventory workflow.

## Current frontend behavior

The browser creates a Supabase client with:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

It does not sign in a user or restore an authenticated session. It then:

1. Selects every row from `cards`.
2. Orders rows by `created_at`.
3. Maps legacy card and listing fields into one client type.
4. Inserts AI output directly into `cards`.

## Breakage after RLS is applied

| Current behavior | Impact |
|---|---|
| No authenticated session | `auth.uid()` is null, so ownership policies cannot match |
| Anonymous `cards` select | Denied because `anon` has no table privileges or policy |
| Anonymous `cards` insert | Denied; `owner_id` cannot resolve to an authenticated user |
| Optimistic inventory update before insert | A failed insert still leaves a phantom card in browser state |
| Read `suggested_price` | Column is replaced by `price_amount` and `currency` |
| Read/write `ebay_title` | Data moves to `listings.title` |
| Read/write `ebay_description` | Data moves to `listings.description` |
| `AnalysisResult` as database shape | No longer matches the normalized database contract |
| Array index as card key | New UUID `cards.id` is ignored |
| No status field in UI state | New card lifecycle status is ignored |
| Direct browser persistence | Analysis, card, and listing writes remain non-atomic |

The initial inventory query currently logs an error and leaves the inventory
empty when Supabase rejects it. The analysis flow adds the AI result to local
state before attempting the database insert, so a rejected RLS write appears
temporarily successful and then displays a save-failure alert.

## Required work before remote RLS activation

These are future implementation tasks, not changes made in Phase 2.5:

1. Choose and implement Supabase Auth sign-in and session restoration.
2. Block inventory queries until authentication state is resolved.
3. Decide whether the browser or FastAPI is the authoritative persistence
   boundary. The architecture review recommends FastAPI.
4. Replace legacy `suggested_price` with numeric amount and currency handling.
5. Read and write listing text through `listings`.
6. Include UUIDs, ownership-safe relationships, timestamps, and status fields
   in typed API contracts.
7. Replace `select("*")` with explicit, paginated fields.
8. Remove optimistic inventory entries or reconcile them after a confirmed
   database transaction.
9. Generate Supabase TypeScript types after the final schema is validated.
10. Test authenticated and cross-user behavior against the local stack.

## Environment variable note

`NEXT_PUBLIC_SUPABASE_ANON_KEY` can hold the legacy local anon key currently
used by the CLI. Supabase now recommends publishable keys for public clients.
Renaming that variable should be handled deliberately with the authentication
work rather than as an undocumented configuration change.

A secret or `service_role` key must never be added to a `NEXT_PUBLIC_`
variable, frontend environment file, browser bundle, or Git history.

## Safe rollout order

1. Validate the migration and RLS locally.
2. Implement and test frontend authentication locally.
3. Implement the normalized read/write contract.
4. Reconcile existing remote data and assign verified owners.
5. Deploy compatible application code.
6. Enable grants and RLS in a coordinated migration.
7. Verify access using two production-safe test users.
8. Monitor denied requests and data consistency before removing legacy fields.

Do not apply the current migration to the remote project until steps 1–4 are
complete and the rollout has explicit approval.
