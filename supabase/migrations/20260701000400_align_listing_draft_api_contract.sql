-- LOCAL-ONLY CONTRACT FIX: do not apply to the remote Supabase project.
-- Adds the fields required by the approved V0.3 Listing Draft API without
-- changing AI generation or marketplace behavior.

begin;

alter table public.listing_drafts
  add column version integer not null default 1,
  add column item_specifics_json jsonb not null default '{}'::jsonb,
  add column category_suggestion text,
  add constraint listing_drafts_version_check check (version > 0),
  add constraint listing_drafts_item_specifics_object_check check (
    jsonb_typeof(item_specifics_json) = 'object'
  ),
  add constraint listing_drafts_category_suggestion_check check (
    category_suggestion is null
    or char_length(btrim(category_suggestion)) between 1 and 200
  );

create or replace function public.set_listing_draft_version()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    new.version = 1;
  else
    new.version = old.version + 1;
  end if;

  return new;
end;
$$;

revoke all on function public.set_listing_draft_version() from public;

create trigger listing_drafts_set_version
before insert or update on public.listing_drafts
for each row execute function public.set_listing_draft_version();

grant update (
  item_specifics_json,
  category_suggestion
) on table public.listing_drafts to authenticated;

comment on column public.listing_drafts.version is
  'Monotonic revision number assigned by the database, starting at 1.';
comment on column public.listing_drafts.item_specifics_json is
  'Marketplace-oriented item specifics stored as a JSON object.';
comment on column public.listing_drafts.category_suggestion is
  'Non-published marketplace category suggestion for user review.';

commit;
