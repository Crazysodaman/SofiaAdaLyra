#!/usr/bin/env bash
# Aegis Platform installer shell, Phase UX-1: read-only preflight.
# This entrypoint never elevates or changes services. Installation requires
# the signed-release verification and owner-authorized executor in #201.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/../.." && pwd -P)"
THEME="$ROOT/contracts/ui/aegis-theme-v1.json"
MODE=menu
PLAIN=0

usage() {
  printf '%s\n' 'Aegis installer preflight (PREVIEW ONLY)' \
    'Usage: install-aegis.sh [--check | --help | --no-color]' \
    'No install/update/repair/uninstall action is enabled yet.'
}

for arg in "$@"; do
  case "$arg" in
    --check) MODE=check ;;
    --help|-h) MODE=help ;;
    --no-color|--plain) PLAIN=1 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
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
if [[ "$PLAIN" -eq 0 && -t 1 && ! -v NO_COLOR &&
      "$(printenv TERM || printf dumb)" != dumb &&
      "$(printenv COLORTERM || true)" =~ (truecolor|24bit) ]]; then
  use_color=1
fi

paint() {
  local role="$1" label="$2" hex r g b
  if [[ "$use_color" -eq 1 ]] && hex="$(theme_hex "$role")"; then
    r=$(printf '%d' "0x$(printf %s "$hex" | cut -c2-3)")
    g=$(printf '%d' "0x$(printf %s "$hex" | cut -c4-5)")
    b=$(printf '%d' "0x$(printf %s "$hex" | cut -c6-7)")
    printf '\033[38;2;%d;%d;%dm%s\033[0m' "$r" "$g" "$b" "$label"
  else
    printf '%s' "$label"
  fi
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

if [[ "$MODE" == help ]]; then usage; exit 0; fi
if [[ "$MODE" == check ]]; then preflight; exit 0; fi

if [[ ! -t 0 || ! -t 1 ]]; then
  printf '%s\n' 'Interactive setup requires a terminal. Use --check for read-only preflight.' >&2
  exit 2
fi

while :; do
  paint primary 'AEGIS PLATFORM | INSTALLATION WIZARD'
  printf '\n'
  printf '%s\n' 'PREVIEW ONLY | SIGNED INSTALLER BACKEND NOT CONNECTED'
  paint accent '[1]'
  printf '%s\n' ' Check prerequisites (read-only)'
  paint accent '[2]'
  printf '%s\n' ' Install Platform (blocked pending signed executor)'
  paint accent '[3]'
  printf '%s\n' ' Update / repair / rollback (blocked)'
  paint accent '[4]'
  printf '%s\n' ' Uninstall Platform (blocked)'
  paint accent '[0]'
  printf '%s\n' ' Exit'
  printf 'Select [0-4]: '
  if ! IFS= read -r choice; then exit 0; fi
  case "$choice" in
    0) exit 0 ;;
    1) preflight ;;
    2|3|4) printf '%s\n' 'BLOCKED: no verified release, owner approval, or installed service executor.' ;;
    *) printf '%s\n' 'Invalid selection; no operation performed.' ;;
  esac
  printf '\n'
done
