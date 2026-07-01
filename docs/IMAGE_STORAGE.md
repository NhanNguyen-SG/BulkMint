# Card Image Storage Contract

Status: **implemented and validated locally — not applied remotely**

The proposed SQL is in
`supabase/migrations/20260701000200_card_image_storage_contract.sql`. It has
been applied and validated against local Supabase only.

## Design goals

- Keep original card images private.
- Make FastAPI the only application boundary for upload and retrieval.
- Preserve the authenticated user's JWT through FastAPI so Storage RLS remains
  the final authorization control.
- Prevent users from selecting `owner_id`, `card_id`, `image_id`, bucket, or
  object path.
- Make partial upload and deletion failures detectable and recoverable.
- Keep one object path immutable for the lifetime of an image record.

## Bucket

| Setting | Value |
|---|---|
| Bucket ID and name | `card-images` |
| Access model | Private |
| File-size limit | 10 MiB (`10485760` bytes) |
| Allowed MIME types | `image/jpeg`, `image/png`, `image/webp` |
| Overwrite/upsert | Not allowed |
| Normal downloads | Authenticated request or short-lived signed URL |

The bucket limit duplicates the FastAPI limit intentionally. FastAPI validates
before upload, while Storage remains protected if an application validation
path is bypassed.

A private bucket subjects downloads to RLS; public object URLs must not be
used. FastAPI should return signed URLs with a five-minute default lifetime
when the UI needs to display an image.

References:

- [Supabase private buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals)
- [Bucket MIME and size restrictions](https://supabase.com/docs/guides/storage/buckets/creating-buckets)

## Canonical object path

```text
<owner_id>/<card_id>/<image_id>.<extension>
```

Example:

```text
8e8c6a24-7c8b-4df6-bbd6-c8e40caa673d/
70d67158-d724-4c60-b85d-aa84409cf0c9/
dd96227f-cc4d-443d-99f3-cbaca7fc5191.jpg
```

The actual path is one line; it is wrapped above for readability.

Rules:

- All three IDs are UUIDs generated or derived by FastAPI.
- `owner_id` is the verified JWT `sub`.
- `card_id` must identify a card owned by the same user.
- `image_id` is generated before metadata insertion and is also
  `card_images.id`.
- Extension is derived from the decoded image format:
  - JPEG becomes `jpg`
  - PNG becomes `png`
  - WebP becomes `webp`
- Original filenames are never used.
- Paths are immutable. Replacing an image creates a new image ID and object.
- Upload uses `upsert=false`.

The policies use `storage.foldername(name)`, `storage.filename(name)`, and
`storage.extension(name)` to validate this structure:
[Supabase Storage helper functions](https://supabase.com/docs/guides/storage/schema/helper-functions).

## Metadata relationship

The existing `public.card_images` table remains the metadata authority:

```text
auth.users.id
      │
      └── owner_id
            │
cards (id, owner_id)
      │
      └── card_images (card_id, owner_id)
            │
            └── storage.objects (bucket_id, name)
```

Mapping:

| `card_images` field | Storage meaning |
|---|---|
| `id` | `image_id` and filename stem |
| `owner_id` | First path segment and JWT subject |
| `card_id` | Second path segment |
| `storage_bucket` | Always `card-images` |
| `storage_path` | Complete canonical object path |
| `mime_type` | Verified MIME type |
| `byte_size` | Validated original byte count |
| `sha256` | Lowercase SHA-256 of original bytes |
| `image_kind` | `front`, `back`, `detail`, or `other` |
| `status` | Object lifecycle state |

The existing composite foreign key `(card_id, owner_id)` to
`cards(id, owner_id)` prevents cross-owner metadata relationships. The unique
constraint on `(storage_bucket, storage_path)` prevents two metadata rows from
claiming one object.

For V0.2 persisted images, `card_id` is required by application validation even
though the Phase 2 schema keeps it nullable for potential pre-card intake.

## Lifecycle states

The migration proposal expands `card_images.status`:

| Status | Meaning |
|---|---|
| `pending` | Metadata exists; object upload or activation is incomplete |
| `active` | Metadata and object both exist and may be read |
| `failed` | Compensation was incomplete and reconciliation is required |
| `removed` | Object was deleted and metadata is retained as a tombstone |

Only `active` objects are readable. Upload policy requires `pending` metadata.
Delete policy accepts `pending`, `active`, or `failed` so cleanup remains
possible.

## Proposed Storage policies

All policies apply only to the `authenticated` role and the private
`card-images` bucket.

### Owner upload

`INSERT` is allowed only when:

- Storage assigns `storage.objects.owner_id` to `auth.uid()`;
- the first path segment equals `auth.uid()`;
- the path has exactly the owner and card folders;
- extension is `jpg`, `png`, or `webp`;
- a `pending` `card_images` row exists for the same owner, card, bucket, path,
  and filename image ID.

There is no `UPDATE` policy. Therefore upsert, overwrite, move, and replacement
are denied.

### Owner read

`SELECT` is allowed only when:

- object ownership and first path segment match `auth.uid()`;
- matching metadata belongs to the user; and
- metadata status is `active`.

This policy governs authenticated downloads and signed-URL creation.

### Owner delete

`DELETE` is allowed only when:

- object ownership and first path segment match `auth.uid()`; and
- matching owned metadata is `pending`, `active`, or `failed`.

Objects must be deleted with the Storage API. Deleting a `storage.objects` row
directly with SQL can orphan the underlying object:
[Supabase object deletion](https://supabase.com/docs/guides/storage/management/delete-objects).

### Anonymous and cross-user denial

- The bucket is private.
- No policies target `anon`.
- Every policy targets `authenticated` and checks Storage ownership, the first
  path segment, and owned metadata.
- `card_images` and `cards` RLS independently restrict the metadata subqueries.
- No service/secret key is exposed to the frontend.

Absence of an allowing policy denies the operation. Supabase Storage uses RLS
on `storage.objects` for this access model:
[Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control).

## Upload sequence

The FastAPI implementation uses this order:

1. FastAPI verifies the user JWT.
2. FastAPI revalidates MIME type, decoded image, size, and hash.
3. FastAPI confirms the card belongs to the verified user.
4. FastAPI generates `image_id` and the canonical path.
5. FastAPI inserts `card_images` metadata with status `pending`.
6. FastAPI uploads once with the user's JWT and `upsert=false`.
7. FastAPI updates metadata from `pending` to `active`.
8. FastAPI returns image metadata and, when needed, a short-lived signed URL.

The browser never writes Storage or `card_images` directly.

## API behavior

`POST /cards` accepts multipart form data:

- `card`: required JSON matching the card creation contract;
- `image`: optional original JPEG, PNG, or WebP file.

FastAPI validates the image again, generates the card and image IDs, creates
the canonical path, and runs the lifecycle above. No storage path, owner ID,
card ID, or image ID is accepted from browser input.

`GET /cards` returns these additional fields:

- `image_id`: active front-image UUID, or null;
- `image_url`: private signed URL valid for five minutes, or null.

The frontend submits the original selected file only after review/save and
renders the returned signed URL in inventory.

## Cleanup and compensation

Storage and PostgreSQL do not share one transaction. Each failure point needs a
compensating action.

| Failure | Immediate compensation | Final state |
|---|---|---|
| Metadata insert fails | Do not upload | No row, no object |
| Object upload fails | Delete pending metadata | No row, no object |
| Activation update fails | Delete object through Storage API, then delete metadata | No row, no object |
| Object cleanup fails | Mark metadata `failed` | Reconciliation required |
| Card save fails before image workflow | Do not create metadata or upload | No image state |
| Image delete fails | Keep metadata unchanged or mark `failed` | Retry safely |
| Object delete succeeds but metadata update fails | Retry tombstone update; object deletion is idempotent | Reconciliation required |

Card deletion must enumerate and delete owned Storage objects before deleting
the card row. PostgreSQL cascade removes metadata rows but cannot remove
Storage objects.

A future reconciliation command should compare `card_images` with
`storage.objects` and report:

- `pending` rows older than a short threshold;
- `failed` rows;
- metadata without objects;
- objects without metadata;
- path/owner/card mismatches.

It should default to report-only mode. Destructive cleanup requires a separate
explicit flag and audit event.

## Local validation plan

After implementation is approved:

1. Apply the proposal to local Supabase only.
2. Create two authenticated users and one owned card each.
3. Verify owner upload/read/delete.
4. Verify anonymous upload/read/delete denial.
5. Verify user B cannot access user A's path, even when IDs are known.
6. Verify invalid extensions, oversized files, malformed paths, missing
   metadata, and non-pending uploads are rejected.
7. Simulate each partial failure and confirm compensation.
8. Confirm no direct SQL object deletion is used.

Do not link to or push this migration to the remote Supabase project without a
separate approval and rollout review.

## Local validation result

Validated locally on 2026-07-01 with Supabase CLI 2.109.0:

```bash
supabase db reset
./supabase/tests/card_image_storage_local.sh
```

Results:

- Both migrations applied successfully from a clean local reset.
- The bucket is private with a 10 MiB limit and the three expected MIME types.
- Anonymous upload and read were denied.
- Owner upload, active-object read, and delete succeeded.
- Cross-user read and delete were denied.
- Metadata create/read remained owner-scoped.
- Owner, card, and image ID path mismatches were denied.
- An owner upload without existing `pending` metadata was denied.
- The successful lifecycle used metadata-first ordering:
  `pending metadata → object upload → active metadata`.
- Cleanup deleted the object through the Storage API, then deleted metadata;
  direct database verification found no remaining object.

No migration change was required. The migration was not applied to any remote
Supabase project.

## Deliberate exclusions

- No direct browser Storage access is implemented.
- No remote migration is applied.
- No service-role client is introduced.
- No public bucket or permanent URL is introduced.
- No image transformation, thumbnail, or CDN policy is introduced.
