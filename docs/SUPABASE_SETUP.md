# Supabase Setup

Status: **manual plan only — do not apply without explicit approval**

The proposed migration creates a fresh target schema. It passed local Supabase
validation on 2026-07-01 and has not been applied to any remote project.

## Why the current project needs a reconciliation migration

The current remote project already has a `cards` table created outside version
controlled migrations. The proposal also creates `public.cards`, so applying it
directly to that project will fail rather than silently modify the existing
table.

The current data also lacks a version-controlled ownership mapping, stores
suggested prices as text, and stores listing text on the card row. These require
an explicit data migration.

## Inspect and back up first

Before any schema change:

1. Confirm a restorable Supabase backup exists.
2. Export the existing schema and `cards` data.
3. Record the current row count.
4. Identify the authentication user who should own each current row.
5. Inspect current columns and RLS policies:

```sql
select
  column_name,
  data_type,
  is_nullable,
  column_default
from information_schema.columns
where table_schema = 'public'
  and table_name = 'cards'
order by ordinal_position;

select count(*) as card_count
from public.cards;

select
  schemaname,
  tablename,
  policyname,
  roles,
  cmd,
  qual,
  with_check
from pg_policies
where schemaname = 'public'
order by tablename, policyname;
```

Do not paste database passwords, access tokens, service-role keys, or exported
customer data into this repository.

## Local Supabase validation

Supabase CLI 2.109.0 is installed on this workstation. The local project is
initialized and can be started with:

```sh
supabase start
supabase db reset
./supabase/tests/rls_local.sh
```

`supabase db reset` is destructive to the local Supabase database. It should
never be pointed at the remote project.

After validation:

```sh
supabase status
supabase stop
```

## Existing-project reconciliation

Create and review a separate migration that:

1. Captures the existing remote schema with `supabase db pull`.
2. Adds authentication and obtains the intended owner's `auth.users.id`.
3. Adds nullable ownership and normalized columns to the existing table.
4. Backfills every row with a verified owner.
5. Parses `suggested_price` into numeric amount and currency, recording rows
   that cannot be parsed.
6. Moves existing listing title and description into `listings`.
7. Verifies source and destination row counts.
8. Makes required ownership columns non-null only after verification.
9. Enables grants and RLS after the authenticated frontend is ready.

Do not use a fabricated owner UUID, discard unparseable prices, or drop legacy
columns in the same rollout.

## Remote dry run and apply

Only after local validation, owner backfill planning, frontend authentication,
and explicit approval:

```sh
supabase login
supabase link --project-ref <project-ref>
supabase migration list
supabase db push --dry-run
```

Review the exact migration list and SQL target. Applying requires a separate,
explicitly approved command:

```sh
supabase db push
```

Only one operator should push migrations at a time.

## Post-apply verification

Use at least two test users and verify:

- Each user sees only their own rows.
- A user cannot insert a row owned by another user.
- A user cannot change `owner_id` through an update.
- Cross-owner child references fail.
- Anonymous reads and writes fail.
- Authenticated users cannot mutate `audit_events`.
- Trusted server code can create audit events.
- Existing row counts and monetary values match the pre-migration export.

## Rollback strategy

The proposal is wrapped in one transaction, so a statement failure should roll
back the initial application. After a successful remote application, do not
edit or delete the deployed migration.

Rollback must be a new forward migration or a database restore. Dropping tables
is destructive and is not an acceptable production rollback while data exists.

## References

- [Supabase database migrations](https://supabase.com/docs/guides/deployment/database-migrations)
- [Supabase local development](https://supabase.com/docs/guides/local-development/overview)
- [Supabase row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security)
