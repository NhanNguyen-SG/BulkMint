-- PROPOSAL ONLY: do not apply to the remote Supabase project.
-- This migration refines the unused Phase 2 listings proposal into the V0.3
-- listing-draft and pricing-provenance contract. It intentionally refuses to
-- run when legacy listing rows exist because no production backfill has been
-- designed or approved.

begin;

do $$
begin
  if exists (select 1 from public.listings limit 1) then
    raise exception
      'listing contract migration requires an explicit backfill for existing rows';
  end if;
end;
$$;

drop index public.listings_marketplace_external_id_key;

alter table public.listings rename to listing_drafts;

alter table public.listing_drafts
  rename constraint listings_pkey to listing_drafts_pkey;
alter table public.listing_drafts
  rename constraint listings_id_owner_key to listing_drafts_id_owner_key;
alter table public.listing_drafts
  rename constraint listings_card_owner_fkey to listing_drafts_card_owner_fkey;
alter table public.listing_drafts
  rename constraint listings_analysis_job_owner_fkey
  to listing_drafts_analysis_job_owner_fkey;
alter table public.listing_drafts
  rename constraint listings_price_amount_check
  to listing_drafts_price_amount_check;
alter table public.listing_drafts
  rename constraint listings_currency_check
  to listing_drafts_currency_check;
alter table public.listing_drafts
  rename constraint listings_quantity_check
  to listing_drafts_quantity_check;
alter table public.listing_drafts
  rename constraint listings_status_check
  to listing_drafts_status_check;

alter index public.listings_owner_status_created_at_idx
  rename to listing_drafts_owner_status_created_at_idx;
alter index public.listings_owner_card_idx
  rename to listing_drafts_owner_card_idx;

alter trigger listings_set_updated_at on public.listing_drafts
  rename to listing_drafts_set_updated_at;

alter policy listings_select_own on public.listing_drafts
  rename to listing_drafts_select_own;
alter policy listings_insert_own on public.listing_drafts
  rename to listing_drafts_insert_own;
alter policy listings_update_own on public.listing_drafts
  rename to listing_drafts_update_own;
alter policy listings_delete_own on public.listing_drafts
  rename to listing_drafts_delete_own;

alter table public.listing_drafts
  rename column marketplace to marketplace_target;

alter table public.listing_drafts
  drop column external_listing_id,
  drop column published_at,
  drop column ended_at,
  drop constraint listing_drafts_status_check,
  add column content_origin text not null default 'manual',
  add column generated_title text,
  add column generated_description text,
  add column generation_provider text,
  add column generation_model text,
  add column prompt_version text,
  add column generated_at timestamptz,
  add column ready_at timestamptz,
  add column archived_at timestamptz,
  add constraint listing_drafts_marketplace_target_check check (
    marketplace_target ~ '^[a-z][a-z0-9_-]{1,31}$'
  ),
  add constraint listing_drafts_status_check check (
    status in ('draft', 'ready', 'archived')
  ),
  add constraint listing_drafts_content_origin_check check (
    content_origin in ('manual', 'ai_generated', 'ai_assisted', 'imported')
  ),
  add constraint listing_drafts_title_length_check check (
    title is null or char_length(title) <= 200
  ),
  add constraint listing_drafts_description_length_check check (
    description is null or char_length(description) <= 10000
  ),
  add constraint listing_drafts_generation_metadata_check check (
    (
      content_origin in ('ai_generated', 'ai_assisted')
      and nullif(btrim(generated_title), '') is not null
      and nullif(btrim(generated_description), '') is not null
      and nullif(btrim(generation_provider), '') is not null
      and nullif(btrim(generation_model), '') is not null
      and nullif(btrim(prompt_version), '') is not null
      and generated_at is not null
    )
    or (
      content_origin not in ('ai_generated', 'ai_assisted')
      and generated_title is null
      and generated_description is null
      and generation_provider is null
      and generation_model is null
      and prompt_version is null
      and generated_at is null
    )
  ),
  add constraint listing_drafts_lifecycle_timestamp_check check (
    (status <> 'ready' or ready_at is not null)
    and (status <> 'archived' or archived_at is not null)
  );

alter table public.listing_drafts
  alter column marketplace_target set default 'ebay';

create table public.pricing_sources (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  source_type text not null,
  source_name text not null,
  source_url text,
  marketplace text,
  created_at timestamptz not null default now(),
  constraint pricing_sources_id_owner_key unique (id, owner_id),
  constraint pricing_sources_type_check check (
    source_type in ('ai', 'manual', 'marketplace', 'derived', 'other')
  ),
  constraint pricing_sources_name_check check (
    char_length(btrim(source_name)) between 1 and 200
  ),
  constraint pricing_sources_url_check check (
    source_url is null or source_url ~ '^https?://'
  ),
  constraint pricing_sources_marketplace_check check (
    marketplace is null or marketplace ~ '^[a-z][a-z0-9_-]{1,31}$'
  )
);

create unique index pricing_sources_owner_identity_key
  on public.pricing_sources (
    owner_id,
    source_type,
    lower(source_name),
    coalesce(source_url, ''),
    coalesce(marketplace, '')
  );

create index pricing_sources_owner_created_at_idx
  on public.pricing_sources (owner_id, created_at desc);

create table public.pricing_observations (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  card_id uuid not null,
  pricing_source_id uuid not null,
  analysis_job_id uuid,
  price_kind text not null,
  observed_price numeric(12, 2) not null,
  currency text not null default 'USD',
  condition text,
  observed_at timestamptz not null,
  confidence numeric(5, 4),
  evidence_url text,
  generation_provider text,
  generation_model text,
  prompt_version text,
  methodology text,
  method_version text,
  recorded_by uuid default auth.uid()
    references auth.users(id) on delete set null,
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint pricing_observations_id_owner_key unique (id, owner_id),
  constraint pricing_observations_id_owner_card_key
    unique (id, owner_id, card_id),
  constraint pricing_observations_card_owner_fkey
    foreign key (card_id, owner_id)
    references public.cards (id, owner_id)
    on delete cascade,
  constraint pricing_observations_source_owner_fkey
    foreign key (pricing_source_id, owner_id)
    references public.pricing_sources (id, owner_id)
    on delete no action
    deferrable initially deferred,
  constraint pricing_observations_analysis_job_owner_fkey
    foreign key (analysis_job_id, owner_id)
    references public.analysis_jobs (id, owner_id)
    on delete set null (analysis_job_id),
  constraint pricing_observations_kind_check check (
    price_kind in ('asking', 'sold', 'estimate', 'manual_override')
  ),
  constraint pricing_observations_price_check check (observed_price >= 0),
  constraint pricing_observations_currency_check check (
    currency ~ '^[A-Z]{3}$'
  ),
  constraint pricing_observations_condition_check check (
    condition is null or char_length(condition) <= 100
  ),
  constraint pricing_observations_confidence_check check (
    confidence is null or confidence between 0 and 1
  ),
  constraint pricing_observations_evidence_url_check check (
    evidence_url is null or evidence_url ~ '^https?://'
  ),
  constraint pricing_observations_generation_metadata_check check (
    (
      generation_provider is null
      and generation_model is null
      and prompt_version is null
    )
    or (
      nullif(btrim(generation_provider), '') is not null
      and nullif(btrim(generation_model), '') is not null
      and nullif(btrim(prompt_version), '') is not null
    )
  ),
  constraint pricing_observations_method_metadata_check check (
    (
      methodology is null
      and method_version is null
    )
    or (
      nullif(btrim(methodology), '') is not null
      and nullif(btrim(method_version), '') is not null
    )
  )
);

create or replace function public.validate_pricing_observation_source()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  selected_source_type text;
begin
  select source.source_type
  into selected_source_type
  from public.pricing_sources as source
  where source.id = new.pricing_source_id
    and source.owner_id = new.owner_id;

  if not found then
    raise exception 'pricing source does not belong to observation owner';
  end if;

  if selected_source_type = 'ai' then
    if new.price_kind <> 'estimate'
      or new.generation_provider is null
      or new.methodology is not null then
      raise exception 'AI sources require estimate kind and generation metadata';
    end if;
  elsif selected_source_type = 'manual' then
    if new.price_kind <> 'manual_override'
      or new.recorded_by is null
      or new.generation_provider is not null
      or new.methodology is not null
      or new.confidence is not null then
      raise exception 'manual sources require actor-backed manual overrides';
    end if;
  elsif selected_source_type = 'marketplace' then
    if new.price_kind not in ('asking', 'sold')
      or new.evidence_url is null
      or new.generation_provider is not null
      or new.methodology is not null
      or new.confidence is not null then
      raise exception 'marketplace sources require URL-backed asking or sold evidence';
    end if;
  elsif selected_source_type = 'derived' then
    if new.price_kind <> 'estimate'
      or new.methodology is null
      or new.generation_provider is not null then
      raise exception 'derived sources require estimate kind and versioned method';
    end if;
  elsif new.generation_provider is not null or new.methodology is not null then
    raise exception 'other sources cannot claim AI or derived provenance';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_pricing_observation_source() from public;

create trigger pricing_observations_validate_source
before insert on public.pricing_observations
for each row execute function public.validate_pricing_observation_source();

create index pricing_observations_owner_card_observed_at_idx
  on public.pricing_observations (owner_id, card_id, observed_at desc);
create index pricing_observations_owner_source_observed_at_idx
  on public.pricing_observations (
    owner_id,
    pricing_source_id,
    observed_at desc
  );
create index pricing_observations_owner_analysis_job_idx
  on public.pricing_observations (owner_id, analysis_job_id)
  where analysis_job_id is not null;

create table public.pricing_observation_inputs (
  owner_id uuid not null default auth.uid()
    references auth.users(id) on delete cascade,
  card_id uuid not null,
  derived_observation_id uuid not null,
  input_observation_id uuid not null,
  weight numeric(5, 4),
  created_at timestamptz not null default now(),
  primary key (derived_observation_id, input_observation_id),
  constraint pricing_observation_inputs_card_owner_fkey
    foreign key (card_id, owner_id)
    references public.cards (id, owner_id)
    on delete cascade,
  constraint pricing_observation_inputs_derived_owner_card_fkey
    foreign key (derived_observation_id, owner_id, card_id)
    references public.pricing_observations (id, owner_id, card_id)
    on delete cascade,
  constraint pricing_observation_inputs_input_owner_card_fkey
    foreign key (input_observation_id, owner_id, card_id)
    references public.pricing_observations (id, owner_id, card_id)
    on delete cascade,
  constraint pricing_observation_inputs_distinct_check check (
    derived_observation_id <> input_observation_id
  ),
  constraint pricing_observation_inputs_weight_check check (
    weight is null or weight between 0 and 1
  )
);

create index pricing_observation_inputs_owner_card_idx
  on public.pricing_observation_inputs (owner_id, card_id);

create or replace function public.validate_pricing_observation_input()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  derived_source_type text;
  derived_observed_at timestamptz;
  input_observed_at timestamptz;
begin
  select source.source_type, derived.observed_at, input.observed_at
  into derived_source_type, derived_observed_at, input_observed_at
  from public.pricing_observations as derived
  join public.pricing_sources as source
    on source.id = derived.pricing_source_id
    and source.owner_id = derived.owner_id
  join public.pricing_observations as input
    on input.id = new.input_observation_id
    and input.owner_id = derived.owner_id
    and input.card_id = derived.card_id
  where derived.id = new.derived_observation_id
    and derived.owner_id = new.owner_id
    and derived.card_id = new.card_id;

  if not found or derived_source_type <> 'derived' then
    raise exception 'pricing input target must be an owned derived observation';
  end if;

  if derived_observed_at < input_observed_at then
    raise exception 'derived observation cannot predate its input';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_pricing_observation_input() from public;

create trigger pricing_observation_inputs_validate
before insert on public.pricing_observation_inputs
for each row execute function public.validate_pricing_observation_input();

alter table public.listing_drafts
  add column selected_pricing_observation_id uuid,
  add constraint listing_drafts_selected_pricing_owner_card_fkey
    foreign key (selected_pricing_observation_id, owner_id, card_id)
    references public.pricing_observations (id, owner_id, card_id)
    on delete no action
    deferrable initially deferred,
  add constraint listing_drafts_price_provenance_check check (
    (price_amount is null) = (selected_pricing_observation_id is null)
  ),
  add constraint listing_drafts_ready_content_check check (
    status <> 'ready'
    or (
      nullif(btrim(title), '') is not null
      and nullif(btrim(description), '') is not null
      and price_amount is not null
      and selected_pricing_observation_id is not null
    )
  );

create or replace function public.validate_listing_draft_pricing()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  selected_price numeric(12, 2);
  selected_currency text;
begin
  if new.selected_pricing_observation_id is null then
    return new;
  end if;

  select observation.observed_price, observation.currency
  into selected_price, selected_currency
  from public.pricing_observations as observation
  where observation.id = new.selected_pricing_observation_id
    and observation.owner_id = new.owner_id
    and observation.card_id = new.card_id;

  if not found then
    raise exception 'selected pricing observation does not belong to draft card';
  end if;

  if new.price_amount is distinct from selected_price
    or new.currency is distinct from selected_currency then
    raise exception
      'draft price and currency must match selected pricing observation';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_listing_draft_pricing() from public;

create trigger listing_drafts_validate_pricing
before insert or update of
  selected_pricing_observation_id,
  price_amount,
  currency,
  card_id,
  owner_id
on public.listing_drafts
for each row execute function public.validate_listing_draft_pricing();

alter table public.pricing_sources enable row level security;
alter table public.pricing_observations enable row level security;
alter table public.pricing_observation_inputs enable row level security;

create policy pricing_sources_select_own
on public.pricing_sources for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy pricing_sources_insert_own
on public.pricing_sources for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy pricing_observations_select_own
on public.pricing_observations for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy pricing_observations_insert_own
on public.pricing_observations for insert
to authenticated
with check (
  (select auth.uid()) = owner_id
  and (
    recorded_by is null
    or recorded_by = (select auth.uid())
  )
);

create policy pricing_observation_inputs_select_own
on public.pricing_observation_inputs for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy pricing_observation_inputs_insert_own
on public.pricing_observation_inputs for insert
to authenticated
with check ((select auth.uid()) = owner_id);

revoke all on table
  public.pricing_sources,
  public.pricing_observations,
  public.pricing_observation_inputs
from public, anon, authenticated;

grant select, insert on table
  public.pricing_sources,
  public.pricing_observations,
  public.pricing_observation_inputs
to authenticated;

grant all privileges on table
  public.pricing_sources,
  public.pricing_observations,
  public.pricing_observation_inputs
to service_role;

revoke update on table public.listing_drafts from authenticated;

grant update (
  status,
  title,
  description,
  price_amount,
  currency,
  quantity,
  selected_pricing_observation_id,
  content_origin,
  ready_at,
  archived_at
) on table public.listing_drafts to authenticated;

comment on table public.listing_drafts is
  'Owner-scoped marketplace-formatted drafts; never proof of publication.';
comment on table public.pricing_sources is
  'Immutable owner-scoped identities for price evidence sources.';
comment on table public.pricing_observations is
  'Append-only owner-scoped price evidence and estimates.';
comment on table public.pricing_observation_inputs is
  'Append-only inputs used to derive a pricing observation.';
comment on column public.listing_drafts.marketplace_target is
  'Formatting target only; it does not indicate marketplace publication.';
comment on column public.listing_drafts.selected_pricing_observation_id is
  'Price provenance selected as the draft asking price.';

commit;
