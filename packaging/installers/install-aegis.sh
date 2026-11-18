#!/usr/bin/env bash
# Aegis Platform one-step installer shell entrypoint.
#
# Default execution starts the real guided installation through the bundled
# runtime Python and the canonical guided orchestrator. This shell only:
#
#   - locates the adjacent signed release bundle and bundled runtime,
#   - requires the independently provisioned installer trust anchor
#     (installer/trusted-publisher.pem and installer/trust.json),
#   - re-executes itself through sudo when OS privilege is required,
#   - forwards --check, --operation, --json and --no-color.
#
# Signature, publisher, revocation, SAFE/STOP, owner approval and lifecycle
# semantics remain mandatory in the orchestrator. This entrypoint never accepts
# a manual approval id, Python path or service command, never adds an
# authorization bypass and never changes a service itself.
#
# Safe read-only --verify-seed / --verify-publisher and inert signed-media
# staging modes remain available; they are not the default installer.
set -euo pipefail

SCRIPT_ARGS=("$@")
SCRIPT_PATH="$(cd -- "$(dirname -- "$0")" && pwd -P)/$(basename -- "$0")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)"
if [[ -f "$SCRIPT_DIR/contracts/ui/aegis-theme-v1.json" ]]; then
  ROOT="$SCRIPT_DIR"
else
  ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
fi
THEME="$ROOT/contracts/ui/aegis-theme-v1.json"

MODE=guided
PLAIN=0
JSON_MODE=0
CHECK_REQUESTED=0
OPERATION_REQUESTED=0
DRY_RUN=0
OPERATION=none
BUNDLE_ROOT_OVERRIDE=''
BUNDLE_ROOT=''
RESOLVED_BUNDLE_ROOT=''
RESOLVED_TRUST_DIR=''
RESOLVED_PYTHON=''
LAST_ERROR=''
SEED_ARCHIVE=''
SEED_SHA256=''
SEED_REQUESTED=0
PUBLISHER_REQUESTED=0
RELEASE_ROOT=''
PUBLISHER_KEY=''
PUBLISHER_FINGERPRINT=''
PUBLISHER_SIGNER=''
CAPSULE_STAGE_REQUESTED=0
CAPSULE_ARCHIVE=''
CAPSULE_SIGNATURE=''
CAPSULE_DESTINATION=''

usage() {
  printf '%s\n' 'Aegis Platform one-step installer' \
    'Usage: install-aegis.sh                 # guided install through UAC-equivalent sudo' \
    '       install-aegis.sh --check [--json] [--no-color]' \
    '       install-aegis.sh --operation OP [--json] [--no-color]' \
    '       install-aegis.sh --verify-seed FILE --trusted-seed-sha256 HEX [--json]' \
    '       install-aegis.sh --verify-publisher DIR --publisher-key PEM --publisher-sha256 HEX --publisher-signer ID [--json]' \
    '       install-aegis.sh --stage-capsule ZIP --capsule-signature RAW64 --publisher-key PEM --publisher-sha256 HEX --publisher-signer ID --staging-destination NEW_PRIVATE_DIR' \
    'OP: verify, status, doctor, install, update, repair, rollback, uninstall, reinstall, reconcile, purge' \
    'The release bundle, trust anchor and bundled Python are discovered relative to this script.' \
    'No manual hash, approval id, Python path or service command is accepted for guided installation.'
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

guided_failure() {
  local message="$1"
  if ((JSON_MODE)); then
    printf '{"schema":"aegis.installer.guided-launcher.v1","result":"BLOCKED","message":"%s","executed":false,"owner_approved":false,"core_activated":false}\n' \
      "$(json_escape "$message")"
  else
    printf 'AEGIS SETUP BLOCKED: %s\n' "$message" >&2
  fi
}

while (($#)); do
  case "$1" in
    --check) MODE=check; CHECK_REQUESTED=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --operation)
      if ((OPERATION_REQUESTED)); then printf '%s\n' 'Operation specified twice' >&2; exit 2; fi
      OPERATION_REQUESTED=1
      if (($# < 2)); then printf '%s\n' 'Missing operation' >&2; exit 2; fi
      OPERATION="$2"
      case "$OPERATION" in
        verify|status|doctor|install|update|repair|rollback|uninstall|reinstall|reconcile|purge) ;;
        *) printf '%s\n' 'Unknown operation' >&2; exit 2 ;;
      esac
      MODE=operation; shift 2 ;;
    --bundle-root)
      if [[ -n "$BUNDLE_ROOT_OVERRIDE" ]] || (($# < 2)); then printf '%s\n' 'Invalid bundle root' >&2; exit 2; fi
      BUNDLE_ROOT_OVERRIDE="$2"; shift 2 ;;
    --verify-publisher)
      if ((PUBLISHER_REQUESTED)) || (($# < 2)); then printf '%s\n' 'Invalid publisher request' >&2; exit 2; fi
      PUBLISHER_REQUESTED=1; MODE=publisher; RELEASE_ROOT="$2"; shift 2 ;;
    --stage-capsule)
      if ((CAPSULE_STAGE_REQUESTED)) || (($# < 2)); then printf '%s\n' 'Invalid capsule stage request' >&2; exit 2; fi
      CAPSULE_STAGE_REQUESTED=1; MODE=capsule_stage; CAPSULE_ARCHIVE="$2"; shift 2 ;;
    --capsule-signature)
      if [[ -n "$CAPSULE_SIGNATURE" ]] || (($# < 2)); then printf '%s\n' 'Invalid capsule signature' >&2; exit 2; fi
      CAPSULE_SIGNATURE="$2"; shift 2 ;;
    --staging-destination)
      if [[ -n "$CAPSULE_DESTINATION" ]] || (($# < 2)); then printf '%s\n' 'Invalid capsule staging target' >&2; exit 2; fi
      CAPSULE_DESTINATION="$2"; shift 2 ;;
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
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

if ((DRY_RUN)) && [[ "$MODE" == guided ]]; then
  if ((OPERATION_REQUESTED)); then
    printf '%s\n' '--dry-run cannot be combined with --operation' >&2
    exit 2
  fi
  CHECK_REQUESTED=1
  MODE=check
fi

if ((CHECK_REQUESTED && OPERATION_REQUESTED)); then
  printf '%s\n' '--check cannot be combined with --operation' >&2
  exit 2
fi
if ((SEED_REQUESTED && (CHECK_REQUESTED || OPERATION_REQUESTED || DRY_RUN))); then
  printf '%s\n' 'Ambiguous operation or seed flags' >&2
  exit 2
fi
if [[ -n "$SEED_SHA256" && "$SEED_REQUESTED" -eq 0 ]]; then
  printf '%s\n' '--trusted-seed-sha256 requires --verify-seed' >&2; exit 2
fi
if ((PUBLISHER_REQUESTED && (CHECK_REQUESTED || OPERATION_REQUESTED || SEED_REQUESTED || DRY_RUN))); then
  printf '%s\n' 'Publisher signature check cannot authorize a protected operation' >&2
  exit 2
fi
if (( !PUBLISHER_REQUESTED && !CAPSULE_STAGE_REQUESTED )) && [[ -n "$PUBLISHER_KEY" || -n "$PUBLISHER_FINGERPRINT" || -n "$PUBLISHER_SIGNER" ]]; then
  printf '%s\n' 'Publisher trust flags require --verify-publisher or --stage-capsule' >&2
  exit 2
fi
if ((PUBLISHER_REQUESTED)) && [[ -n "$SEED_SHA256" ]]; then
  printf '%s\n' 'Publisher mode cannot be mixed with seed mode' >&2
  exit 2
fi
if ((CAPSULE_STAGE_REQUESTED)); then
  if ((PUBLISHER_REQUESTED || SEED_REQUESTED || CHECK_REQUESTED ||
        OPERATION_REQUESTED || DRY_RUN)) ||
     [[ -n "$SEED_SHA256" || -n "$RELEASE_ROOT" ||
        -z "$CAPSULE_SIGNATURE" || -z "$CAPSULE_DESTINATION" ||
        -z "$PUBLISHER_KEY" || -z "$PUBLISHER_FINGERPRINT" ||
        -z "$PUBLISHER_SIGNER" ]]; then
    printf '%s\n' 'Capsule staging requires exact independent publisher parameters' >&2
    exit 2
  fi
elif [[ -n "$CAPSULE_SIGNATURE" || -n "$CAPSULE_DESTINATION" ]]; then
  printf '%s\n' 'Capsule signature and destination require --stage-capsule' >&2
  exit 2
fi

resolve_bundle_root() {
  RESOLVED_BUNDLE_ROOT=''
  LAST_ERROR=''
  local explicit="$1" candidate real parent
  if [[ -n "$explicit" ]]; then
    if [[ ! -d "$explicit" || -L "$explicit" ]]; then
      LAST_ERROR='Installer release root is unavailable or redirected.'
      return 2
    fi
    real="$(realpath -e -- "$explicit")" || {
      LAST_ERROR='Installer release root path is unavailable.'
      return 2
    }
    if [[ "$(realpath -ms -- "$explicit")" != "$real" ]]; then
      LAST_ERROR='Installer release root contains a symbolic link or escape.'
      return 2
    fi
    if [[ ! -f "$real/release-manifest.json" || -L "$real/release-manifest.json" ]]; then
      LAST_ERROR='Installer release root does not contain release-manifest.json.'
      return 2
    fi
    RESOLVED_BUNDLE_ROOT="$real"
    return 0
  fi
  parent="$(dirname -- "$SCRIPT_DIR")"
  # Installable bundles keep signed media in <bundle>/release and the
  # independent installer trust in <bundle>/installer. Prefer that outer
  # bundle root so discover_bundle can see both.
  for candidate in "$SCRIPT_DIR" "$parent"; do
    if [[ -f "$candidate/release/release-manifest.json" &&
          ! -L "$candidate/release/release-manifest.json" ]]; then
      real="$(realpath -e -- "$candidate")" || {
        LAST_ERROR='Installer release root path is unavailable.'
        return 2
      }
      if [[ "$(realpath -ms -- "$candidate")" != "$real" ]]; then
        LAST_ERROR='Installer release root contains a symbolic link or escape.'
        return 2
      fi
      RESOLVED_BUNDLE_ROOT="$real"
      return 0
    fi
  done
  for candidate in "$SCRIPT_DIR" "$SCRIPT_DIR/release" "$SCRIPT_DIR/bundle" \
      "$parent" "$parent/release" "$parent/bundle"; do
    if [[ -f "$candidate/release-manifest.json" && ! -L "$candidate/release-manifest.json" ]]; then
      real="$(realpath -e -- "$candidate")" || {
        LAST_ERROR='Installer release root path is unavailable.'
        return 2
      }
      if [[ "$(realpath -ms -- "$candidate")" != "$real" ]]; then
        LAST_ERROR='Installer release root contains a symbolic link or escape.'
        return 2
      fi
      RESOLVED_BUNDLE_ROOT="$real"
      return 0
    fi
  done
  LAST_ERROR='Aegis release bundle not found. Expected release-manifest.json next to the installer, in its parent directory, or in ./release or ./bundle. Re-download the complete signed setup media.'
  return 2
}

resolve_trust_directory() {
  RESOLVED_TRUST_DIR=''
  LAST_ERROR=''
  local root="$1" candidate real
  for candidate in "$root/installer" "$SCRIPT_DIR" "$SCRIPT_DIR/installer"; do
    if [[ -f "$candidate/trusted-publisher.pem" && ! -L "$candidate/trusted-publisher.pem" &&
          -f "$candidate/trust.json" && ! -L "$candidate/trust.json" ]]; then
      real="$(realpath -e -- "$candidate")" || {
        LAST_ERROR='Installer trust anchor path is unavailable.'
        return 2
      }
      if [[ "$(realpath -ms -- "$candidate")" != "$real" ]]; then
        LAST_ERROR='Installer trust anchor contains a symbolic link or escape.'
        return 2
      fi
      RESOLVED_TRUST_DIR="$real"
      return 0
    fi
  done
  LAST_ERROR='Independent installer trust anchor missing. Provision installer/trusted-publisher.pem and installer/trust.json out of band before running setup. Do not derive publisher trust from the release bundle or its signature.'
  return 2
}

assert_trust_anchor() {
  local root="$1" directory file actual size maximum name
  resolve_trust_directory "$root" || return 2
  directory="$RESOLVED_TRUST_DIR"
  for file in "$directory/trusted-publisher.pem" "$directory/trust.json"; do
    name="$(basename -- "$file")"
    if [[ ! -f "$file" || -L "$file" ]]; then
      LAST_ERROR='Installer trust anchor is not an ordinary file: '"$name"
      return 2
    fi
    actual="$(realpath -e -- "$file")" || {
      LAST_ERROR='Installer trust anchor path is unavailable: '"$name"
      return 2
    }
    if [[ "$(realpath -ms -- "$file")" != "$actual" ]]; then
      LAST_ERROR='Installer trust anchor contains a symbolic link or escape: '"$name"
      return 2
    fi
    size="$(stat -c '%s' -- "$actual")" || {
      LAST_ERROR='Installer trust anchor cannot be measured: '"$name"
      return 2
    }
    case "$name" in
      trusted-publisher.pem) maximum=16384 ;;
      trust.json) maximum=65536 ;;
      *) LAST_ERROR='Unexpected installer trust anchor file.'; return 2 ;;
    esac
    if [[ ! "$size" =~ ^[0-9]+$ ]] || ((size < 1 || size > maximum)); then
      LAST_ERROR='Installer trust anchor is empty or outside bounded size: '"$name"
      return 2
    fi
  done
  return 0
}

resolve_bundled_python() {
  RESOLVED_PYTHON=''
  LAST_ERROR=''
  local root="$1" root_real os arch rel candidate actual
  local found=()
  if [[ ! -d "$root" || -L "$root" ]]; then
    LAST_ERROR='Bundled runtime release root is unavailable or redirected.'
    return 2
  fi
  root_real="$(realpath -e -- "$root")" || {
    LAST_ERROR='Bundled runtime release root is unavailable.'
    return 2
  }
  if [[ "$(realpath -ms -- "$root")" != "$root_real" ]]; then
    LAST_ERROR='Bundled runtime release root contains a symlinked path component.'
    return 2
  fi
  os="$(uname -s 2>/dev/null || true)"
  arch="$(uname -m 2>/dev/null || true)"
  if [[ "$os" != Linux ]]; then
    LAST_ERROR='Bundled Debian runtime discovery requires a Linux host.'
    return 2
  fi
  case "$arch" in
    x86_64|amd64) ;;
    *)
      LAST_ERROR='Bundled Debian runtime discovery requires x86_64 Linux.'
      return 2
      ;;
  esac
  for rel in runtime/python/python.exe; do
    if [[ -e "$root_real/$rel" || -L "$root_real/$rel" ]]; then
      LAST_ERROR='Bundled runtime layout does not match the host operating system.'
      return 2
    fi
  done
  for rel in runtime/python/bin/python3.12 runtime/python/bin/python3; do
    candidate="$root_real/$rel"
    if [[ -e "$candidate" || -L "$candidate" ]]; then
      if [[ ! -f "$candidate" || -L "$candidate" ]]; then
        LAST_ERROR='Bundled Python is not a regular non-symlinked file.'
        return 2
      fi
      actual="$(realpath -e -- "$candidate")" || {
        LAST_ERROR='Bundled Python path is unavailable.'
        return 2
      }
      if [[ "$(realpath -ms -- "$candidate")" != "$actual" ]]; then
        LAST_ERROR='Bundled Python path contains a symlink or escape.'
        return 2
      fi
      case "$actual" in
        "$root_real"/*) ;;
        *)
          LAST_ERROR='Bundled Python resolves outside the release root.'
          return 2
          ;;
      esac
      if [[ ! -x "$actual" ]]; then
        LAST_ERROR='Bundled Python is not executable.'
        return 2
      fi
      found+=("$actual")
    fi
  done
  if ((${#found[@]} != 1)); then
    LAST_ERROR='Exactly one bundled Python runtime must exist inside the release root.'
    return 2
  fi
  RESOLVED_PYTHON="${found[0]}"
  return 0
}

requires_elevation() {
  if ((CHECK_REQUESTED)); then return 1; fi
  case "$MODE" in
    guided) return 0 ;;
    operation)
      case "$OPERATION" in
        verify|status|doctor) return 1 ;;
        *) return 0 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}

theme_hex() {
  local key="$1" value=''
  [[ -f "$THEME" ]] || return 1
  value="$(sed -nE "s/^[[:space:]]*\"$key\"[[:space:]]*:[[:space:]]*\"(#[0-9A-F]{6})\"[,[:space:]]*$/\1/p" "$THEME")"
  [[ "$value" =~ ^#[0-9A-F]{6}$ ]] || return 1
  printf '%s' "$value"
}

use_color=0
narrow=0
if [[ "$PLAIN" -eq 0 && "$JSON_MODE" -eq 0 && -t 0 && -t 1 && ! -v NO_COLOR &&
      "$(printenv TERM || printf dumb)" != dumb ]]; then
  if [[ "$(printenv COLORTERM || true)" =~ (truecolor|24bit) ]]; then
    use_color=3
  elif [[ "$(printenv TERM || true)" == *256color* ]]; then
    use_color=2
  else
    use_color=1
  fi
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

show_guided_banner() {
  if ((JSON_MODE)); then return; fi
  if [[ "$narrow" -eq 1 ]]; then
    printf '%s\n' 'AEGIS GUIDED PLATFORM INSTALLER' "RELEASE_BUNDLE=$BUNDLE_ROOT"
  else
    paint primary 'AEGIS GUIDED PLATFORM INSTALLER'
    printf '\n'
    paint accent "RELEASE_BUNDLE=$BUNDLE_ROOT"
    printf '\n'
  fi
  if ((CHECK_REQUESTED)); then
    paint warning 'MODE=CHECK (read-only preview)'
    printf '\n'
  elif [[ "$OPERATION" != none ]]; then
    paint accent "MODE=OPERATION $OPERATION"
    printf '\n'
  else
    paint accent 'MODE=INSTALL'
    printf '\n'
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
  envelope="$(cat -- "$envelope_file")" || return 3
  local observed_envelope_bytes
  observed_envelope_bytes="$(printf '%s' "$envelope" | wc -c)" || return 3
  [[ "$observed_envelope_bytes" -eq "$envelope_size" ]] || {
    printf '%s\n' 'Signature envelope contains noncanonical trailing or binary bytes' >&2
    return 3
  }
  local envelope_re='^\{"signature_b64":"([A-Za-z0-9+/]{86}==)","signer_key_id":"([A-Za-z0-9_.-]{1,128})"\}$'
  if [[ ! "$envelope" =~ $envelope_re ]]; then
    printf '%s\n' 'Publisher signature envelope not canonical' >&2
    return 3
  fi
  signature="${BASH_REMATCH[1]}"
  signer="${BASH_REMATCH[2]}"
  [[ "$signer" == "$PUBLISHER_SIGNER" ]] || return 3
  digest="$( { printf 'aegis.platform.release.v1\0'; cat -- "$manifest"; } | sha256sum)" || return 3
  digest="$(printf '%s' "$digest" | cut -c1-64)"
  work="$(mktemp -d)" || return 3
  chmod 700 -- "$work"
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

run_guided() {
  if ! resolve_bundle_root "$BUNDLE_ROOT_OVERRIDE"; then
    guided_failure "$LAST_ERROR"
    exit 2
  fi
  BUNDLE_ROOT="$RESOLVED_BUNDLE_ROOT"
  if ! assert_trust_anchor "$BUNDLE_ROOT"; then
    guided_failure "$LAST_ERROR"
    exit 2
  fi
  if ! resolve_bundled_python "$BUNDLE_ROOT"; then
    guided_failure "$LAST_ERROR"
    exit 2
  fi

  if requires_elevation; then
    if [[ "$(id -u)" -ne 0 ]]; then
      if ! command -v sudo >/dev/null 2>&1; then
        guided_failure 'Administrator privilege is required and sudo is unavailable. Run setup from an administrator account with the approved OS privilege mechanism.'
        exit 2
      fi
      # Approved OS mechanism: re-exec this exact script through sudo with the
      # caller's arguments unchanged. The orchestrator still owns SAFE/STOP and
      # owner approval; sudo is not installation authority.
      exec sudo -- "$SCRIPT_PATH" "${SCRIPT_ARGS[@]}"
    fi
  fi

  show_guided_banner
  local -a guided_args=(--bundle-root "$BUNDLE_ROOT")
  if ((CHECK_REQUESTED)); then guided_args+=(--check); fi
  if [[ "$OPERATION" != none ]]; then guided_args+=(--operation "$OPERATION"); fi
  if ((JSON_MODE)); then guided_args+=(--json); fi
  if ((PLAIN)) || [[ -n "${NO_COLOR:-}" ]]; then guided_args+=(--no-color); fi

  set +e
  "$RESOLVED_PYTHON" -E -s -P -B -m sofia.platform.ops.platform_installer_guided "${guided_args[@]}"
  local status=$?
  set -e
  if ((status != 0)) && ((JSON_MODE == 0)); then
    printf 'AEGIS SETUP FAILED: the guided installer exited with code %s. Review the message above; setup did not retry or hide a failed step.\n' "$status" >&2
  fi
  exit "$status"
}

if [[ "$MODE" == help ]]; then usage; exit 0; fi
if [[ "$MODE" == seed ]]; then verify_seed_bytes; exit $?; fi
if [[ "$MODE" == publisher ]]; then verify_publisher_manifest; exit $?; fi
if [[ "$MODE" == capsule_stage ]]; then
  # Inert, owner-private disk staging only. No escalation, SAFE bypass,
  # service registration, release installation, Core or Fleet enrollment.
  bash "$SCRIPT_DIR/stage-aegis-capsule.sh" \
    --capsule "$CAPSULE_ARCHIVE" --signature "$CAPSULE_SIGNATURE" \
    --publisher-key "$PUBLISHER_KEY" --publisher-sha256 "$PUBLISHER_FINGERPRINT" \
    --publisher-signer "$PUBLISHER_SIGNER" --destination "$CAPSULE_DESTINATION"
  exit $?
fi
run_guided
