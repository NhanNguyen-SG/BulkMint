# Listing Draft Contract

Status: **proposal only — not applied locally or remotely**

The proposed SQL is
`supabase/migrations/20260701000300_listing_pricing_contract.sql`. It changes
database contracts only. It does not add APIs, change the OpenAI prompt, call
eBay, or alter runtime behavior.

## Domain boundary

A card and a listing draft are different resources:

```text
cards (inventory identity)
  ├── analysis_jobs (how the card was analyzed)
  ├── pricing_observations (price evidence for the card)
  └── listing_drafts (one card may have many drafts)
        └── selected_pricing_observation_id
```

`cards` remains the inventory authority. A `listing_draft` is an editable,
marketplace-formatted proposal derived from one card. The composite foreign key
`(card_id, owner_id)` prevents a draft from referencing another user's card.

Multiple drafts may exist for one card, including archived revisions or drafts
for different marketplace targets. V0.3 initially uses `ebay` as the formatting
target but does not connect to eBay.

## From `listings` to `listing_drafts`

The Phase 2 proposal used a `listings` table for both drafts and publication
state. V0.3 separates those concerns by renaming it to `listing_drafts` and
removing:

- `external_listing_id`;
- `published_at`;
- `ended_at`;
- publication statuses such as `published`, `sold`, and `error`.

The migration refuses to run if `listings` contains rows. That is deliberate:
there is no approved rule for converting an existing published or partially
published record into a draft. A separate inventory and backfill plan is
required before this proposal can be applied to any non-empty environment.

## `listing_drafts` fields

| Field | Purpose |
|---|---|
| `id` | Server-generated draft UUID |
| `owner_id` | Verified Supabase Auth user ID |
| `card_id` | Required owner-scoped card relationship |
| `analysis_job_id` | Optional analysis that originated the draft |
| `marketplace_target` | Formatting target, initially `ebay` |
| `status` | `draft`, `ready`, or `archived` |
| `title` | Current user-reviewable title |
| `description` | Current user-reviewable description |
| `price_amount` | Current asking price |
| `currency` | Three-letter uppercase currency code |
| `quantity` | Intended listing quantity |
| `selected_pricing_observation_id` | Provenance record matching price/currency |
| `content_origin` | `manual`, `ai_generated`, `ai_assisted`, or `imported` |
| `generated_title` | Immutable original AI title when applicable |
| `generated_description` | Immutable original AI description when applicable |
| `generation_provider` | AI provider when applicable |
| `generation_model` | AI model when applicable |
| `prompt_version` | Versioned generation contract when applicable |
| `generated_at` | AI generation timestamp |
| `ready_at` | Timestamp of explicit review/readiness |
| `archived_at` | Timestamp of archival |
| `created_at`, `updated_at` | Record lifecycle timestamps |

The current `title` and `description` may differ from their generated originals.
When a user edits generated content, `content_origin` becomes `ai_assisted`;
the generated fields and generation metadata remain unchanged. Column-level
update grants prevent authenticated clients from changing those original
generation fields, ownership, card linkage, or analysis linkage after insert.
A manual draft has no generation fields.

## Lifecycle

```text
draft ── explicit review ──> ready
  │                           │
  └──────── archive <─────────┘
```

- `draft`: incomplete or not yet approved by the user.
- `ready`: title, description, quantity, price, and price provenance are valid
  and have been explicitly reviewed.
- `archived`: retained but no longer active.

There is no `published` state. Marking a draft ready means only that its content
is ready for a future integration.

## AI-generated text versus publication

AI generation and marketplace publication are independent facts:

| Concern | V0.3 representation |
|---|---|
| AI created the initial text | `content_origin`, original generated fields, provider/model/prompt metadata |
| User edited AI text | Current fields differ; origin is `ai_assisted` |
| User created text manually | Origin is `manual`; generation fields are null |
| Draft targets eBay formatting | `marketplace_target = 'ebay'` |
| Draft was published to eBay | Not representable in V0.3 |

A future marketplace integration should introduce a separate
`marketplace_listings` resource containing the marketplace account,
`external_listing_id`, publication state, and marketplace timestamps. It would
reference a reviewed draft revision. Those fields do not belong in
`listing_drafts`, and no such table or integration is proposed in V0.3 Step 1.

## Price relationship

A draft asking price is allowed only when
`selected_pricing_observation_id` is present. The selected observation must:

- belong to the same owner;
- belong to the same card;
- have exactly the draft's `price_amount` and `currency`.

The migration enforces ownership and card identity with a composite foreign key
and enforces amount/currency equality with a trigger. A manual price change must
therefore create a new append-only `manual_override` observation and select it;
it must not rewrite prior evidence.

## Ownership and RLS

The renamed table retains the Phase 2 owner policies:

- anonymous users have no access;
- authenticated users may select, insert, and delete only their rows;
- authenticated updates are limited to reviewable content, status, asking
  price/provenance, quantity, origin transition, and lifecycle timestamps;
- `owner_id` is derived from the verified JWT;
- card, analysis-job, and pricing relationships use composite owner foreign
  keys;
- `service_role` retains administrative access but must never reach browser
  code.

FastAPI remains the intended application boundary. V0.3 Step 1 does not expose
the table through a new endpoint.

An owner JWT can still create self-owned rows directly through the Supabase
Data API. RLS protects ownership, but it does not prove that AI metadata was
produced by BulkMint. Before generated drafts are implemented, choose a trusted
insert path—such as a narrowly scoped database function or a server-only
credential—and test that the browser cannot forge generation provenance.

## Audit events

A separate `listing_events` table is not needed. The existing append-only
`audit_events` table can represent:

- `listing_draft.created`;
- `listing_draft.generated`;
- `listing_draft.updated`;
- `listing_draft.ready`;
- `listing_draft.archived`;
- `listing_draft.price_selected`.

Use `entity_type = 'listing_draft'`, the draft UUID as `entity_id`, and
old/new values plus generation or pricing IDs in the JSON fields. Authenticated
clients still cannot insert audit rows directly. A later API implementation
must choose a trusted, transactional write mechanism before recording these
events; this proposal does not expose broader audit privileges.

## Deletion behavior

- Deleting a card cascades to its listing drafts and price observations.
- Deleting an analysis job sets a draft's `analysis_job_id` to null.
- Selected price observations are restricted from deletion.
- Pricing sources and observations are append-only to authenticated users.
- Archival should be the normal user-facing draft removal action.

User-account deletion still cascades through owner records. Retention and legal
requirements must be reviewed before remote rollout.

## Explicit non-capabilities

This contract cannot:

- authenticate with eBay;
- publish, revise, end, or inspect an eBay listing;
- prove that any marketplace listing exists;
- store an eBay token or seller account;
- transition a draft to a published state.
