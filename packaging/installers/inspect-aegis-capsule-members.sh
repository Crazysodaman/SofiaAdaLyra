#!/usr/bin/env bash
# Read-only file-level check for a separately publisher-verified Aegis ZIP.
# NOT a signature check, installer, trust-root authority or owner approval.
# Compare the SAME ZIP SHA against the independently authenticated seal.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
umask 077
if (($# != 4)) || [[ "$1" != '--capsule' || "$3" != '--expected-sha256' ||
      ! "$4" =~ ^[0-9a-f]{64}$ ]]; then
  printf '%s\n' 'Usage: inspect-aegis-capsule-members.sh --capsule ZIP --expected-sha256 SEALED_SHA256' >&2
  exit 2
fi
for cmd in unzip sha256sum realpath stat mktemp chmod rm wc sort cmp tail; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf '%s\n' 'Offline ZIP verification prerequisites missing' >&2
    exit 3
  fi
done
original="$(realpath -ms -- "$2")" || exit 3
actual="$(realpath -e -- "$2")" || exit 3
[[ "$original" == "$actual" && -f "$actual" && ! -L "$actual" ]] || exit 3
size="$(stat -c %s -- "$actual")" || exit 3
[[ "$size" =~ ^[0-9]+$ ]] || exit 3
((size > 0 && size <= 1075838976)) || exit 3
capsule_sha="$(sha256sum -- "$actual")" || exit 3
capsule_sha="${capsule_sha:0:64}"
if [[ "$capsule_sha" != "$4" ]]; then
  printf '%s\n' 'Capsule ZIP differs from authenticated publisher receipt' >&2
  exit 3
fi
work="$(mktemp -d)" || exit 3
trap 'rm -rf -- "$work"' EXIT
chmod 700 -- "$work"
if ! unzip -p "$actual" 'aegis/delivery-index.v1' > "$work/index" 2>/dev/null; then
  printf '%s\n' 'Delivery index missing' >&2; exit 3
fi
index_size="$(stat -c %s -- "$work/index")" || exit 3
((index_size >= 40 && index_size <= 131072)) || exit 3
IFS= read -r header < "$work/index" || exit 3
[[ "$header" == 'aegis.delivery-index.v1' ]] || exit 3
printf '%s\n' 'aegis/delivery-index.v1' > "$work/expected-names"
tab=$'\t'
pattern="^([0-9a-f]{64})${tab}([1-9][0-9]{0,11})${tab}(aegis/[A-Za-z0-9._/+@-]{1,240})$"
count=0
total=0
previous=''
while IFS= read -r record || [[ -n "$record" ]]; do
  [[ "$record" =~ $pattern ]] || exit 3
  digest="${BASH_REMATCH[1]}"
  expected_bytes="${BASH_REMATCH[2]}"
  path="${BASH_REMATCH[3]}"
  if [[ "$path" == 'aegis/delivery-index.v1' ||
        "$path" == *'//'* || "$path" == */../* || "$path" == */./* ||
        "$path" == */.. || "$path" == */. ]]; then
    exit 3
  fi
  if [[ -n "$previous" && !( "$path" > "$previous" ) ]]; then exit 3; fi
  previous="$path"
  ((count+=1))
  ((count <= 128 && expected_bytes <= 536870912)) || exit 3
  total=$((total+expected_bytes))
  ((total <= 1075838976)) || exit 3
  observed="$(unzip -p "$actual" "$path" 2>/dev/null | sha256sum)" || exit 3
  observed="${observed:0:64}"
  actual_bytes="$(unzip -p "$actual" "$path" 2>/dev/null | wc -c)" || exit 3
  if [[ "$observed" != "$digest" || "$actual_bytes" != "$expected_bytes" ]]; then
    printf '%s\n' 'Signed delivery member digest/size differs' >&2
    exit 3
  fi
  printf '%s\n' "$path" >> "$work/expected-names"
done < <(tail -n +2 "$work/index")
((count >= 1)) || exit 3
unzip -Z -1 "$actual" > "$work/zip-names" 2>/dev/null || exit 3
LC_ALL=C sort "$work/zip-names" > "$work/zip-sorted"
LC_ALL=C sort "$work/expected-names" > "$work/expected-sorted"
cmp -s "$work/zip-sorted" "$work/expected-sorted" || exit 3
index_sha="$(sha256sum -- "$work/index")" || exit 3
index_sha="${index_sha:0:64}"
printf '{"schema":"aegis.offline.capsule-member-check.v1","result":"MEMBERS_HASHED_NOT_INSTALLABLE","capsule_sha256":"%s","delivery_index_sha256":"%s","member_count":%s,"asset_bytes_hash_verified":true,"publisher_signature_verified":false,"release_manifest_verified":false,"owner_approved":false,"service_mutated":false,"core_activated":false}\n' "$capsule_sha" "$index_sha" "$count"
