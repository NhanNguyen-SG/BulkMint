begin;

alter table public.cards
  add column detected_game text not null default 'Unknown';

alter table public.cards
  add constraint cards_detected_game_check
  check (
    detected_game in (
      'Pokemon',
      'One Piece',
      'Magic: The Gathering',
      'Yu-Gi-Oh!',
      'Disney Lorcana',
      'Digimon',
      'Dragon Ball Super',
      'Unknown'
    )
  );

create index cards_owner_detected_game_idx
  on public.cards (owner_id, detected_game);

comment on column public.cards.detected_game is
  'Canonical trading card game detected during analysis; legacy rows default to Unknown.';

commit;
