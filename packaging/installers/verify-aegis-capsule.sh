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
for command in openssl sha256sum realpath stat mktemp chmod rm; do
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
printf '{"schema":"aegis.offline.capsule-signature.v1","result":"SIGNED_CAPSULE_BYTES_ONLY","capsule_sha256":"%s","signer_key_id":"%s","publisher_public_key_sha256":"%s","publisher_delivery_verified":true,"release_manifest_verified":false,"release_assets_verified":false,"publisher_revocation_current":false,"owner_approved":false,"executed":false,"core_activated":false}\n' "$digest" "$signer" "$observed_key"
