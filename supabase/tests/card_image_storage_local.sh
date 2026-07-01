#!/bin/bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

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

local_uuid() {
  uuidgen | tr '[:upper:]' '[:lower:]'
}

create_metadata() {
  local name="$1"
  local image_id="$2"
  local storage_path="$3"

  run_request "$name" \
    "$api_url/rest/v1/card_images" \
    -X POST \
    -H "apikey: $publishable_key" \
    -H "Authorization: Bearer $token_a" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d "$(
      jq -nc \
        --arg id "$image_id" \
        --arg card_id "$card_a_id" \
        --arg storage_path "$storage_path" \
        --argjson byte_size "$image_size" \
        --arg sha256 "$image_sha256" \
        '{
          id: $id,
          card_id: $card_id,
          storage_path: $storage_path,
          mime_type: "image/png",
          byte_size: $byte_size,
          sha256: $sha256,
          status: "pending"
        }'
    )"
  expect_status 201 "$name"
}

delete_metadata() {
  local name="$1"
  local image_id="$2"

  run_request "$name" \
    "$api_url/rest/v1/card_images?id=eq.$image_id" \
    -X DELETE \
    -H "apikey: $publishable_key" \
    -H "Authorization: Bearer $token_a" \
    -H "Prefer: return=representation"
  expect_status 200 "$name"
}

command -v supabase >/dev/null 2>&1 || fail "Supabase CLI is not installed"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
command -v jq >/dev/null 2>&1 || fail "jq is not installed"
command -v curl >/dev/null 2>&1 || fail "curl is not installed"
command -v uuidgen >/dev/null 2>&1 || fail "uuidgen is not installed"

status_json="$(supabase status -o json 2>/dev/null)" ||
  fail "local Supabase is not running"

api_url="$(jq -r '.API_URL // empty' <<<"$status_json")"
publishable_key="$(jq -r '.PUBLISHABLE_KEY // .ANON_KEY // empty' <<<"$status_json")"

[[ "$api_url" == http://127.0.0.1:* || "$api_url" == http://localhost:* ]] ||
  fail "refusing to test non-local API URL"
[[ -n "$publishable_key" ]] || fail "local publishable key is unavailable"

bucket_row="$(
  docker exec supabase_db_BulkMint \
    psql -U postgres -d postgres -X -A -t -F '|' \
    -c "select public, file_size_limit, array_to_string(allowed_mime_types, ',')
        from storage.buckets
        where id = 'card-images';"
)"
[[ "$bucket_row" == "f|10485760|image/jpeg,image/png,image/webp" ]] ||
  fail "card-images bucket configuration is incorrect: $bucket_row"
echo "PASS: card-images bucket is private with 10 MiB and expected MIME types"

run_id="$(date +%s)-$$"
email_a="storage-owner-a-$run_id@example.test"
email_b="storage-owner-b-$run_id@example.test"
password_a="BulkMint-storage-A-$run_id!"
password_b="BulkMint-storage-B-$run_id!"

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

token_a="$(jq -r '.access_token // empty' "$tmp_dir/signup_a.response")"
token_b="$(jq -r '.access_token // empty' "$tmp_dir/signup_b.response")"
user_a_id="$(jq -r '.user.id // empty' "$tmp_dir/signup_a.response")"
user_b_id="$(jq -r '.user.id // empty' "$tmp_dir/signup_b.response")"

[[ -n "$token_a" && -n "$user_a_id" ]] || fail "user A session was not created"
[[ -n "$token_b" && -n "$user_b_id" ]] || fail "user B session was not created"
echo "PASS: two local authenticated users created"

run_request create_card \
  "$api_url/rest/v1/cards" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"card_name":"Storage policy test card","status":"draft"}'
expect_status 201 "owner card insert"

card_a_id="$(jq -r '.[0].id // empty' "$tmp_dir/create_card.response")"
[[ -n "$card_a_id" ]] || fail "owner card insert returned no ID"

base64 --decode >"$tmp_dir/card.png" <<'IMAGE'
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=
IMAGE
image_size="$(stat -f '%z' "$tmp_dir/card.png")"
image_sha256="$(shasum -a 256 "$tmp_dir/card.png" | awk '{print $1}')"

missing_metadata_image_id="$(local_uuid)"
missing_metadata_path="$user_a_id/$card_a_id/$missing_metadata_image_id.png"
run_request missing_metadata_upload \
  "$api_url/storage/v1/object/card-images/$missing_metadata_path" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: image/png" \
  --data-binary "@$tmp_dir/card.png"
expect_denied "upload without pending metadata"
echo "PASS: owner upload without pending metadata denied"

image_id="$(local_uuid)"
canonical_path="$user_a_id/$card_a_id/$image_id.png"
create_metadata metadata_create "$image_id" "$canonical_path"

metadata_owner="$(jq -r '.[0].owner_id // empty' "$tmp_dir/metadata_create.response")"
[[ "$metadata_owner" == "$user_a_id" ]] ||
  fail "metadata owner was not assigned from user A"
echo "PASS: owner can create own pending metadata"

run_request owner_metadata_read \
  "$api_url/rest/v1/card_images?id=eq.$image_id&select=id,owner_id,status,storage_path" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_status 200 "owner metadata read"
[[ "$(jq 'length' "$tmp_dir/owner_metadata_read.response")" == "1" ]] ||
  fail "owner could not read own metadata"

run_request anonymous_metadata_read \
  "$api_url/rest/v1/card_images?id=eq.$image_id&select=id" \
  -H "apikey: $publishable_key"
expect_denied "anonymous metadata read"

run_request cross_metadata_read \
  "$api_url/rest/v1/card_images?id=eq.$image_id&select=id" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b"
expect_status 200 "cross-user metadata read"
[[ "$(jq 'length' "$tmp_dir/cross_metadata_read.response")" == "0" ]] ||
  fail "user B could read user A metadata"
echo "PASS: metadata is owner-readable and hidden from anonymous/cross-user access"

wrong_owner_image_id="$(local_uuid)"
wrong_owner_path="$user_b_id/$card_a_id/$wrong_owner_image_id.png"
create_metadata wrong_owner_metadata "$wrong_owner_image_id" "$wrong_owner_path"
run_request wrong_owner_upload \
  "$api_url/storage/v1/object/card-images/$wrong_owner_path" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: image/png" \
  --data-binary "@$tmp_dir/card.png"
expect_denied "wrong-owner path upload"
delete_metadata wrong_owner_metadata_cleanup "$wrong_owner_image_id"

wrong_card_image_id="$(local_uuid)"
wrong_card_id="$(local_uuid)"
wrong_card_path="$user_a_id/$wrong_card_id/$wrong_card_image_id.png"
create_metadata wrong_card_metadata "$wrong_card_image_id" "$wrong_card_path"
run_request wrong_card_upload \
  "$api_url/storage/v1/object/card-images/$wrong_card_path" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: image/png" \
  --data-binary "@$tmp_dir/card.png"
expect_denied "wrong-card path upload"
delete_metadata wrong_card_metadata_cleanup "$wrong_card_image_id"

wrong_filename_image_id="$(local_uuid)"
wrong_filename_id="$(local_uuid)"
wrong_filename_path="$user_a_id/$card_a_id/$wrong_filename_id.png"
create_metadata wrong_filename_metadata "$wrong_filename_image_id" "$wrong_filename_path"
run_request wrong_filename_upload \
  "$api_url/storage/v1/object/card-images/$wrong_filename_path" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: image/png" \
  --data-binary "@$tmp_dir/card.png"
expect_denied "wrong-image-id path upload"
delete_metadata wrong_filename_metadata_cleanup "$wrong_filename_image_id"
echo "PASS: owner, card, and image path components are enforced"

run_request anonymous_upload \
  "$api_url/storage/v1/object/card-images/$canonical_path" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Content-Type: image/png" \
  --data-binary "@$tmp_dir/card.png"
expect_denied "anonymous upload"
echo "PASS: anonymous upload denied"

run_request owner_upload \
  "$api_url/storage/v1/object/card-images/$canonical_path" \
  -X POST \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: image/png" \
  --data-binary "@$tmp_dir/card.png"
expect_status 200 "owner upload"
echo "PASS: owner upload allowed with matching pending metadata"

run_request pending_read \
  "$api_url/storage/v1/object/authenticated/card-images/$canonical_path" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_denied "pending object read"

run_request activate_metadata \
  "$api_url/rest/v1/card_images?id=eq.$image_id" \
  -X PATCH \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"status":"active"}'
expect_status 200 "metadata activation"
[[ "$(jq -r '.[0].status // empty' "$tmp_dir/activate_metadata.response")" == "active" ]] ||
  fail "metadata did not become active"
echo "PASS: pending object remains unreadable until metadata activation"

run_request anonymous_read \
  "$api_url/storage/v1/object/authenticated/card-images/$canonical_path" \
  -H "apikey: $publishable_key"
expect_denied "anonymous read"

run_request owner_read \
  "$api_url/storage/v1/object/authenticated/card-images/$canonical_path" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_status 200 "owner read"
cmp "$tmp_dir/card.png" "$tmp_dir/owner_read.response" ||
  fail "owner download bytes do not match upload"

run_request cross_read \
  "$api_url/storage/v1/object/authenticated/card-images/$canonical_path" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b"
expect_denied "cross-user read"
echo "PASS: anonymous/cross-user read denied and owner read allowed"

run_request cross_delete \
  "$api_url/storage/v1/object/card-images/$canonical_path" \
  -X DELETE \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_b"
expect_denied "cross-user delete"

run_request owner_delete \
  "$api_url/storage/v1/object/card-images/$canonical_path" \
  -X DELETE \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_status 200 "owner delete"
echo "PASS: cross-user delete denied and owner delete allowed"

delete_metadata owner_metadata_cleanup "$image_id"
[[ "$(jq 'length' "$tmp_dir/owner_metadata_cleanup.response")" == "1" ]] ||
  fail "owner metadata cleanup deleted no row"

run_request verify_metadata_removed \
  "$api_url/rest/v1/card_images?id=eq.$image_id&select=id" \
  -H "apikey: $publishable_key" \
  -H "Authorization: Bearer $token_a"
expect_status 200 "metadata cleanup verification"
[[ "$(jq 'length' "$tmp_dir/verify_metadata_removed.response")" == "0" ]] ||
  fail "metadata row remains after cleanup"

object_count="$(
  docker exec supabase_db_BulkMint \
    psql -U postgres -d postgres -X -A -t \
    -c "select count(*) from storage.objects
        where bucket_id = 'card-images' and name = '$canonical_path';" |
    tr -d '[:space:]'
)"
[[ "$object_count" == "0" ]] || fail "Storage object remains after cleanup"
echo "PASS: cleanup removed metadata and object with no orphan"

echo "All local card image Storage policy tests passed."
