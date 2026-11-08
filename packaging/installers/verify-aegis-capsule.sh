#!/usr/bin/env bash
# AG-D011: read-only outer capsule publisher seal verification, NOT INSTALL.
# Only the existing Platform publisher Ed25519 key may sign this domain.
# The shell verifier itself must be independently trusted before invocation.
# No project Python, Cargo, Git, Core, Internet or privilege is required.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
umask 077

if (($# != 10)) ||
   [[ "$1" != '--capsule' || "$3" != '--signature' ||
      "$5" != '--publisher-key' || "$7" != '--publisher-sha256' ||
      "$9" != '--publisher-signer' ]]; then
  printf '%s\n' 'Usage: verify-aegis-capsule.sh --capsule ZIP --signature RAW64 --publisher-key PEM --publisher-sha256 HEX --publisher-signer ID' >&2
  exit 2
fi
capsule="$2"
signature="$4"
key="$6"
key_fingerprint="$8"
signer="${10}"
if [[ ! "$key_fingerprint" =~ ^[0-9a-f]{64}$ ||
      ! "$signer" =~ ^[A-Za-z0-9_.-]{1,128}$ ]]; then
  printf '%s\n' 'Independent publisher fingerprint/signer required' >&2
  exit 2
fi
for command in openssl sha256sum realpath stat mktemp chmod rm unzip wc sort cmp tail; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf '%s\n' 'Required stock verification utility missing; refusing publisher trust' >&2
    exit 3
  fi
done
verify_local_file() {
  local name="$1" limit="$2" original resolved size
  [[ -f "$name" && ! -L "$name" ]] || return 1
  original="$(realpath -ms -- "$name")" || return 1
  resolved="$(realpath -e -- "$name")" || return 1
  [[ "$original" == "$resolved" ]] || return 1
  size="$(stat -c %s -- "$resolved")" || return 1
  [[ "$size" =~ ^[0-9]+$ ]] || return 1
  ((size >= 1 && size <= limit)) || return 1
  printf '%s\n' "$resolved"
}
capsule_path="$(verify_local_file "$capsule" 1075838976)" || {
  printf '%s\n' 'Capsule missing, redirected or oversized' >&2; exit 3;
}
signature_path="$(verify_local_file "$signature" 64)" || {
  printf '%s\n' 'Signature missing, redirected or oversized' >&2; exit 3;
}
if [[ "$(stat -c %s -- "$signature_path")" != 64 ]]; then
  printf '%s\n' 'Detached Ed25519 signature must be exactly 64 bytes' >&2
  exit 3
fi
key_path="$(verify_local_file "$key" 16384)" || {
  printf '%s\n' 'Publisher key missing, redirected or oversized' >&2; exit 3;
}
if [[ "${capsule_path%/*}" == "${key_path%/*}" ]]; then
  printf '%s\n' 'Publisher public key must be provisioned outside capsule media directory' >&2
  exit 3
fi
observed_key="$(sha256sum -- "$key_path")" || exit 3
observed_key="${observed_key:0:64}"
if [[ "$observed_key" != "$key_fingerprint" ]]; then
  printf '%s\n' 'Publisher root differs from independent pin' >&2
  exit 3
fi
algorithms="$(openssl list -public-key-algorithms 2>/dev/null || true)"
if [[ "${algorithms,,}" != *ed25519* ]]; then
  printf '%s\n' 'OpenSSL Ed25519 verification unavailable: no fallback to integrity' >&2
  exit 3
fi
digest="$(sha256sum -- "$capsule_path")" || exit 3
digest="${digest:0:64}"
tmp="$(mktemp -d)" || exit 3
trap 'rm -rf -- "$tmp"' EXIT
chmod 700 -- "$tmp"
# Distinct signature context, signer and complete ZIP digest are all bound.
printf 'aegis.offline.capsule.v1\0%s\0%s' "$signer" "$digest" > "$tmp/to-verify"
if ! openssl pkeyutl -verify -pubin -inkey "$key_path" -rawin \
       -in "$tmp/to-verify" -sigfile "$signature_path" >/dev/null 2>&1; then
  printf '%s\n' '{"schema":"aegis.offline.capsule-signature.v1","result":"REJECTED","publisher_delivery_verified":false,"release_assets_verified":false,"owner_approved":false,"executed":false}'
  exit 3
fi
# The signed outer ZIP is trusted as a byte envelope, not yet an
# executable release. Rehash each indexed member before ANY extraction.
if ! unzip -p "$capsule_path" 'aegis/delivery-index.v1' > "$tmp/index" 2>/dev/null; then
  printf '%s\n' 'Signed capsule has no delivery index' >&2; exit 3
fi
index_bytes="$(stat -c %s -- "$tmp/index")" || exit 3
if ((index_bytes < 40 || index_bytes > 131072)); then
  printf '%s\n' 'Signed delivery index outside bounds' >&2; exit 3
fi
IFS= read -r header < "$tmp/index" || exit 3
[[ "$header" == 'aegis.delivery-index.v1' ]] || {
  printf '%s\n' 'Unexpected signed delivery index version' >&2; exit 3
}
printf '%s\n' 'aegis/delivery-index.v1' > "$tmp/expected-names"
previous=''
count=0
total=0
tab=,"capsule_sha256":"%s","signer_key_id":"%s","publisher_public_key_sha256":"%s","publisher_delivery_verified":true,"delivery_members_hashed":true,"delivery_member_count":%s,"delivery_index_sha256":"%s","release_manifest_verified":false,"release_assets_verified":false,"publisher_revocation_current":false,"owner_approved":false,"executed":false,"core_activated":false}\n' "$digest" "$signer" "$observed_key" "$count" "$delivery_index_sha256"
\t'
record_pattern="^([0-9a-f]{64})${tab}([1-9][0-9]{0,11})${tab}(aegis/[A-Za-z0-9._/+@-]{1,240})$"
while IFS= read -r record || [[ -n "$record" ]]; do
  [[ "$record" =~ $record_pattern ]] || {
    printf '%s\n' 'Malformed delivery inventory record' >&2; exit 3
  }
  expected_digest="${BASH_REMATCH[1]}"
  expected_size="${BASH_REMATCH[2]}"
  member="${BASH_REMATCH[3]}"
  if [[ "$member" == 'aegis/delivery-index.v1' ||
        "$member" == *'//'* || "$member" == */../* ||
        "$member" == */./* || "$member" == */.. || "$member" == */. ||
        ( -n "$previous" && ! "$member" > "$previous" ) ]]; then
    printf '%s\n' 'Duplicate, unordered or redirected member' >&2; exit 3
  fi
  previous="$member"
  ((count+=1))
  if ((count > 128 || expected_size > 536870912)); then
    printf '%s\n' 'Signed delivery member exceeds bounds' >&2; exit 3
  fi
  total=$((total + expected_size))
  if ((total > 1075838976)); then
    printf '%s\n' 'Signed delivery total exceeds limit' >&2; exit 3
  fi
  observed_digest="$(unzip -p "$capsule_path" "$member" 2>/dev/null | sha256sum)" || exit 3
  observed_digest="${observed_digest:0:64}"
  observed_size="$(unzip -p "$capsule_path" "$member" 2>/dev/null | wc -c)" || exit 3
  [[ "$observed_size" =~ ^[0-9]+$ ]] || exit 3
  if [[ "$observed_digest" != "$expected_digest" || "$observed_size" != "$expected_size" ]]; then
    printf '%s\n' 'Publisher-sealed delivery member digest or size differs' >&2; exit 3
  fi
  printf '%s\n' "$member" >> "$tmp/expected-names"
done < <(tail -n +2 "$tmp/index")
((count >= 1)) || { printf '%s\n' 'Empty signed inventory refused' >&2; exit 3; }
unzip -Z -1 "$capsule_path" > "$tmp/archive-names" 2>/dev/null || exit 3
LC_ALL=C sort "$tmp/archive-names" > "$tmp/archive-sorted"
LC_ALL=C sort "$tmp/expected-names" > "$tmp/expected-sorted"
cmp -s "$tmp/archive-sorted" "$tmp/expected-sorted" || {
  printf '%s\n' 'ZIP contains unexpected/missing/duplicate entries' >&2; exit 3
}
delivery_index_sha256="$(sha256sum -- "$tmp/index")" || exit 3
delivery_index_sha256="${delivery_index_sha256:0:64}"
printf '{"schema":"aegis.offline.capsule-signature.v1","result":"SIGNED_CAPSULE_BYTES_ONLY","capsule_sha256":"%s","signer_key_id":"%s","publisher_public_key_sha256":"%s","publisher_delivery_verified":true,"release_manifest_verified":false,"release_assets_verified":false,"publisher_revocation_current":false,"owner_approved":false,"executed":false,"core_activated":false}\n' "$digest" "$signer" "$observed_key"
