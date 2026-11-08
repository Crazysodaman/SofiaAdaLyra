#!/usr/bin/env bash
# AG-D011 Team E / IG-001: read-only Debian12 service/journal witness.
# Captures native systemd facts, NOT authenticated Platform READY or approval.
# Never executes an installer, changes owner state or prints journal content.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
if (($# != 2)) || [[ "$1" != '--expected-unit-sha256' ]] ||
   [[ ! "$2" =~ ^[0-9a-f]{64}$ ]]; then
  printf '%s\n' 'Usage: observe-debian12-service.sh --expected-unit-sha256 PINNED_HEX' >&2
  exit 2
fi
expected="$2"
unit=aegis-platform.service
path=/etc/systemd/system/aegis-platform.service
if [[ ! -r /etc/os-release ]]; then
  printf '%s\n' 'OS metadata unavailable' >&2; exit 3
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != debian || "${VERSION_ID:-}" != 12 ||
      "$(uname -m)" != x86_64 || ! -d /run/systemd/system ]]; then
  printf '%s\n' 'Only a running disposable Debian12 x86-64 systemd host can be observed' >&2
  exit 3
fi
if [[ ! -f "$path" || -L "$path" ||
      "$(realpath -ms -- "$path")" != "$(realpath -e -- "$path")" ]]; then
  printf '%s\n' 'Native service unit missing or redirected' >&2; exit 3
fi
observed="$(sha256sum -- "$path")" || exit 3
observed="${observed:0:64}"
if [[ "$observed" != "$expected" ]]; then
  printf '%s\n' 'Native systemd unit bytes disagree with independently pinned receipt' >&2
  exit 3
fi
fields="$(systemctl show "$unit" --no-pager \
  --property=LoadState,FragmentPath,ActiveState,SubState,MainPID,ExecMainStatus,NRestarts 2>/dev/null)" || exit 3
[[ "${#fields}" -le 8192 ]] || exit 3
load='' fragment='' active='' sub='' pid='' exitcode='' restarts=''
seen='|'
while IFS= read -r record; do
  [[ "$record" == *=* ]] || continue
  key="${record%%=*}"
  value="${record#*=}"
  if [[ "$seen" == *"|$key|"* ]]; then
    printf '%s\n' 'Duplicate native service field, refused' >&2
    exit 3
  fi
  seen+="$key|"
  case "$key" in
    LoadState) load="$value" ;;
    FragmentPath) fragment="$value" ;;
    ActiveState) active="$value" ;;
    SubState) sub="$value" ;;
    MainPID) pid="$value" ;;
    ExecMainStatus) exitcode="$value" ;;
    NRestarts) restarts="$value" ;;
    *) printf '%s\n' 'Unexpected systemctl field, refused' >&2; exit 3 ;;
  esac
done <<< "$fields"
if [[ "$load" != loaded || "$fragment" != "$path" ||
      ! "$pid" =~ ^[0-9]{1,12}$ || ! "$exitcode" =~ ^[0-9]{1,12}$ ||
      ! "$restarts" =~ ^[0-9]{1,12}$ ||
      ! "$active" =~ ^[a-z-]{1,24}$ || ! "$sub" =~ ^[a-z-]{1,24}$ ]]; then
  printf '%s\n' 'Native service origin/status missing or foreign' >&2; exit 3
fi
boot=''
if [[ -r /proc/sys/kernel/random/boot_id ]]; then
  IFS= read -r boot < /proc/sys/kernel/random/boot_id || true
fi
[[ "$boot" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || {
  printf '%s\n' 'Kernel boot identity unavailable' >&2; exit 3;
}
# Observe Team A's epoch-scoped operator sockets without claiming a
# currently enrolled operator, active RUN generation, or authenticated READY.
# Never open/connect to, chmod or unlink the socket.
runtime_dir=/run/aegis-platform
runtime_present=false
runtime_mode='UNKNOWN'
socket_count=0
socket_mode='UNKNOWN'
socket_owner_uid=0
socket_group_gid=0
if [[ -d "$runtime_dir" && ! -L "$runtime_dir" ]] &&
   [[ "$(realpath -ms -- "$runtime_dir")" == "$(realpath -e -- "$runtime_dir")" ]]; then
  candidate_mode="$(stat -c %a -- "$runtime_dir")" || exit 3
  if [[ "$candidate_mode" == 700 || "$candidate_mode" == 750 ]]; then
    runtime_present=true
    runtime_mode="$candidate_mode"
    for entry in "$runtime_dir"/mgmt-*.sock; do
      [[ -e "$entry" ]] || continue
      [[ ! -L "$entry" && -S "$entry" ]] || {
        printf '%s\\n' 'Management endpoint is redirected or not a Unix socket' >&2
        exit 3
      }
      basename="${entry##*/}"
      [[ "$basename" =~ ^mgmt-[1-9][0-9]{0,18}\\.sock$ ]] || {
        printf '%s\\n' 'Management endpoint has unreviewed epoch identity' >&2
        exit 3
      }
      ((socket_count+=1))
      if ((socket_count > 32)); then
        printf '%s\\n' 'Too many retained epoch-socket entries' >&2
        exit 3
      fi
      # Multiple stale epoch sockets may be left after crashes. They are
      # observations, not multiple active authoritative services.
      socket_mode="$(stat -c %a -- "$entry")" || exit 3
      socket_owner_uid="$(stat -c %u -- "$entry")" || exit 3
      socket_group_gid="$(stat -c %g -- "$entry")" || exit 3
      if [[ "$socket_mode" != 600 && "$socket_mode" != 660 ]]; then
        printf '%s\\n' 'Management socket has overly broad permissions' >&2
        exit 3
      fi
    done
  fi
fi
journal=''
if command -v journalctl >/dev/null 2>&1; then
  # Only a digest of at most 100 short-format records is exposed; never the
  # raw journal, whose entries may contain sensitive context or owner data.
  journal="$(journalctl --unit="$unit" --boot -n 100 --no-pager \
    --output=short-unix --quiet 2>/dev/null | sha256sum)" || journal=''
  if [[ -n "$journal" ]]; then journal="${journal:0:64}"; fi
fi
running=false
if [[ "$active" == active && "$sub" == running && "$pid" != 0 ]]; then
  running=true
fi
if [[ -z "$journal" ]]; then journal='UNAVAILABLE'; fi
printf '{"schema":"aegis.debian12.native-service-observation.v1","result":"%s","service":"aegis-platform.service","boot_id":"%s","unit_sha256":"%s","unit_digest_matches_external_receipt":true,"active_state":"%s","sub_state":"%s","main_pid":%s,"exec_main_status":%s,"restart_count":%s,"journal_sample_sha256":"%s","os_process_running":%s,"runtime_directory_observed":%s,"runtime_directory_mode":"%s","epoch_socket_count":%s,"last_socket_mode":"%s","last_socket_owner_uid":%s,"last_socket_group_gid":%s,"operator_socket_authenticated":false,"platform_ready_authenticated":false,"platform_uuid_authenticated":false,"operator_enrollment_authenticated":false,"owner_approved":false,"core_activated":false,"service_mutated":false}\n' \
  "$([[ "$running" == true ]] && printf 'OS_RUNNING_NOT_PLATFORM_READY' || printf 'NOT_RUNNING')" \
  "$boot" "$observed" "$active" "$sub" "$pid" "$exitcode" "$restarts" "$journal" "$running" \
  "$runtime_present" "$runtime_mode" "$socket_count" "$socket_mode" "$socket_owner_uid" "$socket_group_gid"
if [[ "$running" == true ]]; then exit 0; fi
exit 3
