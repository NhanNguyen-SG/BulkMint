#!/bin/bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

request() {
  local output_name="$1"
  shift
  HTTP_STATUS="$(
    curl --silent --show-error \
      --output "$tmp_dir/$output_name.json" \
      --write-out '%{http_code}' \
      "$@"
  )"
}

expect_status() {
  local expected="$1"
  local description="$2"
  if [[ "$HTTP_STATUS" != "$expected" ]]; then
    echo "Response body:" >&2
    jq . "$tmp_dir/$CURRENT_RESPONSE.json" >&2 2>/dev/null || true
    fail "$description returned HTTP $HTTP_STATUS; expected $expected"
  fi
}

expect_denied() {
  local description="$1"
  if [[ "$HTTP_STATUS" =~ ^2 ]]; then
    echo "Response body:" >&2
    jq . "$tmp_dir/$CURRENT_RESPONSE.json" >&2 2>/dev/null || true
    fail "$description unexpectedly returned HTTP $HTTP_STATUS"
  fi
}

run_request() {
  CURRENT_RESPONSE="$1"
  shift
  request "$CURRENT_RESPONSE" "$@"
}

command -v supabase >/dev/null 2>&1 || fail "Supabase CLI is not installed"
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

run_id="$(date +%s)-$$"
email_a="bulkmint-owner-a-$run_id@example.test"
email_b="bulkmint-owner-b-$run_id@example.test"
password_a="BulkMint-local-A-$run_id!"
password_b="BulkMint-local-B-$run_id!"

run_request signup_a \
  "$api_url/auth/v1/signup" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$email_a\",\"password\":\"$password_a\"}"
expect_status 200 "user A signup"

run_request signup_b \
  "$api_url/auth/v1/signup" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$email_b\",\"password\":\"$password_b\"}"
expect_status 200 "user B signup"

token_a="$(jq -r '.access_token // empty' "$tmp_dir/signup_a.json")"
token_b="$(jq -r '.access_token // empty' "$tmp_dir/signup_b.json")"
user_a_id="$(jq -r '.user.id // empty' "$tmp_dir/signup_a.json")"
user_b_id="$(jq -r '.user.id // empty' "$tmp_dir/signup_b.json")"

[[ -n "$token_a" && -n "$user_a_id" ]] || fail "user A session was not created"
[[ -n "$token_b" && -n "$user_b_id" ]] || fail "user B session was not created"

run_request anonymous_cards \
  "$api_url/rest/v1/cards?select=id" \
  -H "apikey: $publishable_key"
expect_denied "anonymous cards read"
echo "PASS: anonymous access denied"

run_request owner_insert \
  "$api_url/rest/v1/cards" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"card_name":"Local RLS owner test","status":"draft"}'
expect_status 201 "owner insert"

card_a_id="$(jq -r '.[0].id // empty' "$tmp_dir/owner_insert.json")"
card_a_owner="$(jq -r '.[0].owner_id // empty' "$tmp_dir/owner_insert.json")"
[[ -n "$card_a_id" ]] || fail "owner insert did not return a card ID"
[[ "$card_a_owner" == "$user_a_id" ]] || fail "owner_id did not default to user A"
echo "PASS: owner insert assigns authenticated owner"

run_request owner_read \
  "$api_url/rest/v1/cards?id=eq.$card_a_id&select=id,owner_id,status" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_status 200 "owner read"
[[ "$(jq 'length' "$tmp_dir/owner_read.json")" == "1" ]] ||
  fail "owner could not read their card"
echo "PASS: owner can read own row"

run_request cross_read \
  "$api_url/rest/v1/cards?id=eq.$card_a_id&select=*" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b"
expect_status 200 "cross-user read"
[[ "$(jq 'length' "$tmp_dir/cross_read.json")" == "0" ]] ||
  fail "user B could read user A's card"
echo "PASS: cross-user read hidden"

run_request cross_update \
  "$api_url/rest/v1/cards?id=eq.$card_a_id" \
  -X PATCH \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"status":"archived"}'
expect_status 200 "cross-user update"
[[ "$(jq 'length' "$tmp_dir/cross_update.json")" == "0" ]] ||
  fail "user B updated user A's card"
echo "PASS: cross-user update blocked"

run_request forged_owner_insert \
  "$api_url/rest/v1/cards" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b" \
  -H "Content-Type: application/json" \
  -d "{\"owner_id\":\"$user_a_id\",\"card_name\":\"Forbidden owner test\"}"
expect_denied "forged owner insert"
echo "PASS: forged ownership blocked"

run_request owner_update \
  "$api_url/rest/v1/cards?id=eq.$card_a_id" \
  -X PATCH \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"status":"active"}'
expect_status 200 "owner update"
[[ "$(jq -r '.[0].status // empty' "$tmp_dir/owner_update.json")" == "active" ]] ||
  fail "owner update did not persist"
echo "PASS: owner can update own row"

run_request service_read \
  "$api_url/rest/v1/cards?id=eq.$card_a_id&select=id,owner_id,status" \
  -H "apikey: $secret_key"
expect_status 200 "service-role read"
[[ "$(jq 'length' "$tmp_dir/service_read.json")" == "1" ]] ||
  fail "service role could not bypass RLS"
echo "PASS: service role bypasses RLS"

run_request service_audit_insert \
  "$api_url/rest/v1/audit_events" \
  -X POST \
  -H "apikey: $secret_key" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d "{\"owner_id\":\"$user_a_id\",\"action\":\"rls_test\",\"entity_type\":\"card\",\"entity_id\":\"$card_a_id\"}"
expect_status 201 "service-role audit insert"
audit_id="$(jq -r '.[0].id // empty' "$tmp_dir/service_audit_insert.json")"
[[ -n "$audit_id" ]] || fail "service role did not create an audit event"

run_request owner_audit_read \
  "$api_url/rest/v1/audit_events?id=eq.$audit_id&select=id" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_status 200 "owner audit read"
[[ "$(jq 'length' "$tmp_dir/owner_audit_read.json")" == "1" ]] ||
  fail "owner could not read their audit event"

run_request other_audit_read \
  "$api_url/rest/v1/audit_events?id=eq.$audit_id&select=id" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b"
expect_status 200 "cross-user audit read"
[[ "$(jq 'length' "$tmp_dir/other_audit_read.json")" == "0" ]] ||
  fail "user B could read user A's audit event"
echo "PASS: audit events are owner-readable and service-writeable"

run_request owner_delete \
  "$api_url/rest/v1/cards?id=eq.$card_a_id" \
  -X DELETE \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Prefer: return=representation"
expect_status 200 "owner delete"
[[ "$(jq 'length' "$tmp_dir/owner_delete.json")" == "1" ]] ||
  fail "owner could not delete their card"
echo "PASS: owner can delete own row"

echo "All local RLS tests passed."
