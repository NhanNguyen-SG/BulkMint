begin;

update storage.buckets
set
  file_size_limit = 26214400,
  allowed_mime_types = array[
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/heic',
    'image/heif',
    'image/avif'
  ]
where id = 'card-images';

alter policy card_images_objects_insert_own
on storage.objects
with check (
  bucket_id = 'card-images'
  and owner_id = (select auth.uid()::text)
  and array_length(storage.foldername(name), 1) = 2
  and (storage.foldername(name))[1] = (select auth.uid()::text)
  and storage.extension(name) = any (
    array['jpg', 'png', 'webp', 'heic', 'heif', 'avif']
  )
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

commit;
