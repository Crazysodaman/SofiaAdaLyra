#!/usr/bin/env bash
# Aegis Platform installer shell, Phase UX-1: read-only preflight.
# This entrypoint never elevates or changes services. Installation requires
# the signed-release verification and owner-authorized executor in #201.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd -P)"
# Support both repository development layout and a future reviewed bundle root.
if [[ -f "$SCRIPT_DIR/contracts/ui/aegis-theme-v1.json" ]]; then
  ROOT="$SCRIPT_DIR"
else
  ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
fi
THEME="$ROOT/contracts/ui/aegis-theme-v1.json"
MODE=menu
PLAIN=0
JSON_MODE=0
DRY_RUN=0
CHECK_REQUESTED=0
OPERATION_REQUESTED=0
OPERATION=none
SEED_ARCHIVE=''
SEED_SHA256=''
SEED_REQUESTED=0
PUBLISHER_REQUESTED=0
RELEASE_ROOT=''
PUBLISHER_KEY=''
PUBLISHER_FINGERPRINT=''
PUBLISHER_SIGNER=''

usage() {
  printf '%s\n' 'Aegis installer (PREVIEW ONLY)' \
    'Usage: install-aegis.sh [--check] [--no-color|--plain|--line-mode] [--json]' \
    '       install-aegis.sh --operation OP [--json] [--dry-run]' \
    '       install-aegis.sh --verify-seed FILE --trusted-seed-sha256 HEX [--json]' \
    '       install-aegis.sh --verify-publisher DIR --publisher-key PEM --publisher-sha256 HEX --publisher-signer ID [--json]' \
    'OP: status, doctor, install, update, repair, rollback, uninstall, purge' \
    'Mutation is BLOCKED until the signed OS executor and SAFE/STOP are connected.'
}

while (($#)); do
  case "$1" in
    --check) MODE=check; CHECK_REQUESTED=1; shift ;;
    --verify-publisher)
      if ((PUBLISHER_REQUESTED)) || (($# < 2)); then printf '%s\n' 'Invalid publisher request' >&2; exit 2; fi
      PUBLISHER_REQUESTED=1; MODE=publisher; RELEASE_ROOT="$2"; shift 2 ;;
    --publisher-key)
      if [[ -n "$PUBLISHER_KEY" ]] || (($# < 2)); then printf '%s\n' 'Invalid publisher key' >&2; exit 2; fi
      PUBLISHER_KEY="$2"; shift 2 ;;
    --publisher-sha256)
      if [[ -n "$PUBLISHER_FINGERPRINT" ]] || (($# < 2)); then printf '%s\n' 'Invalid publisher fingerprint' >&2; exit 2; fi
      PUBLISHER_FINGERPRINT="$2"; shift 2 ;;
    --publisher-signer)
      if [[ -n "$PUBLISHER_SIGNER" ]] || (($# < 2)); then printf '%s\n' 'Invalid publisher identity' >&2; exit 2; fi
      PUBLISHER_SIGNER="$2"; shift 2 ;;
    --verify-seed)
      if ((SEED_REQUESTED)) || (($# < 2)); then printf '%s\n' 'Invalid seed argument' >&2; exit 2; fi
      SEED_REQUESTED=1; MODE=seed; SEED_ARCHIVE="$2"; shift 2 ;;
    --trusted-seed-sha256)
      if [[ -n "$SEED_SHA256" ]] || (($# < 2)); then printf '%s\n' 'Invalid trusted digest argument' >&2; exit 2; fi
      SEED_SHA256="$2"; shift 2 ;;
    --help|-h) MODE=help; shift ;;
    --no-color|--plain|--line-mode) PLAIN=1; shift ;;
    --json) JSON_MODE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --operation)
      if ((OPERATION_REQUESTED)); then printf '%s\n' 'Operation specified twice' >&2; exit 2; fi
      OPERATION_REQUESTED=1
      if (($# < 2)); then printf '%s\n' 'Missing operation' >&2; exit 2; fi
      OPERATION="$2"
      case "$OPERATION" in
        status|doctor|install|update|repair|rollback|uninstall|purge) ;;
        *) printf '%s\n' 'Unknown operation' >&2; exit 2 ;;
      esac
      MODE=operation; shift 2 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

if (( (CHECK_REQUESTED && OPERATION_REQUESTED) || (SEED_REQUESTED && (CHECK_REQUESTED || OPERATION_REQUESTED || DRY_RUN)) )); then
  printf '%s\n' 'Ambiguous operation or seed flags' >&2
  exit 2
fi
if [[ -n "$SEED_SHA256" && "$SEED_REQUESTED" -eq 0 ]]; then
  printf '%s\n' '--trusted-seed-sha256 requires --verify-seed' >&2; exit 2
fi
if ((PUBLISHER_REQUESTED && (CHECK_REQUESTED || OPERATION_REQUESTED || SEED_REQUESTED || DRY_RUN))); then
  printf '%s\n' 'Publisher signature check cannot authorize a protected operation' >&2; exit 2
fi
if (( !PUBLISHER_REQUESTED )) && [[ -n "$PUBLISHER_KEY" || -n "$PUBLISHER_FINGERPRINT" || -n "$PUBLISHER_SIGNER" ]]; then
  printf '%s\n' 'Publisher trust flags require --verify-publisher' >&2; exit 2
fi
if ((PUBLISHER_REQUESTED)) && [[ -n "$SEED_SHA256" ]]; then
  printf '%s\n' 'Publisher mode cannot be mixed with seed mode' >&2; exit 2
fi

# Presentation manifest is never evaluated or sourced as executable code.
theme_hex() {
  local key="$1" value=''
  [[ -f "$THEME" ]] || return 1
  value="$(sed -nE "s/^[[:space:]]*\"$key\"[[:space:]]*:[[:space:]]*\"(#[0-9A-F]{6})\"[,[:space:]]*$/\1/p" "$THEME")"
  [[ "$value" =~ ^#[0-9A-F]{6}$ ]] || return 1
  printf '%s' "$value"
}

use_color=0
narrow=0
# No ANSI in noninteractive output. Use the single canonical theme manifest.
if [[ "$PLAIN" -eq 0 && "$JSON_MODE" -eq 0 && -t 0 && -t 1 && ! -v NO_COLOR &&
      "$(printenv TERM || printf dumb)" != dumb ]]; then
  if [[ "$(printenv COLORTERM || true)" =~ (truecolor|24bit) ]]; then
    use_color=3
  elif [[ "$(printenv TERM || true)" == *256color* ]]; then
    use_color=2
  else
    use_color=1
  fi
  # Narrow SSH/serial windows use monochrome instead of clipped color art.
  width="$(tput cols 2>/dev/null || printf 80)"
  if [[ "$width" =~ ^[0-9]{1,4}$ ]] && ((width < 64)); then use_color=0; narrow=1; fi
fi

paint() {
  local role="$1" label="$2" hex r g b code color256
  if [[ "$use_color" -eq 0 ]] || ! hex="$(theme_hex "$role")"; then
    printf '%s' "$label"; return
  fi
  case "$role:$hex" in
    primary:'#9400D3') code=35; color256=128 ;;
    accent:'#00C2FF') code=36; color256=45 ;;
    success:'#39FF14') code=32; color256=118 ;;
    warning:'#FFB000') code=33; color256=214 ;;
    text_main:'#E5E7EB') code=37; color256=254 ;;
    *) printf '%s' "$label"; return ;;
  esac
  case "$use_color" in
    3)
      r=$(printf '%d' "0x$(printf '%s' "$hex" | cut -c2-3)")
      g=$(printf '%d' "0x$(printf '%s' "$hex" | cut -c4-5)")
      b=$(printf '%d' "0x$(printf '%s' "$hex" | cut -c6-7)")
      printf '\033[38;2;%d;%d;%dm%s\033[0m' "$r" "$g" "$b" "$label"
      ;;
    2) printf '\033[38;5;%dm%s\033[0m' "$color256" "$label" ;;
    1) printf '\033[%sm%s\033[0m' "$code" "$label" ;;
  esac
}

preflight() {
  local os_name='UNKNOWN' arch='UNKNOWN'
  if [[ -r /etc/os-release ]]; then
    os_name="$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | head -n1 | tr -d '"')"
  fi
  arch="$(uname -m 2>/dev/null || printf UNKNOWN)"
  printf '%s\n' 'AEGIS PLATFORM INSTALLER PREFLIGHT' \
    'MODE=PREVIEW_ONLY' 'SIGNED_RELEASE=NOT_VERIFIED' \
    'SERVICE_STATE=NOT_OBSERVED' \
    "OS=$os_name" "ARCH=$arch" \
    'INSTALL_AUTHORITY=NOT_CONNECTED' \
    'RESULT=NO_CHANGES_MADE'
}

# Stable, machine-readable, deliberately untrusted preview result.
json_result() {
  local result="$1"
  printf '{"schema":"aegis.installer.preflight.v1","mode":"PREVIEW_ONLY","operation":"%s","signed_release":"NOT_VERIFIED","service_state":"NOT_OBSERVED","authority":"NOT_CONNECTED","executed":false,"owner_approved":false,"core_activated":false,"result":"%s"}\n' "$OPERATION" "$result"
}
blocked() {
  if [[ "$JSON_MODE" -eq 1 ]]; then json_result BLOCKED
  else
    printf '%s\n' 'MODE=PREVIEW_ONLY' "REQUESTED_OPERATION=$OPERATION" \
      'SIGNED_RELEASE=NOT_VERIFIED' 'INSTALL_AUTHORITY=NOT_CONNECTED' \
      'RESULT=BLOCKED' 'BLOCKED: no signed native OS executor or fresh SAFE/STOP owner authority.'
  fi
  return 3
}
readonly_preview() {
  if [[ "$JSON_MODE" -eq 1 ]]; then json_result NO_CHANGES_MADE
  else preflight
  fi
}

# Offline byte verification uses Debian standard coreutils, not a project
# Python/Rust/Git/Ollama installation. The SHA must be obtained independently
# from trusted release provenance: a hash printed on the same medium is not trust.
verify_seed_bytes() {
  if [[ ! "$SEED_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
    printf '%s\n' 'An independently pinned lowercase SHA-256 is required' >&2
    return 2
  fi
  if [[ ! -f "$SEED_ARCHIVE" || -L "$SEED_ARCHIVE" ]]; then
    printf '%s\n' 'Seed must be an existing ordinary file' >&2; return 3
  fi
  # Debian 12 coreutils realpath rejects symlink/junction-like path components.
  local original actual size observed
  original="$(realpath -ms -- "$SEED_ARCHIVE")" || return 3
  actual="$(realpath -e -- "$SEED_ARCHIVE")" || return 3
  if [[ "$original" != "$actual" ]]; then
    printf '%s\n' 'Seed path contains filesystem redirection' >&2; return 3
  fi
  size="$(stat -c '%s' -- "$actual")" || return 3
  if [[ ! "$size" =~ ^[0-9]+$ ]] || ((size < 1 || size > 1073741824)); then
    printf '%s\n' 'Offline seed size outside bounded policy' >&2; return 3
  fi
  observed="$(sha256sum -- "$actual")" || return 3
  observed="${observed:0:64}"
  if [[ "$observed" != "$SEED_SHA256" ]]; then
    if ((JSON_MODE)); then
      printf '%s\n' '{"schema":"aegis.installer.seed-byte-check.v1","result":"REJECTED","byte_digest_match":false,"signature_verified":false,"executed":false,"core_activated":false}'
    else printf '%s\n' 'RESULT=REJECTED' 'SIGNED_RELEASE=NOT_VERIFIED' 'NO_CHANGES_MADE=TRUE'
    fi
    return 3
  fi
  if ((JSON_MODE)); then
    printf '{"schema":"aegis.installer.seed-byte-check.v1","result":"HASH_MATCH_ONLY","sha256":"%s","size_bytes":%s,"signature_verified":false,"owner_approved":false,"executed":false,"core_activated":false}\n' "$observed" "$size"
  else
    printf '%s\n' 'RESULT=HASH_MATCH_ONLY' "SHA256=$observed" "SIZE_BYTES=$size" 'SIGNED_RELEASE=NOT_VERIFIED' 'PUBLISHER_SIGNATURE=NOT_VERIFIED' 'INSTALL_AUTHORITY=NOT_CONNECTED' 'NO_CHANGES_MADE=TRUE'
  fi
  return 0
}

# Public Ed25519 proof over the existing canonical Python release digest.
# This invokes only stock OpenSSL, SHA256 and base64. It does NOT verify the
# assets/manifest schema, install a service, or act as owner authorization.
verify_publisher_manifest() {
  local root="$RELEASE_ROOT" key="$PUBLISHER_KEY"
  local root_real key_real manifest envelope_file envelope signature signer
  local manifest_size envelope_size key_size hash digest work rc=3
  if [[ ! "$PUBLISHER_FINGERPRINT" =~ ^[0-9a-f]{64}$ ||
        ! "$PUBLISHER_SIGNER" =~ ^[A-Za-z0-9_.-]{1,128}$ ]]; then
    printf '%s\n' 'Independently pinned publisher fingerprint and signer required' >&2
    return 2
  fi
  if ! command -v openssl >/dev/null 2>&1 ||
     ! command -v sha256sum >/dev/null 2>&1 ||
     ! command -v base64 >/dev/null 2>&1; then
    printf '%s\n' 'Stock Ed25519 verifier unavailable; deny signature acceptance' >&2
    return 3
  fi
  if [[ ! -d "$root" || -L "$root" || ! -f "$key" || -L "$key" ]]; then
    printf '%s\n' 'Signed bundle or independently pinned publisher key unavailable' >&2
    return 3
  fi
  root_real="$(realpath -e -- "$root")" || return 3
  key_real="$(realpath -e -- "$key")" || return 3
  if [[ "$(realpath -ms -- "$root")" != "$root_real" ||
        "$(realpath -ms -- "$key")" != "$key_real" ]]; then
    printf '%s\n' 'Bundle or publisher root contains filesystem redirection' >&2
    return 3
  fi
  case "$key_real" in "$root_real"/*|"$root_real")
    printf '%s\n' 'Publisher trust root must be independently provisioned' >&2
    return 3 ;;
  esac
  manifest="$root_real/release-manifest.json"
  envelope_file="$root_real/release-signature.json"
  for file in "$manifest" "$envelope_file" "$key_real"; do
    [[ -f "$file" && ! -L "$file" ]] || return 3
    [[ "$(realpath -ms -- "$file")" == "$(realpath -e -- "$file")" ]] || return 3
  done
  manifest_size="$(stat -c %s -- "$manifest")" || return 3
  envelope_size="$(stat -c %s -- "$envelope_file")" || return 3
  key_size="$(stat -c %s -- "$key_real")" || return 3
  if ((manifest_size < 1 || manifest_size > 131072 ||
        envelope_size < 1 || envelope_size > 8192 ||
        key_size < 1 || key_size > 16384)); then
    printf '%s\n' 'Signed manifest, signature or key exceeds bounded limits' >&2
    return 3
  fi
  hash="$(sha256sum -- "$key_real")" || return 3
  hash="$(printf '%s' "$hash" | cut -c1-64)"
  [[ "$hash" == "$PUBLISHER_FINGERPRINT" ]] || {
    printf '%s\n' 'Publisher key differs from independent trust anchor' >&2
    return 3
  }
  # Canonical signature envelope: exact two keys, one line, no trailing bytes
  # beyond permitted line ending. Unknown/duplicate JSON fields fail closed.
  envelope="$(cat -- "$envelope_file")" || return 3
  local envelope_re='^\{"signature_b64":"([A-Za-z0-9+/]{86}==)","signer_key_id":"([A-Za-z0-9_.-]{1,128})"\}
if [[ "$MODE" == seed ]]; then verify_seed_bytes; exit $?; fi
if [[ "$MODE" == check ]]; then readonly_preview; exit 0; fi
if [[ "$MODE" == operation ]]; then
  case "$OPERATION" in
    status|doctor) readonly_preview; exit 0 ;;
    *) blocked; exit 3 ;;
  esac
fi
if [[ "$JSON_MODE" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
  printf '%s\n' '--json/--dry-run require --check or --operation' >&2
  exit 2
fi
if [[ ! -t 0 || ! -t 1 ]]; then
  printf '%s\n' 'Interactive setup requires a terminal. Use --check for read-only preflight.' >&2
  exit 2
fi

while :; do
  if [[ "$narrow" -eq 1 ]]; then
    printf '%s\n' 'AEGIS PLATFORM INSTALLER' 'PREVIEW ONLY / NO INSTALL AUTHORITY'
  else
    paint primary '+------------------------------------------------------------+'
    printf '\n'
    paint primary '|                AEGIS PLATFORM INSTALLER                    |'
    printf '\n'
    paint warning '|        PREVIEW ONLY / NO INSTALL AUTHORITY                 |'
    printf '\n'
    paint primary '+------------------------------------------------------------+'
    printf '\n'
  fi
  paint accent '[1]'; printf ' Install Platform (blocked)\n'
  paint accent '[2]'; printf ' Update Platform (blocked)\n'
  paint accent '[3]'; printf ' Repair Platform (blocked)\n'
  paint accent '[4]'; printf ' Uninstall Platform (blocked)\n'
  paint accent '[5]'; printf ' Diagnostics (read-only)\n'
  paint accent '[6]'; printf ' Rollback (blocked)\n'
  paint accent '[7]'; printf ' Status (unverified)\n'
  paint accent '[0]'; printf ' Exit\n'
  printf '%s\n' '[?] Help | [B] Back | [C] Cancel'
  printf 'Select [0-7]: '
  if ! IFS= read -r choice; then exit 0; fi
  case "$choice" in
    0|b|B|c|C) exit 0 ;;
    5|7) preflight ;;
    1|2|3|4|6)
      case "$choice" in
        1) OPERATION=install ;; 2) OPERATION=update ;;
        3) OPERATION=repair ;; 4) OPERATION=uninstall ;;
        6) OPERATION=rollback ;;
      esac
      blocked || : ;;
    '?') usage ;;
    *) printf '%s\n' 'Invalid selection; no operation performed.' ;;
  esac
  printf '\n'
done

  if [[ ! "$envelope" =~ $envelope_re ]]; then
    printf '%s\n' 'Publisher signature envelope not canonical' >&2
    return 3
  fi
  signature="${BASH_REMATCH[1]}"
  signer="${BASH_REMATCH[2]}"
  [[ "$signer" == "$PUBLISHER_SIGNER" ]] || return 3
  # Existing canonical PlatformReleaseManifest.digest is:
  # SHA256('aegis.platform.release.v1' + NUL + manifest canonical JSON).
  digest="$( { printf 'aegis.platform.release.v1\0'; cat -- "$manifest"; } | sha256sum)" || return 3
  digest="$(printf '%s' "$digest" | cut -c1-64)"
  work="$(mktemp -d)" || return 3
  chmod 700 -- "$work"
  # Owner-private temporary public signature/digest only; never owner secrets.
  if printf '%s' "$signature" | base64 -d >"$work/signature.bin" 2>/dev/null &&
     printf '%s' "$digest" >"$work/digest-ascii.txt" &&
     openssl pkeyutl -verify -pubin -inkey "$key_real" -rawin \
       -in "$work/digest-ascii.txt" -sigfile "$work/signature.bin" >/dev/null 2>&1; then
    rc=0
  fi
  rm -rf -- "$work"
  if ((rc)); then
    if ((JSON_MODE)); then
      printf '%s\n' '{"schema":"aegis.installer.publisher-check.v1","result":"REJECTED","signature_verified":false,"assets_verified":false,"owner_approved":false,"executed":false}'
    else printf '%s\n' 'RESULT=REJECTED' 'PUBLISHER_SIGNATURE=NOT_VERIFIED' 'NO_CHANGES_MADE=TRUE'
    fi
    return 3
  fi
  if ((JSON_MODE)); then
    printf '{"schema":"aegis.installer.publisher-check.v1","result":"SIGNED_MANIFEST_ONLY","manifest_sha256":"%s","signer_key_id":"%s","publisher_key_sha256":"%s","signature_verified":true,"assets_verified":false,"owner_approved":false,"executed":false,"core_activated":false}\n' "$digest" "$signer" "$hash"
  else
    printf '%s\n' 'RESULT=SIGNED_MANIFEST_ONLY' "MANIFEST_SHA256=$digest" "SIGNER_KEY_ID=$signer" 'ASSETS_VERIFIED=FALSE' 'INSTALL_AUTHORITY=NOT_CONNECTED' 'NO_CHANGES_MADE=TRUE'
  fi
  return 0
}

if [[ "$MODE" == help ]]; then usage; exit 0; fi
if [[ "$MODE" == publisher ]]; then verify_publisher_manifest; exit $?; fi
if [[ "$MODE" == seed ]]; then verify_seed_bytes; exit $?; fi
if [[ "$MODE" == check ]]; then readonly_preview; exit 0; fi
if [[ "$MODE" == operation ]]; then
  case "$OPERATION" in
    status|doctor) readonly_preview; exit 0 ;;
    *) blocked; exit 3 ;;
  esac
fi
if [[ "$JSON_MODE" -eq 1 || "$DRY_RUN" -eq 1 ]]; then
  printf '%s\n' '--json/--dry-run require --check or --operation' >&2
  exit 2
fi
if [[ ! -t 0 || ! -t 1 ]]; then
  printf '%s\n' 'Interactive setup requires a terminal. Use --check for read-only preflight.' >&2
  exit 2
fi

while :; do
  if [[ "$narrow" -eq 1 ]]; then
    printf '%s\n' 'AEGIS PLATFORM INSTALLER' 'PREVIEW ONLY / NO INSTALL AUTHORITY'
  else
    paint primary '+------------------------------------------------------------+'
    printf '\n'
    paint primary '|                AEGIS PLATFORM INSTALLER                    |'
    printf '\n'
    paint warning '|        PREVIEW ONLY / NO INSTALL AUTHORITY                 |'
    printf '\n'
    paint primary '+------------------------------------------------------------+'
    printf '\n'
  fi
  paint accent '[1]'; printf ' Install Platform (blocked)\n'
  paint accent '[2]'; printf ' Update Platform (blocked)\n'
  paint accent '[3]'; printf ' Repair Platform (blocked)\n'
  paint accent '[4]'; printf ' Uninstall Platform (blocked)\n'
  paint accent '[5]'; printf ' Diagnostics (read-only)\n'
  paint accent '[6]'; printf ' Rollback (blocked)\n'
  paint accent '[7]'; printf ' Status (unverified)\n'
  paint accent '[0]'; printf ' Exit\n'
  printf '%s\n' '[?] Help | [B] Back | [C] Cancel'
  printf 'Select [0-7]: '
  if ! IFS= read -r choice; then exit 0; fi
  case "$choice" in
    0|b|B|c|C) exit 0 ;;
    5|7) preflight ;;
    1|2|3|4|6)
      case "$choice" in
        1) OPERATION=install ;; 2) OPERATION=update ;;
        3) OPERATION=repair ;; 4) OPERATION=uninstall ;;
        6) OPERATION=rollback ;;
      esac
      blocked || : ;;
    '?') usage ;;
    *) printf '%s\n' 'Invalid selection; no operation performed.' ;;
  esac
  printf '\n'
done
