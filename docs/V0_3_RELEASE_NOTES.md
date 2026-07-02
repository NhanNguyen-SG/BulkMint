# BulkMint V0.3 Release Notes

Released: July 2, 2026
Tag: `v0.3.0`

## Overview

V0.3 adds an authenticated, owner-scoped workflow for creating and reviewing
AI-generated listing drafts. Listing drafts remain private application data:
this release does not authenticate with eBay, call eBay APIs, or publish
listings.

## Included

### Listing Draft API

- Added authenticated endpoints to create, list, retrieve, and update listing
  drafts.
- Enforced owner-scoped access with `401` responses for anonymous requests and
  `404` responses for cross-user resources.
- Persisted structured listing content, pricing provenance, generation model,
  prompt version, and audit events.

### Listing Draft UI

- Added draft generation and review controls to inventory cards.
- Displays title, description, price, currency, status, category suggestion,
  item specifics, and draft version.
- Includes copy buttons for the title, description, and item-specifics JSON.
- Provides loading, success, and error states for draft operations.

### AI Listing Draft Generation

- Added a separate, versioned listing-generation prompt
  (`listing-draft-v1`) without changing the card-analysis prompt.
- Generates validated title, description, condition summary, category
  suggestion, item specifics, keywords, and an optional price estimate.
- Uses saved card data and the stored card image when one is available.
- Records generated prices as AI estimates with model and prompt provenance.

### Draft Version History

- Regenerating creates a new draft and preserves existing drafts.
- Updating a draft increments its version and records an audit event.
- Generated model and prompt metadata remain attached to each saved draft.

### Manual Editing

- Users can edit allowed draft fields through the authenticated API.
- Manual price changes create separate manual pricing provenance.
- Ownership, card relationships, IDs, and generation metadata cannot be
  reassigned through the edit API.

## Validation

- Backend test suite: 82 tests passed.
- Ruff: passed.
- mypy: passed.
- Frontend lint: passed.
- Frontend production build: passed.
- Local create, edit, regenerate, and version-history workflow: passed.

## Not Included

- No eBay OAuth or credential storage.
- No eBay API integration.
- No live listing publication, revision, or deletion.
- No remote Supabase migration or RLS rollout.
