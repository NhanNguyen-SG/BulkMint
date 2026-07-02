# Pricing Provenance Contract

Status: **proposal only — not applied locally or remotely**

The proposed SQL is
`supabase/migrations/20260701000300_listing_pricing_contract.sql`. V0.3 uses
append-only pricing observations because each price is a point-in-time claim,
not mutable card state.

## Why observations

The current `cards.price_amount` is useful inventory data but cannot answer:

- who or what suggested the price;
- whether it was an asking price, sold price, estimate, or manual override;
- where the evidence came from;
- when it was observed;
- which condition it described;
- whether an AI model generated it.

`pricing_observations` preserves those facts. Updating a price creates a new
observation. Historical evidence is not overwritten.

The term `snapshot` is reserved for a future immutable capture of a complete
marketplace response. V0.3 does not fetch or store marketplace payloads, so
`pricing_observations` is the more accurate name.

## Table responsibilities

### `pricing_sources`

An immutable, owner-scoped source identity.

| Field | Purpose |
|---|---|
| `id`, `owner_id` | Server-generated identity and owner |
| `source_type` | `ai`, `manual`, `marketplace`, `derived`, or `other` |
| `source_name` | Human-readable source name |
| `source_url` | Optional canonical HTTP(S) source URL |
| `marketplace` | Optional normalized marketplace identifier |
| `created_at` | Source registration timestamp |

Examples:

| Source type | Source name | Source URL |
|---|---|---|
| `ai` | `BulkMint AI estimate` | null |
| `manual` | `Owner-entered price` | null |
| `marketplace` | `eBay sold listings` | `https://www.ebay.com/` |
| `derived` | `BulkMint comparable median` | null |

The marketplace example defines a future source type only. V0.3 Step 1 does not
query eBay or claim that sold-listing evidence exists.

### `pricing_observations`

An append-only point-in-time price claim.

| Field | Purpose |
|---|---|
| `id`, `owner_id`, `card_id` | Observation identity and owner-scoped card |
| `pricing_source_id` | Required owner-scoped source |
| `analysis_job_id` | Optional analysis that generated the estimate |
| `price_kind` | `asking`, `sold`, `estimate`, or `manual_override` |
| `observed_price` | Non-negative numeric amount |
| `currency` | Three-letter uppercase currency code |
| `condition` | Optional condition associated with the observation |
| `observed_at` | When the price was observed, generated, or entered |
| `confidence` | Optional normalized value from 0 through 1 |
| `evidence_url` | Optional exact HTTP(S) evidence page |
| `generation_provider` | AI provider for estimates |
| `generation_model` | AI model for estimates |
| `prompt_version` | Versioned prompt/contract for estimates |
| `methodology` | Deterministic method for a derived estimate |
| `method_version` | Version of the derivation method |
| `recorded_by` | Authenticated actor when applicable |
| `notes` | Optional human-readable context |
| `metadata` | Non-secret structured context |
| `created_at` | When BulkMint recorded the observation |

`source_url` identifies the source generally; `evidence_url` identifies the
specific page supporting one observation. Neither field may contain
credentials, access tokens, signed URLs, or private query parameters.

Source type controls the accepted provenance:

- AI sources require estimate kind plus provider, model, and prompt version.
- Manual sources require a manual-override kind and authenticated actor.
- Marketplace sources require asking/sold kind and an exact evidence URL.
- Derived sources require estimate kind plus methodology and method version.

This prevents manual, marketplace, and derived evidence from being mislabeled
as model output.

### `pricing_observation_inputs`

An append-only relationship from a derived observation to its input
observations.

It stores:

- owner and card;
- derived observation ID;
- input observation ID;
- optional normalized weight;
- creation timestamp.

Both observations must belong to the same owner and card. The relationship
cannot point an observation to itself. The target must use a derived source and
cannot predate its input. This provides relational provenance for future
medians or weighted recommendations without storing unverifiable input IDs
only in JSON.

## Required provenance

The requested provenance maps as follows:

| Requirement | Contract field |
|---|---|
| Source name | `pricing_sources.source_name` |
| Source URL | `pricing_sources.source_url` |
| Exact evidence URL | `pricing_observations.evidence_url` |
| Observed price | `pricing_observations.observed_price` |
| Currency | `pricing_observations.currency` |
| Condition | `pricing_observations.condition` |
| Timestamp | `pricing_observations.observed_at` |
| Confidence | `pricing_observations.confidence` |

## Confidence semantics

`confidence` is nullable and constrained to `0..1`. It must be interpreted as a
source-specific confidence signal, not a calibrated probability, unless the
source documents calibration.

- Manual prices normally use null.
- Marketplace observations normally use null because the observed amount is a
  fact about that source, not a prediction.
- AI estimates may use a value only if the model or application has a defined,
  testable interpretation.
- Derived estimates may use a value only when the derivation method defines
  it.

The UI should display qualitative wording only after these semantics are
defined. It must not manufacture a confidence percentage.

## Manual overrides

A user-entered price never mutates prior evidence:

1. Reuse or create an owner-scoped manual pricing source.
2. Insert a `manual_override` observation with the new amount, currency,
   condition, actor, and timestamp.
3. Select that observation on the listing draft.
4. Preserve earlier AI or marketplace observations.
5. Record `listing_draft.price_selected` through the trusted audit path when
   that path is implemented.

## AI estimates

The current suggested price must be described as an AI estimate, not market
data. When persistence is implemented, one estimate should record:

- source type `ai`;
- price kind `estimate`;
- provider, model, and prompt version;
- generation timestamp in `observed_at`;
- the related card and optional analysis job;
- condition used by the estimate;
- confidence only if its meaning is defined.

Changing the OpenAI prompt is outside this contract step.

## Future marketplace observations

A future read-only research integration may create asking or sold observations
only when it can preserve:

- marketplace source;
- exact evidence URL or durable external reference;
- observed timestamp;
- item condition;
- amount and currency;
- raw identifiers needed to deduplicate evidence.

No such integration exists in V0.3 Step 1. The presence of a marketplace source
row is not evidence that BulkMint queried that marketplace.

## Immutability, RLS, and deletion

Authenticated users receive only `select` and `insert` privileges for pricing
sources, observations, and derived-input relationships. There are no
authenticated update or delete policies.

RLS requires every row to match `auth.uid()`. Composite foreign keys prevent
cross-owner card, source, analysis-job, and input relationships. Service-role
administration remains possible but must stay server-side.

These controls make provenance append-only and owner-scoped; they do not prove
that a user-supplied URL or claimed source is genuine. A future marketplace
import must use a trusted ingestion path and distinguish verified imports from
owner-entered evidence.

Deletion rules:

- deleting a card cascades its observations;
- deleting a user cascades all owned pricing records;
- deleting a source is restricted while observations reference it;
- an observation selected by a draft cannot be deleted;
- normal corrections append a replacement observation rather than editing.

## Risks before implementation

- The existing `cards.price_amount` has no historical provenance and needs a
  deliberate backfill classification, likely `manual` or `unknown`, before
  remote rollout.
- Source and evidence URLs can leak credentials if accepted without
  normalization and redaction.
- Owner JWTs can create self-owned source and observation rows; trusted AI and
  marketplace ingestion needs a narrower server-side write path.
- AI confidence can mislead users unless its semantics are defined.
- Marketplace condition labels require normalization before comparison.
- Currency conversion needs dated exchange-rate provenance; V0.3 should not
  silently compare different currencies.
- Derived prices need deterministic, versioned methodology and explicit input
  observations.
- Derived-input graphs need cycle detection before multi-stage derivations are
  supported.
- Append-only evidence requires a correction/supersession convention before
  user-facing editing is implemented.
