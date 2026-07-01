-- PROPOSAL ONLY: do not apply to the current Supabase project until the
-- existing cards table has been inventoried and its rows have an owner mapping.

begin;

create extension if not exists pgcrypto with schema extensions;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

revoke all on function public.set_updated_at() from public;

create table public.cards (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  card_name text not null,
  set_name text,
  card_number text,
  rarity text,
  condition_guess text,
  price_amount numeric(12, 2),
  currency text not null default 'USD',
  status text not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint cards_id_owner_key unique (id, owner_id),
  constraint cards_price_amount_check check (price_amount is null or price_amount >= 0),
  constraint cards_currency_check check (currency ~ '^[A-Z]{3}$'),
  constraint cards_status_check check (
    status in ('draft', 'active', 'listed', 'sold', 'archived')
  )
);

create table public.card_images (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  card_id uuid,
  storage_bucket text not null default 'card-images',
  storage_path text not null,
  image_kind text not null default 'front',
  mime_type text not null,
  byte_size bigint,
  sha256 text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint card_images_id_owner_key unique (id, owner_id),
  constraint card_images_card_owner_fkey
    foreign key (card_id, owner_id)
    references public.cards (id, owner_id)
    on delete cascade,
  constraint card_images_storage_object_key unique (storage_bucket, storage_path),
  constraint card_images_kind_check check (image_kind in ('front', 'back', 'detail', 'other')),
  constraint card_images_byte_size_check check (byte_size is null or byte_size >= 0),
  constraint card_images_sha256_check check (
    sha256 is null or sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint card_images_status_check check (status in ('active', 'removed'))
);

create table public.analysis_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  card_id uuid,
  input_image_id uuid,
  status text not null default 'pending',
  provider text not null default 'openai',
  model text,
  prompt_version text,
  idempotency_key text,
  result jsonb,
  error_code text,
  error_message text,
  attempt_count integer not null default 0,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint analysis_jobs_id_owner_key unique (id, owner_id),
  constraint analysis_jobs_card_owner_fkey
    foreign key (card_id, owner_id)
    references public.cards (id, owner_id)
    on delete set null (card_id),
  constraint analysis_jobs_image_owner_fkey
    foreign key (input_image_id, owner_id)
    references public.card_images (id, owner_id)
    on delete set null (input_image_id),
  constraint analysis_jobs_status_check check (
    status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')
  ),
  constraint analysis_jobs_attempt_count_check check (attempt_count >= 0)
);

create table public.listings (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  card_id uuid not null,
  analysis_job_id uuid,
  marketplace text not null,
  external_listing_id text,
  status text not null default 'draft',
  title text,
  description text,
  price_amount numeric(12, 2),
  currency text not null default 'USD',
  quantity integer not null default 1,
  published_at timestamptz,
  ended_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint listings_id_owner_key unique (id, owner_id),
  constraint listings_card_owner_fkey
    foreign key (card_id, owner_id)
    references public.cards (id, owner_id)
    on delete cascade,
  constraint listings_analysis_job_owner_fkey
    foreign key (analysis_job_id, owner_id)
    references public.analysis_jobs (id, owner_id)
    on delete set null (analysis_job_id),
  constraint listings_price_amount_check check (price_amount is null or price_amount >= 0),
  constraint listings_currency_check check (currency ~ '^[A-Z]{3}$'),
  constraint listings_quantity_check check (quantity > 0),
  constraint listings_status_check check (
    status in ('draft', 'ready', 'published', 'ended', 'sold', 'error')
  )
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  actor_id uuid default auth.uid() references auth.users(id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id uuid,
  old_data jsonb,
  new_data jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index analysis_jobs_owner_idempotency_key
  on public.analysis_jobs (owner_id, idempotency_key)
  where idempotency_key is not null;

create unique index listings_marketplace_external_id_key
  on public.listings (marketplace, external_listing_id)
  where external_listing_id is not null;

create index cards_owner_created_at_idx
  on public.cards (owner_id, created_at desc);
create index cards_owner_status_idx
  on public.cards (owner_id, status);
create index cards_owner_identity_idx
  on public.cards (owner_id, set_name, card_number);

create index card_images_owner_card_idx
  on public.card_images (owner_id, card_id);
create index card_images_owner_sha256_idx
  on public.card_images (owner_id, sha256)
  where sha256 is not null;

create index analysis_jobs_owner_status_created_at_idx
  on public.analysis_jobs (owner_id, status, created_at desc);
create index analysis_jobs_owner_card_idx
  on public.analysis_jobs (owner_id, card_id);

create index listings_owner_status_created_at_idx
  on public.listings (owner_id, status, created_at desc);
create index listings_owner_card_idx
  on public.listings (owner_id, card_id);

create index audit_events_owner_created_at_idx
  on public.audit_events (owner_id, created_at desc);
create index audit_events_owner_entity_idx
  on public.audit_events (owner_id, entity_type, entity_id);

create trigger cards_set_updated_at
before update on public.cards
for each row execute function public.set_updated_at();

create trigger card_images_set_updated_at
before update on public.card_images
for each row execute function public.set_updated_at();

create trigger analysis_jobs_set_updated_at
before update on public.analysis_jobs
for each row execute function public.set_updated_at();

create trigger listings_set_updated_at
before update on public.listings
for each row execute function public.set_updated_at();

alter table public.cards enable row level security;
alter table public.card_images enable row level security;
alter table public.analysis_jobs enable row level security;
alter table public.listings enable row level security;
alter table public.audit_events enable row level security;

create policy cards_select_own
on public.cards for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy cards_insert_own
on public.cards for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy cards_update_own
on public.cards for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy cards_delete_own
on public.cards for delete
to authenticated
using ((select auth.uid()) = owner_id);

create policy card_images_select_own
on public.card_images for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy card_images_insert_own
on public.card_images for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy card_images_update_own
on public.card_images for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy card_images_delete_own
on public.card_images for delete
to authenticated
using ((select auth.uid()) = owner_id);

create policy analysis_jobs_select_own
on public.analysis_jobs for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy analysis_jobs_insert_own
on public.analysis_jobs for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy analysis_jobs_update_own
on public.analysis_jobs for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy analysis_jobs_delete_own
on public.analysis_jobs for delete
to authenticated
using ((select auth.uid()) = owner_id);

create policy listings_select_own
on public.listings for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy listings_insert_own
on public.listings for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy listings_update_own
on public.listings for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy listings_delete_own
on public.listings for delete
to authenticated
using ((select auth.uid()) = owner_id);

create policy audit_events_select_own
on public.audit_events for select
to authenticated
using ((select auth.uid()) = owner_id);

revoke all on table
  public.cards,
  public.card_images,
  public.analysis_jobs,
  public.listings,
  public.audit_events
from public, anon, authenticated;

grant select, insert, update, delete on table
  public.cards,
  public.card_images,
  public.analysis_jobs,
  public.listings
to authenticated;

grant select on table public.audit_events to authenticated;

grant all privileges on table
  public.cards,
  public.card_images,
  public.analysis_jobs,
  public.listings,
  public.audit_events
to service_role;

comment on table public.cards is
  'User-owned trading card inventory records.';
comment on table public.card_images is
  'Metadata for card images stored outside PostgreSQL.';
comment on table public.analysis_jobs is
  'Durable state and validated output for card analysis attempts.';
comment on table public.listings is
  'Marketplace-neutral listing drafts and publication state.';
comment on table public.audit_events is
  'Immutable user-visible audit records written by trusted server code.';

commit;
