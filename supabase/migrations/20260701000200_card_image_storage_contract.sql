-- PROPOSAL ONLY: do not apply locally or remotely until image upload
-- implementation and lifecycle tests are approved.

begin;

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'card-images',
  'card-images',
  false,
  10485760,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

alter table public.card_images
  drop constraint card_images_status_check;

alter table public.card_images
  alter column status set default 'pending';

alter table public.card_images
  add constraint card_images_status_check
  check (status in ('pending', 'active', 'failed', 'removed'));

create policy card_images_objects_insert_own
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'card-images'
  and owner_id = (select auth.uid()::text)
  and array_length(storage.foldername(name), 1) = 2
  and (storage.foldername(name))[1] = (select auth.uid()::text)
  and storage.extension(name) = any (array['jpg', 'png', 'webp'])
  and exists (
    select 1
    from public.card_images as card_image
    where card_image.owner_id = (select auth.uid())
      and card_image.card_id is not null
      and card_image.card_id::text = (storage.foldername(name))[2]
      and card_image.storage_bucket = bucket_id
      and card_image.storage_path = name
      and storage.filename(name) =
        card_image.id::text || '.' || storage.extension(name)
      and card_image.status = 'pending'
  )
);

create policy card_images_objects_select_own
on storage.objects
for select
to authenticated
using (
  bucket_id = 'card-images'
  and owner_id = (select auth.uid()::text)
  and array_length(storage.foldername(name), 1) = 2
  and (storage.foldername(name))[1] = (select auth.uid()::text)
  and exists (
    select 1
    from public.card_images as card_image
    where card_image.owner_id = (select auth.uid())
      and card_image.card_id is not null
      and card_image.card_id::text = (storage.foldername(name))[2]
      and card_image.storage_bucket = bucket_id
      and card_image.storage_path = name
      and storage.filename(name) =
        card_image.id::text || '.' || storage.extension(name)
      and card_image.status = 'active'
  )
);

create policy card_images_objects_delete_own
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'card-images'
  and owner_id = (select auth.uid()::text)
  and array_length(storage.foldername(name), 1) = 2
  and (storage.foldername(name))[1] = (select auth.uid()::text)
  and exists (
    select 1
    from public.card_images as card_image
    where card_image.owner_id = (select auth.uid())
      and card_image.card_id is not null
      and card_image.card_id::text = (storage.foldername(name))[2]
      and card_image.storage_bucket = bucket_id
      and card_image.storage_path = name
      and storage.filename(name) =
        card_image.id::text || '.' || storage.extension(name)
      and card_image.status in ('pending', 'active', 'failed')
  )
);

commit;
