# BulkMint V0.3.1 Release Notes

Released: July 2, 2026

Tag: `v0.3.1`

## Overview

V0.3.1 improves the listing-draft review experience while preserving the
existing backend, database, authentication, AI prompt, and marketplace
boundaries. It also handles missing or stale frontend authentication sessions
without triggering the Next.js development error overlay.

## UI Polish

- Improved spacing, field alignment, color contrast, focus styles, empty
  states, and loading feedback.
- Added responsive layouts for tablet and desktop widths.
- Constrained long titles, descriptions, and JSON to prevent overflow.
- Added tooltips and accessible labels to draft actions.

## Price Formatting

- Renamed the display field to **Suggested Price**.
- Formats USD values as `$5.00 USD`.
- Displays a clear fallback when no price is available.

## Item Specifics

- Replaced the primary raw JSON view with a readable table.
- Prioritizes card name, set, card number, rarity, condition, and language when
  available.
- Preserves a collapsible **View Raw JSON** section for advanced review.

## Keywords

- Displays generated keywords as compact chips.
- Added one-click copying for all keywords.

## Draft Versions

- Clearly identifies the selected draft.
- Highlights the newest draft with a **Latest** badge.
- Preserves access to every generated draft and its saved version.

## Card Image Preview

- Displays the stored card image alongside the selected draft.
- Uses a responsive layout and gracefully handles cards without an image.
- Opens a larger keyboard-accessible preview when selected.

## Copy Actions

- Added copy controls beside listing title and description headings.
- Preserved the existing copy-title, copy-description, and copy-JSON actions.
- Added accessible labels and clipboard success feedback.

## Validation

- Frontend lint: passed.
- Frontend production build: passed.
- Backend tests: 82 passed.
- Ruff: passed.
- mypy: passed.
- Local upload, analysis, inventory save, image persistence, draft generation,
  draft editing, regeneration, and version-history workflow: passed.
- Clipboard round-trip checks for title, description, and JSON: passed.

## Boundaries

- No backend behavior or API changes.
- No database or schema changes.
- No OpenAI prompt changes.
- No eBay integration or publishing.
