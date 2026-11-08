#!/usr/bin/env bash
# AG-D011 read-only native Debian 12 stock-host prerequisites.
# NOT an installer, signer, publisher-root admission or SAFE owner grant.
# No network, package installation, PATH overrides from a caller, service
# mutation, identity creation or release execution.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
if (($# > 1)) || { (($# == 1)) && [[ "$1" != '--json' && "$1" != '--plain' ]]; }; then
  printf '%s\n' 'Usage: debian12-offline-prerequisites.sh [--json|--plain]' >&2
  exit 2
fi
mode=json
if (($# == 1)); then mode="${1#--}"; fi
os_debian12=false
architecture_amd64=false
openssl_ed25519=false
systemd_manager=false
missing=''
if [[ -r /etc/os-release ]]; then
  # /etc/os-release is local OS metadata, not a publisher/owner authority.
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" == debian && "${VERSION_ID:-}" == 12 ]]; then os_debian12=true; fi
fi
if [[ "$(uname -m)" == x86_64 ]]; then architecture_amd64=true; fi
required=(bash sha256sum base64 stat realpath openssl systemctl getent id
          install flock timeout readlink mktemp chmod)
for binary in "${required[@]}"; do
  if ! command -v "$binary" >/dev/null 2>&1; then
    if [[ -n "$missing" ]]; then missing+=','; fi
    missing+="$binary"
  fi
done
if [[ "$missing" != *,openssl,* && "$missing" != openssl && "$missing" != *,openssl ]] &&
   command -v openssl >/dev/null 2>&1; then
  algorithms="$(openssl list -public-key-algorithms 2>/dev/null || true)"
  if [[ "${algorithms,,}" == *ed25519* ]] &&
     openssl pkeyutl -help >/dev/null 2>&1; then
    openssl_ed25519=true
  fi
fi
if command -v systemctl >/dev/null 2>&1 &&
   [[ -d /run/systemd/system ]] &&
   systemctl show --property=Version --value >/dev/null 2>&1; then
  systemd_manager=true
fi
ready=false
if [[ "$os_debian12" == true && "$architecture_amd64" == true &&
      "$openssl_ed25519" == true && "$systemd_manager" == true &&
      -z "$missing" ]]; then ready=true; fi
if [[ "$mode" == json ]]; then
  # Missing binary names come exclusively from the fixed allowlist above.
  printf '{"schema":"aegis.installer.debian12-offline-prerequisites.v1","result":"%s","debian12":%s,"x86_64":%s,"openssl_ed25519":%s,"systemd_manager":%s,"missing_binaries":"%s","network_requested":false,"download_performed":false,"publisher_trust_verified":false,"owner_authorized":false,"service_mutated":false,"core_activated":false}\n' \
    "$([[ "$ready" == true ]] && printf 'PREREQUISITES_PRESENT_ONLY' || printf 'BLOCKED')" \
    "$os_debian12" "$architecture_amd64" "$openssl_ed25519" "$systemd_manager" "$missing"
else
  printf 'RESULT=%s\nDEBIAN12=%s\nX86_64=%s\nOPENSSL_ED25519=%s\nSYSTEMD_MANAGER=%s\nMISSING_BINARIES=%s\nPUBLISHER_TRUST=NOT_VERIFIED\nINSTALL_AUTHORITY=NOT_CONNECTED\nSERVICE_MUTATION=FALSE\n' \
    "$([[ "$ready" == true ]] && printf 'PREREQUISITES_PRESENT_ONLY' || printf 'BLOCKED')" \
    "$os_debian12" "$architecture_amd64" "$openssl_ed25519" "$systemd_manager" "$missing"
fi
if [[ "$ready" == true ]]; then exit 0; fi
exit 3
