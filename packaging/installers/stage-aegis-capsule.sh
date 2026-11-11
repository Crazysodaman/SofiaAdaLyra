#!/usr/bin/env bash
# Aegis verified offline capsule STAGING ONLY. Not a native installer.
# This script must itself originate from an independently trusted publisher.
# A ZIP, its included scripts, or a printed SHA is never its own trust root.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
umask 077

if (($# != 12)) || [[ "$1" != '--capsule' || "$3" != '--signature' ||
    "$5" != '--publisher-key' || "$7" != '--publisher-sha256' ||
    "$9" != '--publisher-signer' || "${11}" != '--destination' ]]; then
  printf '%s\n' 'Usage: stage-aegis-capsule.sh --capsule ZIP --signature RAW64 --publisher-key PEM --publisher-sha256 PIN --publisher-signer ID --destination PRIVATE_NEW_DIRECTORY' >&2
  exit 2
fi
capsule="$2"; signature="$4"; publisher_key="$6"
publisher_pin="$8"; signer="${10}"; destination="${12}"
for tool in bash openssl sha256sum realpath stat mktemp unzip mkdir chmod rm mv wc head tail od tr sed dirname basename id; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf '%s\n' 'Required stock Debian verification/staging tool missing' >&2
    exit 3
  fi
done
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
verifier="$script_dir/verify-aegis-capsule.sh"
inspector="$script_dir/inspect-aegis-capsule-members.sh"
if [[ ! -f "$verifier" || -L "$verifier" || ! -f "$inspector" || -L "$inspector" ]]; then
  printf '%s\n' 'Independently reviewed capsule verification scripts unavailable' >&2
  exit 3
fi
# No root elevation, symlinks, arbitrary destinations or permissions changes
# outside the one explicitly designated new owner-private directory.
if [[ "$destination" != /* || -e "$destination" || -L "$destination" ]]; then
  printf '%s\n' 'Staging destination must be a new absolute path' >&2
  exit 3
fi
leaf="$(basename -- "$destination")"
if [[ ! "$leaf" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$ ]]; then
  printf '%s\n' 'Staging directory name rejected' >&2; exit 3
fi
parent="$(dirname -- "$destination")"
if [[ ! -d "$parent" || -L "$parent" ||
      "$(realpath -ms -- "$parent")" != "$(realpath -e -- "$parent")" ]]; then
  printf '%s\n' 'Staging parent missing or redirected' >&2; exit 3
fi
mode="$(stat -c %a -- "$parent")" || exit 3
owner="$(stat -c %u -- "$parent")" || exit 3
if [[ "$mode" != 700 && "$mode" != 0700 ]] || [[ "$owner" != "$(id -u)" ]]; then
  printf '%s\n' 'Staging parent must be owner-owned mode 0700' >&2; exit 3
fi

# The existing independently trusted Ed25519 seal and every ZIP member are
# verified BEFORE any destination is created. A staged release is inert bytes.
seal="$(bash "$verifier" --capsule "$capsule" --signature "$signature" \
  --publisher-key "$publisher_key" --publisher-sha256 "$publisher_pin" \
  --publisher-signer "$signer")" || exit 3
if [[ "$seal" != *'"result":"SIGNED_CAPSULE_BYTES_ONLY"'* ||
      "$seal" != *'"publisher_delivery_verified":true'* ]]; then
  printf '%s\n' 'Outer publisher seal not verified' >&2; exit 3
fi
verified_sha="$(printf '%s\n' "$seal" | sed -nE 's/.*"capsule_sha256":"([0-9a-f]{64})".*/\1/p')"
[[ "$verified_sha" =~ ^[0-9a-f]{64}$ ]] || {
  printf '%s\n' 'Authenticated capsule digest unavailable' >&2; exit 3;
}
sealed_sha="$(sha256sum -- "$capsule")" || exit 3
sealed_sha="${sealed_sha:0:64}"
[[ "$sealed_sha" == "$verified_sha" ]] || {
  printf '%s\n' 'Capsule changed after publisher verification' >&2; exit 3;
}
bash "$inspector" --capsule "$capsule" --expected-sha256 "$sealed_sha" >/dev/null || exit 3

work="$(mktemp -d -- "$parent/.aegis-stage-XXXXXXXX")" || exit 3
committed=0
cleanup() {
  if ((committed == 0)); then rm -rf -- "$work"; fi
}
trap cleanup EXIT
chmod 700 -- "$work"
# The inspector already enforces a sorted, unique, exact ZIP member list,
# canonical relative paths and hash/size bounds. Recheck each extracted file
# independently against its signed inventory and the final sealed ZIP hash.
index="$work/.delivery-index"
if ! unzip -p "$capsule" 'aegis/delivery-index.v1' | head -c 131073 > "$index"; then
  printf '%s\n' 'Bounded signed delivery index changed' >&2; exit 3
fi
[[ "$(wc -c < "$index")" -le 131072 ]] || exit 3
IFS= read -r header < "$index" || exit 3
[[ "$header" == 'aegis.delivery-index.v1' ]] || exit 3
# Do not inherit a changed global IFS into later filesystem operations.
# The signed inventory is tab-delimited, sorted, newline-terminated and
# bounded, exactly as the upstream inspector and Python verifier require.
[[ "$(tail -c 1 -- "$index" | od -An -tu1 | tr -d '[:space:]')" == 10 ]] || exit 3
count=0
total=0
previous=''
while IFS=
  # Explicit redirection creates a normal file, NEVER follows a ZIP symlink.
  # head and pipefail stop an oversized decompressor before unbounded output.
  if ! unzip -p "$capsule" "$relative" | head -c "$((size+1))" > "$file"; then
    printf '%s\n' 'Capsule member extraction failed or overflowed' >&2; exit 3
  fi
  [[ "$(stat -c %s -- "$file")" == "$size" ]] || exit 3
  observed="$(sha256sum -- "$file")" || exit 3
  [[ "${observed:0:64}" == "$digest" ]] || exit 3
  chmod 600 -- "$file"
done < <(sed '1d' "$index")
((count >= 1)) || exit 3
# Preserve the signed delivery index as a normal regular file, within the
# same staging namespace as the extracted release and launchers.
mkdir -p -- "$work/aegis"
mv -- "$index" "$work/aegis/delivery-index.v1"
chmod 600 -- "$work/aegis/delivery-index.v1"
final_sha="$(sha256sum -- "$capsule")" || exit 3
[[ "${final_sha:0:64}" == "$sealed_sha" ]] || {
  printf '%s\n' 'Signed capsule changed during staging' >&2; exit 3;
}
if [[ -e "$destination" || -L "$destination" ]]; then
  printf '%s\n' 'Destination appeared during safe staging' >&2; exit 3
fi
# GNU mv --no-clobber does not overwrite an existing destination. Confirm
# the temporary directory disappeared before reporting a completed stage.
mv -T --no-clobber -- "$work" "$destination" || exit 3
if [[ -e "$work" || ! -d "$destination" ]]; then
  printf '%s\n' 'Staging commit not completed' >&2; exit 3
fi
committed=1
printf '{"schema":"aegis.offline.capsule-stage.v1","result":"SIGNED_MEDIA_STAGED_NOT_INSTALLED","capsule_sha256":"%s","member_count":%d,"publisher_delivery_verified":true,"inner_release_assets_verified_by_stager":false,"owner_approved":false,"native_service_registered":false,"core_activated":false,"fleet_enrolled":false}\n' "$sealed_sha" "$count"
\t' read -r digest size relative || [[ -n "$digest$size$relative" ]]; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ && "$size" =~ ^[1-9][0-9]{0,11}$ &&
      "$relative" =~ ^aegis/[A-Za-z0-9._/+@-]{1,240}$ ]] || exit 3
  [[ "$relative" != *'//'* && "$relative" != */../* &&
     "$relative" != */./* && "$relative" != */.. && "$relative" != */. ]] || exit 3
  if [[ -n "$previous" && !( "$relative" > "$previous" ) ]]; then exit 3; fi
  previous="$relative"
  ((count+=1))
  ((count <= 128 && size <= 536870912)) || exit 3
  total=$((total+size))
  ((total <= 1075838976)) || exit 3
  file="$work/$relative"
  mkdir -p -- "$(dirname -- "$file")"
  # Explicit redirection creates a normal file, NEVER follows a ZIP symlink.
  # head and pipefail stop an oversized decompressor before unbounded output.
  if ! unzip -p "$capsule" "$relative" | head -c "$((size+1))" > "$file"; then
    printf '%s\n' 'Capsule member extraction failed or overflowed' >&2; exit 3
  fi
  [[ "$(stat -c %s -- "$file")" == "$size" ]] || exit 3
  observed="$(sha256sum -- "$file")" || exit 3
  [[ "${observed:0:64}" == "$digest" ]] || exit 3
  chmod 600 -- "$file"
done < <(sed '1d' "$index")
((count >= 1)) || exit 3
# Preserve the signed delivery index as a normal regular file, within the
# same staging namespace as the extracted release and launchers.
mkdir -p -- "$work/aegis"
mv -- "$index" "$work/aegis/delivery-index.v1"
chmod 600 -- "$work/aegis/delivery-index.v1"
final_sha="$(sha256sum -- "$capsule")" || exit 3
[[ "${final_sha:0:64}" == "$sealed_sha" ]] || {
  printf '%s\n' 'Signed capsule changed during staging' >&2; exit 3;
}
if [[ -e "$destination" || -L "$destination" ]]; then
  printf '%s\n' 'Destination appeared during safe staging' >&2; exit 3
fi
# GNU mv --no-clobber does not overwrite an existing destination. Confirm
# the temporary directory disappeared before reporting a completed stage.
mv -T --no-clobber -- "$work" "$destination" || exit 3
if [[ -e "$work" || ! -d "$destination" ]]; then
  printf '%s\n' 'Staging commit not completed' >&2; exit 3
fi
committed=1
printf '{"schema":"aegis.offline.capsule-stage.v1","result":"SIGNED_MEDIA_STAGED_NOT_INSTALLED","capsule_sha256":"%s","member_count":%d,"publisher_delivery_verified":true,"inner_release_assets_verified_by_stager":false,"owner_approved":false,"native_service_registered":false,"core_activated":false,"fleet_enrolled":false}\n' "$sealed_sha" "$count"
\t' read -r digest size relative || [[ -n "$digest$size$relative" ]]; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ && "$size" =~ ^[1-9][0-9]{0,11}$ &&
      "$relative" =~ ^aegis/[A-Za-z0-9._/+@-]{1,240}$ ]] || exit 3
  [[ "$relative" != *'//'* && "$relative" != */../* &&
     "$relative" != */./* && "$relative" != */.. && "$relative" != */. ]] || exit 3
  if [[ -n "$previous" && !( "$relative" > "$previous" ) ]]; then exit 3; fi
  previous="$relative"
  ((count+=1))
  ((count <= 128 && size <= 536870912)) || exit 3
  total=$((total+size))
  ((total <= 1075838976)) || exit 3
  file="$work/$relative"
  mkdir -p -- "$(dirname -- "$file")"
  # Explicit redirection creates a normal file, NEVER follows a ZIP symlink.
  # head and pipefail stop an oversized decompressor before unbounded output.
  if ! unzip -p "$capsule" "$relative" | head -c "$((size+1))" > "$file"; then
    printf '%s\n' 'Capsule member extraction failed or overflowed' >&2; exit 3
  fi
  [[ "$(stat -c %s -- "$file")" == "$size" ]] || exit 3
  observed="$(sha256sum -- "$file")" || exit 3
  [[ "${observed:0:64}" == "$digest" ]] || exit 3
  chmod 600 -- "$file"
done < <(sed '1d' "$index")
((count >= 1)) || exit 3
# Preserve the signed delivery index as a normal regular file, within the
# same staging namespace as the extracted release and launchers.
mkdir -p -- "$work/aegis"
mv -- "$index" "$work/aegis/delivery-index.v1"
chmod 600 -- "$work/aegis/delivery-index.v1"
final_sha="$(sha256sum -- "$capsule")" || exit 3
[[ "${final_sha:0:64}" == "$sealed_sha" ]] || {
  printf '%s\n' 'Signed capsule changed during staging' >&2; exit 3;
}
if [[ -e "$destination" || -L "$destination" ]]; then
  printf '%s\n' 'Destination appeared during safe staging' >&2; exit 3
fi
# GNU mv --no-clobber does not overwrite an existing destination. Confirm
# the temporary directory disappeared before reporting a completed stage.
mv -T --no-clobber -- "$work" "$destination" || exit 3
if [[ -e "$work" || ! -d "$destination" ]]; then
  printf '%s\n' 'Staging commit not completed' >&2; exit 3
fi
committed=1
printf '{"schema":"aegis.offline.capsule-stage.v1","result":"SIGNED_MEDIA_STAGED_NOT_INSTALLED","capsule_sha256":"%s","member_count":%d,"publisher_delivery_verified":true,"inner_release_assets_verified_by_stager":false,"owner_approved":false,"native_service_registered":false,"core_activated":false,"fleet_enrolled":false}\n' "$sealed_sha" "$count"
\t' read -r digest size relative || [[ -n "$digest$size$relative" ]]; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ && "$size" =~ ^[1-9][0-9]{0,11}$ &&
      "$relative" =~ ^aegis/[A-Za-z0-9._/+@-]{1,240}$ ]] || exit 3
  [[ "$relative" != *'//'* && "$relative" != */../* &&
     "$relative" != */./* && "$relative" != */.. && "$relative" != */. ]] || exit 3
  if [[ -n "$previous" && !( "$relative" > "$previous" ) ]]; then exit 3; fi
  previous="$relative"
  ((count+=1))
  ((count <= 128 && size <= 536870912)) || exit 3
  total=$((total+size))
  ((total <= 1075838976)) || exit 3
  file="$work/$relative"
  mkdir -p -- "$(dirname -- "$file")"
  # Explicit redirection creates a normal file, NEVER follows a ZIP symlink.
  # head and pipefail stop an oversized decompressor before unbounded output.
  if ! unzip -p "$capsule" "$relative" | head -c "$((size+1))" > "$file"; then
    printf '%s\n' 'Capsule member extraction failed or overflowed' >&2; exit 3
  fi
  [[ "$(stat -c %s -- "$file")" == "$size" ]] || exit 3
  observed="$(sha256sum -- "$file")" || exit 3
  [[ "${observed:0:64}" == "$digest" ]] || exit 3
  chmod 600 -- "$file"
done < <(sed '1d' "$index")
((count >= 1)) || exit 3
# Preserve the signed delivery index as a normal regular file, within the
# same staging namespace as the extracted release and launchers.
mkdir -p -- "$work/aegis"
mv -- "$index" "$work/aegis/delivery-index.v1"
chmod 600 -- "$work/aegis/delivery-index.v1"
final_sha="$(sha256sum -- "$capsule")" || exit 3
[[ "${final_sha:0:64}" == "$sealed_sha" ]] || {
  printf '%s\n' 'Signed capsule changed during staging' >&2; exit 3;
}
if [[ -e "$destination" || -L "$destination" ]]; then
  printf '%s\n' 'Destination appeared during safe staging' >&2; exit 3
fi
# GNU mv --no-clobber does not overwrite an existing destination. Confirm
# the temporary directory disappeared before reporting a completed stage.
mv -T --no-clobber -- "$work" "$destination" || exit 3
if [[ -e "$work" || ! -d "$destination" ]]; then
  printf '%s\n' 'Staging commit not completed' >&2; exit 3
fi
committed=1
printf '{"schema":"aegis.offline.capsule-stage.v1","result":"SIGNED_MEDIA_STAGED_NOT_INSTALLED","capsule_sha256":"%s","member_count":%d,"publisher_delivery_verified":true,"inner_release_assets_verified_by_stager":false,"owner_approved":false,"native_service_registered":false,"core_activated":false,"fleet_enrolled":false}\n' "$sealed_sha" "$count"
