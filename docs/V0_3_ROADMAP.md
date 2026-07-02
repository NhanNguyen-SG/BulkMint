# BulkMint V0.3 Roadmap

Status: **planning only — no V0.3 features are implemented**

## Goal

V0.3 should create a reliable, owner-scoped listing-draft boundary before any
marketplace integration. It should:

- prepare eBay-oriented draft generation without publishing;
- preserve the provenance of every suggested or manually entered price;
- persist listing drafts separately from inventory cards;
- make generated content reviewable and editable;
- leave live eBay authentication and API calls out of scope.

## V0.2 baseline

The `v0.2.0` checkpoint provides:

- authenticated, owner-scoped card inventory through FastAPI;
- private image persistence and signed image retrieval;
- card editing, archive, and permanent deletion;
- server-side inventory search and filters;
- local Supabase schema and RLS policy validation.

The current analysis response still combines card identification, a suggested
price, and eBay-oriented title/description text. Inventory persistence stores
the normalized card and price, but it does not persist the generated listing
text. The suggested price is an AI estimate with no durable source, method, or
observation timestamp.

The proposed local schema already contains `analysis_jobs` and `listings`, but
their contract must be reviewed for V0.3 before any remote migration is
approved.

## Non-goals

V0.3 must not include:

- eBay OAuth, seller-account connection, or token storage;
- eBay create, revise, publish, end, or fulfillment API calls;
- automatic listing publication;
- scraping eBay or another marketplace;
- background bulk listing generation;
- remote Supabase migration or RLS rollout without separate approval;
- treating an AI estimate as verified market data.

## Core design decisions

### Listing drafts are separate resources

A card is inventory; a listing draft is marketplace-specific presentation and
commercial intent. V0.3 should keep them separate.

The canonical listing draft should include:

- `id`, `owner_id`, and `card_id`;
- optional originating `analysis_job_id`;
- marketplace, initially `ebay`;
- title and description;
- price amount, currency, and quantity;
- draft lifecycle status;
- generation provider, model, and prompt version when AI-generated;
- creation and update timestamps.

Only `draft` and `ready` should be reachable through V0.3 application flows.
Existing publication-oriented statuses remain reserved for a later eBay
integration.

### Pricing requires provenance

Every proposed listing price should be traceable to its basis. The contract
must distinguish:

- AI estimate;
- manual user entry or override;
- imported marketplace observation in a future release;
- derived recommendation based on one or more observations.

At minimum, provenance should capture:

- source type and source name;
- amount and currency;
- observed or generated timestamp;
- provider, model, and prompt version when AI-generated;
- optional condition and explanatory note;
- actor for manual overrides;
- linkage to the card, analysis job, and listing draft where applicable.

The UI must label AI-generated prices as estimates. It must not imply that
sold-listing comparisons or live market data were used unless evidence records
actually exist.

### FastAPI remains the authority

The browser should continue using Supabase directly only for Auth. FastAPI
must:

- derive `owner_id` from the verified JWT;
- create and retrieve only owner-scoped listing drafts;
- reject immutable ownership and relationship fields from client input;
- validate title, description, price, currency, quantity, and status;
- record provenance server-side;
- keep marketplace credentials and future integrations outside browser code.

## Recommended implementation order

### 1. Finalize the listing and pricing contract

Review the existing `listings` and `analysis_jobs` proposal and decide whether
pricing provenance belongs in a dedicated append-only table or a versioned
structured record.

Deliverables:

- `docs/LISTING_DRAFTS.md`;
- `docs/PRICING_PROVENANCE.md`;
- a local-only migration proposal;
- owner-scoped RLS policies and indexes;
- lifecycle and deletion behavior;
- local SQL/RLS tests.

Acceptance criteria:

- Inventory, analysis, listing drafts, and price evidence have unambiguous
  ownership and relationships.
- Manual overrides do not erase their prior provenance.
- The contract supports future marketplace evidence without claiming that it
  exists today.
- No remote schema change is made.

### 2. Add typed listing-draft persistence

Add explicit Pydantic models, repository methods, and authenticated endpoints
for creating, reading, and editing a card's draft.

Candidate API:

```text
GET    /cards/{card_id}/listing-drafts
POST   /cards/{card_id}/listing-drafts
PATCH  /listing-drafts/{listing_id}
```

Acceptance criteria:

- Anonymous access is rejected.
- Cross-user card and listing IDs return 404.
- Ownership, IDs, generation metadata, and timestamps cannot be reassigned.
- Draft validation is covered by backend tests.

### 3. Isolate draft generation

Move listing-draft generation behind a dedicated service contract rather than
coupling it to card identification.

Proposed work:

- define a versioned structured output schema;
- record provider, model, and prompt version;
- retain the source analysis relationship;
- validate generated fields before persistence;
- make retries explicit and idempotent;
- preserve the existing prompt until a separately reviewed prompt change.

Acceptance criteria:

- Generation output can be tested with a mocked provider.
- A generation failure does not corrupt the card or an existing draft.
- Generated prices are recorded as AI estimates with provenance.
- No eBay API request is made.

### 4. Add draft review and editing

Extend the existing card UI with a simple listing-draft review state.

Proposed work:

- display generated title, description, price, and provenance;
- allow owner edits through FastAPI;
- distinguish generated values from manual overrides;
- support `draft` to `ready` after explicit review;
- avoid publishing language or controls.

Acceptance criteria:

- The user can review and edit a persisted draft.
- Price source and timestamp are visible.
- Saving is protected against duplicate submission.
- Inventory behavior remains unchanged.

### 5. Validate the no-publish boundary

Add tests and documentation proving that V0.3 cannot publish externally.

Required checks:

- no eBay credentials or OAuth configuration;
- no marketplace HTTP client capable of mutation;
- no `published` transition exposed by the API;
- owner and cross-user authorization tests;
- backend tests, Ruff, mypy, frontend lint, and frontend build;
- local Supabase migration and RLS validation.

## Suggested commits

```text
docs: define listing draft and pricing provenance contracts
feat: add local listing draft and pricing schema
test: validate listing draft ownership locally
feat: add owner-scoped listing draft API
feat: persist listing pricing provenance
feat: add listing draft review workflow
test: enforce v0.3 no-publish boundary
```

## Release gate

V0.3 is ready to tag only when:

1. Listing drafts persist separately from cards.
2. Every stored price has an explicit source type and timestamp.
3. Generated drafts record their provider, model, and prompt version.
4. Anonymous and cross-user draft access is denied.
5. Users can review and edit drafts without any live publishing action.
6. The complete V0.2 inventory workflow still passes.
7. Remote migration and RLS activation remain separately approved.
