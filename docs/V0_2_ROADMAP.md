# BulkMint V0.2 Roadmap

Status: **completed — released as `v0.2.0`**

## Release outcome

V0.2 was completed and tagged at commit
`cc5f0815feed79641575588367a8cf2840a6ed21`.

Delivered:

- private, owner-scoped card image storage through FastAPI;
- short-lived signed image URLs for inventory display;
- compensating cleanup for failed image persistence and card deletion;
- owner-scoped inventory editing with explicit mutable fields;
- reversible archive and confirmed permanent deletion;
- server-side card-name search and set, rarity, and status filters;
- archived cards hidden by default;
- bounded inventory responses with a default limit of 50 and maximum of 100;
- frontend search/filter controls and clear loading, empty, and error states.

The release retained FastAPI as the application boundary and Supabase Auth as
the browser's only direct Supabase integration. Storage and RLS behavior was
validated locally. No remote Supabase migration or RLS rollout was performed.

Composite cursor pagination and card-number search were intentionally deferred.
The current bounded response avoids an unsafe partial cursor design; stable
keyset pagination should use both `created_at` and `id`.

## Original goal

V0.2 should make the authenticated inventory useful beyond the single-card
creation flow by adding:

- durable card-image storage;
- editing existing card records;
- deleting cards safely;
- searching and filtering inventory.

The release should preserve FastAPI as the application and authorization
boundary. The browser should continue using Supabase directly only for Auth.

## V0.1 baseline

The `v0.1.0` checkpoint provides:

- authenticated email/password sessions;
- FastAPI JWT verification;
- authenticated single-image analysis;
- upload type, size, and readability validation;
- review-before-save behavior;
- owner-scoped card create/list operations through FastAPI;
- a normalized local `cards` table contract.

The remote database migration and RLS policies remain unapplied.

## Non-goals

V0.2 should not include:

- bulk upload or background batch processing;
- eBay API integration or listing publication;
- OpenAI prompt changes;
- multi-user roles, teams, or sharing;
- mobile applications;
- remote migration or RLS activation without a separate reviewed rollout.

## Implementation constraints

The implementation followed these constraints:

1. Keep all schema and Storage work local until separately approved.
2. Confirm the normalized card contract is the canonical contract.
3. Use explicit Pydantic and TypeScript API models.
4. Support both reversible archive and confirmed permanent deletion.
5. Apply compensating image cleanup when card creation or deletion fails.
6. Preserve owner filtering in FastAPI and the authenticated user JWT on every
   Supabase request.

## Original implementation order

The sections below retain the implementation plan for historical context. The
release outcome above is authoritative where the delivered scope differs.

### 1. Image storage foundation

Image lifecycle affects card creation and deletion, so it should be completed
before those mutations expand.

Proposed work:

- Define a private `card-images` Storage bucket locally.
- Add owner-scoped Storage policy proposals.
- Use the existing `card_images` table for metadata.
- Store the original validated image only after the user confirms save.
- Generate storage paths server-side:
  `<owner_id>/<card_id>/<image_id>.<extension>`.
- Never accept an owner or storage path from the browser.
- Return a short-lived signed image URL through FastAPI.
- Compensate for partial failures so database rows and objects do not become
  orphaned.

Acceptance criteria:

- Owners can upload and view their own card images.
- Anonymous and cross-user access is denied in local tests.
- Invalid, oversized, and unreadable files remain rejected.
- Failed card/image operations leave no orphaned object or metadata row.

Suggested commits:

```text
docs: define card image storage contract
feat: add local card image storage policies
feat: persist card images through FastAPI
test: cover card image ownership and cleanup
```

### 2. Edit card

Proposed work:

- Add `PATCH /cards/{id}`.
- Define a dedicated update model with an explicit field allowlist.
- Derive ownership from the verified JWT and filter by both card ID and owner.
- Keep immutable fields such as `id`, `owner_id`, and `created_at` out of the
  request model.
- Add an edit mode to the current card review/inventory UI without redesigning
  the page.
- Use `updated_at` for conflict awareness.

Acceptance criteria:

- An owner can edit supported fields.
- Anonymous and cross-user updates are rejected.
- Ownership and immutable fields cannot be changed.
- Invalid price, currency, or status values return clear validation errors.

Suggested commits:

```text
feat: add owner-scoped card update endpoint
feat: add inventory card editing
test: cover card update authorization
```

### 3. Delete card

Start with a documented product decision:

- Archive should be the default reversible action when retention is useful.
- Permanent deletion should require explicit confirmation and remove associated
  image objects and metadata.

Proposed work:

- Add an owner-scoped archive endpoint or status update.
- Add `DELETE /cards/{id}` only if permanent deletion is approved.
- Delete Storage objects before or with compensating cleanup around database
  deletion.
- Add a confirmation step and clear success/failure state in the UI.

Acceptance criteria:

- Owners can archive or delete only their own records.
- Repeated requests are handled idempotently.
- Associated images do not become orphaned.
- The inventory updates only after the API confirms success.

Suggested commits:

```text
feat: add owner-scoped card archival
feat: add confirmed card deletion and image cleanup
test: cover card deletion lifecycle
```

### 4. Search and filter inventory

Proposed work:

- Extend `GET /cards` with explicit query parameters:
  `q`, `status`, `set_name`, `rarity`, `limit`, and `cursor`.
- Search only owner-scoped rows.
- Add reviewed indexes based on measured query plans.
- Add debounced search and compact filters to the existing inventory section.
- Keep filtering server-side so behavior scales beyond a small local list.

Acceptance criteria:

- Search covers card name, set name, and card number.
- Filters can be combined and cleared.
- Results remain owner-scoped and consistently ordered.
- Pagination prevents unbounded inventory responses.
- Empty, loading, and error states remain clear.

Suggested commits:

```text
feat: add owner-scoped inventory search API
feat: add inventory search and filters
test: cover search filters and pagination
```

## Cross-cutting requirements

Every V0.2 increment should include:

- backend tests, Ruff, and mypy;
- frontend lint and production build;
- anonymous, owner, and cross-user authorization tests;
- no secrets or service-role key in browser code;
- explicit API errors without access-token leakage;
- local validation before any remote change;
- migration and rollback documentation for schema or Storage changes.

## Release gate result

The V0.2 release gate passed:

1. Image upload, retrieval, and cleanup passed local ownership tests.
2. Edit, archive, and delete actions are owner-scoped.
3. Search/filter responses are bounded and owner-scoped.
4. Backend tests, Ruff, mypy, frontend lint, and frontend build passed.
5. Remote migration and RLS rollout remain separately approved and documented.
