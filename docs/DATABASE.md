# Database Contract

Status: **proposal only — not applied to Supabase**

The proposed database contract is defined in
`supabase/migrations/20260701000100_initial_database_contract.sql`. It targets a
fresh Supabase schema. The current remote `cards` table must be inspected and
migrated separately before this proposal can be applied to an existing project.

## Current frontend contract

The frontend currently reads every row from `cards`, ordered by `created_at`,
and inserts records directly with the public Supabase client.

| Current field | Proposed destination | Migration note |
|---|---|---|
| `card_name` | `cards.card_name` | Retained |
| `set_name` | `cards.set_name` | Retained |
| `card_number` | `cards.card_number` | Retained |
| `rarity` | `cards.rarity` | Retained |
| `condition_guess` | `cards.condition_guess` | Retained until a reviewed condition model exists |
| `suggested_price` | `cards.price_amount` and `cards.currency` | Existing text values require parsing |
| `ebay_title` | `listings.title` | Moved out of inventory records |
| `ebay_description` | `listings.description` | Moved out of inventory records |
| `created_at` | `cards.created_at` | Retained |

The current frontend does not authenticate users or supply `owner_id`.
Therefore, applying this migration before frontend authentication and data
backfill would stop current reads and inserts. That is intentional protection,
not a backwards-compatible rollout.

## Tables

### `cards`

The canonical inventory record.

- UUID primary key and authenticated `owner_id`
- Card identity and condition fields used by the current frontend
- Numeric `price_amount` plus ISO-style three-letter `currency`
- Status: `draft`, `active`, `listed`, `sold`, or `archived`
- Creation and automatic update timestamps

### `card_images`

Metadata for an object stored in Supabase Storage or another object store.
Database rows do not contain image bytes.

- Optional card association, allowing intake before card identification
- Storage bucket and path
- Image kind, MIME type, byte size, and SHA-256 digest
- Status: `active` or `removed`

This migration does not create a Storage bucket or Storage RLS policies.

### `analysis_jobs`

Durable state for an analysis attempt.

- Optional card and input-image associations
- Provider, model, and prompt-version metadata
- JSON result or structured failure details
- Attempt count and lifecycle timestamps
- Status: `pending`, `running`, `succeeded`, `failed`, or `cancelled`
- Optional owner-scoped idempotency key

The migration does not change the existing OpenAI request path or prompt.

### `listings`

Marketplace-neutral listing drafts and publication state.

- Required card association and optional originating analysis job
- Marketplace and external listing identifier
- Title, description, numeric price, currency, and quantity
- Status: `draft`, `ready`, `published`, `ended`, `sold`, or `error`

No marketplace API integration is implemented by this migration.

### `audit_events`

Append-only audit records intended to be written by trusted server code.

- Owner and optional actor
- Action, entity type, and entity UUID
- Old data, new data, and metadata as JSON
- Creation timestamp only

Authenticated users may read their own events but cannot insert, update, or
delete them through the public API.

## Ownership integrity

Every domain table contains `owner_id`, linked to `auth.users(id)`. Child tables
use composite foreign keys such as `(card_id, owner_id)` to prevent a user-owned
child row from referencing another user's parent row.

Deleting an authentication user cascades through that user's owned records.
This behavior must be confirmed against retention requirements before applying
the migration.

## Row-level security

RLS is enabled on all five tables.

| Role | Cards, images, jobs, listings | Audit events |
|---|---|---|
| `anon` | No privileges or policies | No privileges or policies |
| `authenticated` | Select, insert, update, and delete own rows only | Select own rows only |
| `service_role` | Full access; bypasses RLS | Full access; bypasses RLS |

Ownership policies use `(select auth.uid()) = owner_id`. Unauthenticated
requests have no table privileges and cannot satisfy an ownership policy.

The service-role key must remain server-side. It must never use a
`NEXT_PUBLIC_` variable or be committed to Git.

## Indexes

Indexes support:

- Owner-scoped inventory ordering and status filtering
- Card identity lookup by set and card number
- Card/image relationships and image hash lookup
- Job and listing queues ordered by status and creation time
- Owner-scoped listing and audit history
- Idempotent analysis submission
- Unique external listing identifiers

## Deliberate exclusions

- Existing-row migration and owner backfill
- Supabase Auth UI or frontend session handling
- Storage buckets and Storage policies
- Generated Supabase TypeScript types
- Backend persistence changes
- Realtime publication configuration
- OpenAI and marketplace integrations
