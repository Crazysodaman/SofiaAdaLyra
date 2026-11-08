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
OPERATION=none

usage() {
  printf '%s\n' 'Aegis installer (PREVIEW ONLY)' \
    'Usage: install-aegis.sh [--check] [--no-color|--plain|--line-mode] [--json]' \
    '       install-aegis.sh --operation OP [--json] [--dry-run]' \
    'OP: status, doctor, install, update, repair, rollback, uninstall, purge' \
    'Mutation is BLOCKED until the signed OS executor and SAFE/STOP are connected.'
}

while (($#)); do
  case "$1" in
    --check) MODE=check; shift ;;
    --help|-h) MODE=help; shift ;;
    --no-color|--plain|--line-mode) PLAIN=1; shift ;;
    --json) JSON_MODE=1; shift ;;
    --dry-run) shift ;;
    --operation)
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

# Presentation manifest is never evaluated or sourced as executable code.
theme_hex() {
  local key="$1" value=''
  [[ -f "$THEME" ]] || return 1
  value="$(sed -nE "s/^[[:space:]]*\"$key\"[[:space:]]*:[[:space:]]*\"(#[0-9A-F]{6})\"[,[:space:]]*$/\1/p" "$THEME")"
  [[ "$value" =~ ^#[0-9A-F]{6}$ ]] || return 1
  printf '%s' "$value"
}

use_color=0
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

if [[ "$MODE" == help ]]; then usage; exit 0; fi
if [[ "$MODE" == check ]]; then readonly_preview; exit 0; fi
if [[ "$MODE" == operation ]]; then
  case "$OPERATION" in
    status|doctor) readonly_preview; exit 0 ;;
    *) blocked; exit 3 ;;
  esac
fi
if [[ "$JSON_MODE" -eq 1 ]]; then
  printf '%s\n' '--json requires --check or --operation' >&2
  exit 2
fi
if [[ ! -t 0 || ! -t 1 ]]; then
  printf '%s\n' 'Interactive setup requires a terminal. Use --check for read-only preflight.' >&2
  exit 2
fi

while :; do
  paint primary '+------------------------------------------------------------+'
  printf '\n'
  paint primary '|                AEGIS PLATFORM INSTALLER                    |'
  printf '\n'
  paint warning '|        PREVIEW ONLY / NO INSTALL AUTHORITY                 |'
  printf '\n'
  paint primary '+------------------------------------------------------------+'
  printf '\n'
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
