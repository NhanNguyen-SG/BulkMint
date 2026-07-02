#!/bin/bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
user_a_id=""
user_b_id=""

cleanup() {
  if [[ -n "${secret_key:-}" && -n "${api_url:-}" ]]; then
    for user_id in "$user_a_id" "$user_b_id"; do
      if [[ -n "$user_id" ]]; then
        curl --silent --show-error \
          --request DELETE \
          "$api_url/auth/v1/admin/users/$user_id" \
          --header "apikey: $secret_key" \
          --header "Authorization: Bearer $secret_key" \
          >/dev/null 2>&1 || true
      fi
    done
  fi
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

run_request() {
  local name="$1"
  shift
  CURRENT_RESPONSE="$name"
  HTTP_STATUS="$(
    curl --silent --show-error \
      --output "$tmp_dir/$name.response" \
      --write-out '%{http_code}' \
      "$@"
  )"
}

expect_status() {
  local expected="$1"
  local description="$2"
  if [[ "$HTTP_STATUS" != "$expected" ]]; then
    echo "Response body:" >&2
    cat "$tmp_dir/$CURRENT_RESPONSE.response" >&2
    fail "$description returned HTTP $HTTP_STATUS; expected $expected"
  fi
}

expect_denied() {
  local description="$1"
  if [[ "$HTTP_STATUS" =~ ^2 ]]; then
    echo "Response body:" >&2
    cat "$tmp_dir/$CURRENT_RESPONSE.response" >&2
    fail "$description unexpectedly returned HTTP $HTTP_STATUS"
  fi
}

expect_empty_array() {
  local description="$1"
  expect_status 200 "$description"
  if [[ "$(jq 'length' "$tmp_dir/$CURRENT_RESPONSE.response")" != "0" ]]; then
    fail "$description exposed or modified a cross-owner row"
  fi
}

command -v supabase >/dev/null 2>&1 || fail "Supabase CLI is not installed"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
command -v jq >/dev/null 2>&1 || fail "jq is not installed"
command -v curl >/dev/null 2>&1 || fail "curl is not installed"

status_json="$(supabase status -o json 2>/dev/null)" ||
  fail "local Supabase is not running"

api_url="$(jq -r '.API_URL // empty' <<<"$status_json")"
publishable_key="$(jq -r '.PUBLISHABLE_KEY // .ANON_KEY // empty' <<<"$status_json")"
secret_key="$(jq -r '.SECRET_KEY // .SERVICE_ROLE_KEY // empty' <<<"$status_json")"

[[ "$api_url" == http://127.0.0.1:* || "$api_url" == http://localhost:* ]] ||
  fail "refusing to test non-local API URL"
[[ -n "$publishable_key" ]] || fail "local publishable key is unavailable"
[[ -n "$secret_key" ]] || fail "local secret key is unavailable"

table_rows="$(
  docker exec supabase_db_BulkMint \
    psql -U postgres -d postgres -X -A -t -F '|' \
    -c "select c.relname, c.relrowsecurity
        from pg_class as c
        join pg_namespace as n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind = 'r'
          and c.relname in (
            'listing_drafts',
            'pricing_sources',
            'pricing_observations',
            'pricing_observation_inputs'
          )
        order by c.relname;"
)"

expected_tables="$(
  printf '%s\n' \
    'listing_drafts|t' \
    'pricing_observation_inputs|t' \
    'pricing_observations|t' \
    'pricing_sources|t'
)"

[[ "$table_rows" == "$expected_tables" ]] ||
  fail "V0.3 tables are missing or do not have RLS enabled"
echo "PASS: V0.3 tables exist with RLS enabled"

listing_api_columns="$(
  docker exec supabase_db_BulkMint \
    psql -U postgres -d postgres -X -A -t \
    -c "select column_name
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'listing_drafts'
          and column_name in (
            'version',
            'item_specifics_json',
            'category_suggestion'
          )
        order by column_name;"
)"

expected_listing_api_columns="$(
  printf '%s\n' \
    'category_suggestion' \
    'item_specifics_json' \
    'version'
)"

[[ "$listing_api_columns" == "$expected_listing_api_columns" ]] ||
  fail "listing_drafts is missing V0.3 API contract columns"
echo "PASS: listing draft API contract columns exist"

for table in \
  listing_drafts \
  pricing_sources \
  pricing_observations \
  pricing_observation_inputs; do
  run_request "anonymous_$table" \
    "$api_url/rest/v1/$table?select=*" \
    --header "apikey: $publishable_key"
  expect_denied "anonymous $table read"
done
echo "PASS: anonymous access denied for all V0.3 tables"

run_id="$(date +%s)-$$"
email_a="listing-owner-a-$run_id@example.test"
email_b="listing-owner-b-$run_id@example.test"
password_a="BulkMint-listing-A-$run_id!"
password_b="BulkMint-listing-B-$run_id!"
observed_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

run_request signup_a \
  "$api_url/auth/v1/signup" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Content-Type: application/json" \
  --data "{\"email\":\"$email_a\",\"password\":\"$password_a\"}"
expect_status 200 "user A signup"

run_request signup_b \
  "$api_url/auth/v1/signup" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Content-Type: application/json" \
  --data "{\"email\":\"$email_b\",\"password\":\"$password_b\"}"
expect_status 200 "user B signup"

token_a="$(jq -r '.access_token // empty' "$tmp_dir/signup_a.response")"
token_b="$(jq -r '.access_token // empty' "$tmp_dir/signup_b.response")"
user_a_id="$(jq -r '.user.id // empty' "$tmp_dir/signup_a.response")"
user_b_id="$(jq -r '.user.id // empty' "$tmp_dir/signup_b.response")"

[[ -n "$token_a" && -n "$user_a_id" ]] || fail "user A session was not created"
[[ -n "$token_b" && -n "$user_b_id" ]] || fail "user B session was not created"
echo "PASS: two local authenticated users created"

run_request card_a \
  "$api_url/rest/v1/cards" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data '{"card_name":"Listing owner A test","status":"draft"}'
expect_status 201 "user A card insert"

run_request card_b \
  "$api_url/rest/v1/cards" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data '{"card_name":"Listing owner B test","status":"draft"}'
expect_status 201 "user B card insert"

card_a_id="$(jq -r '.[0].id // empty' "$tmp_dir/card_a.response")"
card_b_id="$(jq -r '.[0].id // empty' "$tmp_dir/card_b.response")"
[[ -n "$card_a_id" && -n "$card_b_id" ]] || fail "test cards were not created"

run_request manual_source_a \
  "$api_url/rest/v1/pricing_sources" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "{\"source_type\":\"manual\",\"source_name\":\"Owner A override $run_id\"}"
expect_status 201 "user A manual pricing source insert"

run_request manual_source_b \
  "$api_url/rest/v1/pricing_sources" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "{\"source_type\":\"manual\",\"source_name\":\"Owner B override $run_id\"}"
expect_status 201 "user B manual pricing source insert"

source_a_id="$(jq -r '.[0].id // empty' "$tmp_dir/manual_source_a.response")"
source_b_id="$(jq -r '.[0].id // empty' "$tmp_dir/manual_source_b.response")"
[[ -n "$source_a_id" && -n "$source_b_id" ]] ||
  fail "manual pricing sources were not created"

run_request observation_a \
  "$api_url/rest/v1/pricing_observations" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      --arg source_id "$source_a_id" \
      --arg observed_at "$observed_at" \
      '{
        card_id: $card_id,
        pricing_source_id: $source_id,
        price_kind: "manual_override",
        observed_price: 12.34,
        currency: "USD",
        condition: "Near Mint",
        observed_at: $observed_at,
        notes: "Local contract validation"
      }'
  )"
expect_status 201 "user A pricing observation insert"

observation_a_id="$(
  jq -r '.[0].id // empty' "$tmp_dir/observation_a.response"
)"
observation_a_owner="$(
  jq -r '.[0].owner_id // empty' "$tmp_dir/observation_a.response"
)"
[[ -n "$observation_a_id" ]] || fail "pricing observation returned no ID"
[[ "$observation_a_owner" == "$user_a_id" ]] ||
  fail "pricing observation did not inherit user A ownership"
echo "PASS: owner can create price evidence for own card"

run_request cross_observation_read \
  "$api_url/rest/v1/pricing_observations?id=eq.$observation_a_id&select=id" \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b"
expect_empty_array "cross-user pricing observation read"

run_request cross_card_observation \
  "$api_url/rest/v1/pricing_observations" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b" \
  --header "Content-Type: application/json" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      --arg source_id "$source_b_id" \
      --arg observed_at "$observed_at" \
      '{
        card_id: $card_id,
        pricing_source_id: $source_id,
        price_kind: "manual_override",
        observed_price: 99.99,
        currency: "USD",
        observed_at: $observed_at
      }'
  )"
expect_denied "cross-user card pricing observation insert"
echo "PASS: price observations are owner-scoped through card ownership"

run_request invalid_currency \
  "$api_url/rest/v1/pricing_observations" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      --arg source_id "$source_a_id" \
      --arg observed_at "$observed_at" \
      '{
        card_id: $card_id,
        pricing_source_id: $source_id,
        price_kind: "manual_override",
        observed_price: 12.34,
        currency: "usd",
        observed_at: $observed_at
      }'
  )"
expect_denied "invalid observation currency"
echo "PASS: invalid currency rejected"

run_request draft_a \
  "$api_url/rest/v1/listing_drafts" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      --arg observation_id "$observation_a_id" \
      '{
        card_id: $card_id,
        marketplace_target: "ebay",
        status: "draft",
        title: "Local listing draft",
        description: "Local-only listing contract validation.",
        item_specifics_json: {
          game: "One Piece Card Game",
          language: "English"
        },
        category_suggestion: "Collectible Card Games",
        price_amount: 12.34,
        currency: "USD",
        quantity: 1,
        selected_pricing_observation_id: $observation_id,
        version: 99
      }'
  )"
expect_status 201 "owner listing draft insert"

draft_a_id="$(jq -r '.[0].id // empty' "$tmp_dir/draft_a.response")"
draft_a_owner="$(jq -r '.[0].owner_id // empty' "$tmp_dir/draft_a.response")"
[[ -n "$draft_a_id" ]] || fail "listing draft returned no ID"
[[ "$draft_a_owner" == "$user_a_id" ]] ||
  fail "listing draft did not inherit user A ownership"
[[ "$(jq -r '.[0].version' "$tmp_dir/draft_a.response")" == "1" ]] ||
  fail "database did not assign listing draft version 1"
[[ "$(jq -r '.[0].item_specifics_json.game // empty' "$tmp_dir/draft_a.response")" == "One Piece Card Game" ]] ||
  fail "listing draft item specifics were not persisted"
[[ "$(jq -r '.[0].category_suggestion // empty' "$tmp_dir/draft_a.response")" == "Collectible Card Games" ]] ||
  fail "listing draft category suggestion was not persisted"
[[ "$(jq -r '.[0].generation_model // "null"' "$tmp_dir/draft_a.response")" == "null" ]] ||
  fail "placeholder draft unexpectedly persisted an AI model"
[[ "$(jq -r '.[0].prompt_version // "null"' "$tmp_dir/draft_a.response")" == "null" ]] ||
  fail "placeholder draft unexpectedly persisted a prompt version"
echo "PASS: placeholder fields persist with version 1 and null AI metadata"

run_request owner_draft_read \
  "$api_url/rest/v1/listing_drafts?id=eq.$draft_a_id&select=id,owner_id,status,version" \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a"
expect_status 200 "owner listing draft read"
[[ "$(jq 'length' "$tmp_dir/owner_draft_read.response")" == "1" ]] ||
  fail "owner could not read own listing draft"

run_request owner_draft_update \
  "$api_url/rest/v1/listing_drafts?id=eq.$draft_a_id" \
  --request PATCH \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "$(
    jq -nc \
      --arg ready_at "$observed_at" \
      '{
        title: "Reviewed local listing draft",
        status: "ready",
        ready_at: $ready_at,
        item_specifics_json: {
          game: "One Piece Card Game",
          language: "English",
          condition: "Near Mint"
        },
        category_suggestion: "CCG Individual Cards"
      }'
  )"
expect_status 200 "owner listing draft update"
[[ "$(jq -r '.[0].status // empty' "$tmp_dir/owner_draft_update.response")" == "ready" ]] ||
  fail "owner listing draft did not become ready"
[[ "$(jq -r '.[0].version' "$tmp_dir/owner_draft_update.response")" == "2" ]] ||
  fail "listing draft version did not increment to 2"
[[ "$(jq -r '.[0].item_specifics_json.condition // empty' "$tmp_dir/owner_draft_update.response")" == "Near Mint" ]] ||
  fail "listing draft item specifics update did not persist"
echo "PASS: owner can create, read, and update own listing draft"

run_request cross_draft_read \
  "$api_url/rest/v1/listing_drafts?id=eq.$draft_a_id&select=id" \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b"
expect_empty_array "cross-user listing draft read"

run_request cross_draft_update \
  "$api_url/rest/v1/listing_drafts?id=eq.$draft_a_id" \
  --request PATCH \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data '{"title":"Cross-user update"}'
expect_empty_array "cross-user listing draft update"
echo "PASS: cross-user listing draft access denied"

run_request cross_card_draft \
  "$api_url/rest/v1/listing_drafts" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --data "$(
    jq -nc \
      --arg card_id "$card_b_id" \
      '{
        card_id: $card_id,
        marketplace_target: "ebay",
        status: "draft",
        title: "Forbidden cross-owner draft",
        description: "Must not be inserted"
      }'
  )"
expect_denied "draft attached to another user's card"
echo "PASS: draft cannot attach to another user's card"

run_request invalid_status \
  "$api_url/rest/v1/listing_drafts" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      '{
        card_id: $card_id,
        marketplace_target: "ebay",
        status: "published",
        title: "Invalid published draft",
        description: "Must not be inserted"
      }'
  )"
expect_denied "invalid listing draft status"
echo "PASS: invalid listing draft status rejected"

run_request invalid_item_specifics \
  "$api_url/rest/v1/listing_drafts" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      '{
        card_id: $card_id,
        marketplace_target: "ebay",
        status: "draft",
        title: "Invalid item specifics",
        description: "Must not be inserted",
        item_specifics_json: []
      }'
  )"
expect_denied "non-object listing item specifics"
echo "PASS: non-object item specifics rejected"

run_request immutable_generation_update \
  "$api_url/rest/v1/listing_drafts?id=eq.$draft_a_id" \
  --request PATCH \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --data '{"generation_model":"forged-model"}'
expect_denied "immutable generation metadata update"
echo "PASS: generation provenance columns are immutable after insert"

run_request immutable_version_update \
  "$api_url/rest/v1/listing_drafts?id=eq.$draft_a_id" \
  --request PATCH \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --data '{"version":99}'
expect_denied "client-controlled listing draft version update"
echo "PASS: listing draft version is database-managed"

run_request derived_source \
  "$api_url/rest/v1/pricing_sources" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "{\"source_type\":\"derived\",\"source_name\":\"Local method $run_id\"}"
expect_status 201 "derived pricing source insert"
derived_source_id="$(jq -r '.[0].id // empty' "$tmp_dir/derived_source.response")"

run_request derived_observation \
  "$api_url/rest/v1/pricing_observations" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      --arg source_id "$derived_source_id" \
      --arg observed_at "$observed_at" \
      '{
        card_id: $card_id,
        pricing_source_id: $source_id,
        price_kind: "estimate",
        observed_price: 12.34,
        currency: "USD",
        observed_at: $observed_at,
        confidence: 0.75,
        methodology: "weighted_mean",
        method_version: "v1"
      }'
  )"
expect_status 201 "derived pricing observation insert"
derived_observation_id="$(
  jq -r '.[0].id // empty' "$tmp_dir/derived_observation.response"
)"

run_request derived_input \
  "$api_url/rest/v1/pricing_observation_inputs" \
  --request POST \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "$(
    jq -nc \
      --arg card_id "$card_a_id" \
      --arg derived_id "$derived_observation_id" \
      --arg input_id "$observation_a_id" \
      '{
        card_id: $card_id,
        derived_observation_id: $derived_id,
        input_observation_id: $input_id,
        weight: 1
      }'
  )"
expect_status 201 "derived pricing input insert"
echo "PASS: derived pricing input linkage accepted for same owner and card"

run_request service_audit_insert \
  "$api_url/rest/v1/audit_events" \
  --request POST \
  --header "apikey: $secret_key" \
  --header "Content-Type: application/json" \
  --header "Prefer: return=representation" \
  --data "$(
    jq -nc \
      --arg owner_id "$user_a_id" \
      --arg draft_id "$draft_a_id" \
      '{
        owner_id: $owner_id,
        action: "listing_draft.ready",
        entity_type: "listing_draft",
        entity_id: $draft_id,
        metadata: {validation: "local"}
      }'
  )"
expect_status 201 "listing draft audit event insert"
audit_id="$(jq -r '.[0].id // empty' "$tmp_dir/service_audit_insert.response")"
[[ -n "$audit_id" ]] || fail "audit event returned no ID"

run_request owner_audit_read \
  "$api_url/rest/v1/audit_events?id=eq.$audit_id&select=id,entity_type,entity_id" \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_a"
expect_status 200 "owner listing draft audit read"
[[ "$(jq -r '.[0].entity_id // empty' "$tmp_dir/owner_audit_read.response")" == "$draft_a_id" ]] ||
  fail "audit event does not reference the listing draft"

run_request cross_audit_read \
  "$api_url/rest/v1/audit_events?id=eq.$audit_id&select=id" \
  --header "apikey: $publishable_key" \
  --header "Authorization: Bearer $token_b"
expect_empty_array "cross-user listing draft audit read"
echo "PASS: audit event links to draft and remains owner-scoped"

echo "All local listing and pricing contract tests passed."
