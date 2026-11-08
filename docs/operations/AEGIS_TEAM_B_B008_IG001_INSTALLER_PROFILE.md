# Team B B-008 | IG-001 verified B1/systemd native handoff

**Draft source only, NO-GO.** One Platform service, one canonical B1
installer, one existing Ed25519 publisher authority, one A SAFE/STOP owner
authority. No production/mainside mutations, Hub/Core start or duplicate writer.

## Exact critical-path source to overlay into Team E's combined checkout

The previous working B1 systemd signed source blob
\`9e74997004435d5ae6af34c8e0553db30e2fda53\` contained the
\`ProtectSystem=strict\` SQLite/WAL \`ReadWritePaths\` correction.
The B-008 version additionally checks dedicated \`aegis\` PRIMARY GID
on all private B1 code/state files and the kernel traverse permission on
*every ancestor ABOVE the signed release tree* (not just the bundled
runtime's internal directories). A foreign root-owned 0700
\`/opt/aegis/releases\` ancestor can otherwise prevent real native
ExecStart despite a correctly owned signed binary.

Overlay the **actual latest Team B Git blob** for
\`src/sofia/platform/ops/platform_installer_native_service.py\`, and its
exact sibling tests
\`test/test_ops_platform_installer_native_service.py\`, when creating the
next isolated IG-001 combined SHA. Do not overlay an old E008 tree or
weaken the existing \`ReadWritePaths\` / systemd safety flags.

The **native driver does not create users, chmod/chown foreign directories,
alter group membership or supply an owner authorization flag**.
Existing \`apply_owner_approved_native_service\` still consumes the
canonical B1 one-use SAFE approval and fences STOP, and remains inaccessible
from the unauthenticated Bash/PowerShell launchers.

## Original-repository test commands for Team E

On the new isolated full checkout with Python 3.12 and signed test fixtures:

\`\`\`bash
set -euo pipefail
git rev-parse HEAD
python -m pytest -q \
  test/test_ops_platform_installer_native_service.py \
  test/test_ops_platform_installer_native_transaction.py \
  test/test_ops_platform_installer_native_update.py \
  test/test_ops_platform_installation.py \
  test/test_platform_management_safe_service_e2e_linux.py
\`\`\`

New B-008 tests enforce: same exact \`aegis\` primary GID, private release
root and bundled Python ancestry, root-owned outer parent traversal,
restricted SQLite/WAL writable directory; signed existing unit denies
unrelated service adoption.

Profile reviewer and its tests (also source-only until independently run):
\`\`\`bash
python -m pytest -q test/test_ops_platform_installer_native_profile.py
\`\`\`

The new
\`sofia.platform.ops.platform_installer_native_profile.review_private_installed_linux_service\`
is a read-only, **internal** B1/OS review, not an installed profile
signer, service issuer, owner enrollment or login grant. It requires an
actual Debian12 host, existing canonical publisher verifier and B1
receipt, service account and private installed B1 file checks, actual
matching systemd unit with running process, active RUN lease, same
generation after re-read, no STOP, verified private socket
\`/run/aegis-platform/mgmt-<RUN-epoch>.sock\` with exact owner/service
primary GID 0700 parent and 0600 socket. It reads kernel inode/dev and
refuses socket replacement. Supervisor PID observed via systemctl is
**NOT** the Python AF_UNIX service peer PID: never claim those are the
same process or feed Rust a forged \`service_pid\`. The reviewer returns
\`service_pid=null\`; C's Rust SO_PEERCRED must independently check
service UID and primary GID and optional actual Python PID.

The review deliberately returns:
\`safe_owner_grant_verified=false\`,
\`external_operator_enrollment_verified=false\`,
\`publisher_revocation_current_verified=false\`,
\`authenticated_platform_ready_verified=false\`,
\`external_tui_activation_approved=false\`.
Neither local B1 SQL state nor an OS socket is the current Team A owner
grant or publisher revocation receipt. The current source supports only
private 0700/0600; the enrolled 0750/0660 external operator requires
A/C/E agreement, an explicitly provisioned \`aegis-mgmt\` GID and the
service's signed supplementary membership and current owner grant.

## E's real Debian12 host procedure (ONLY after separately authorized setup)

On an explicitly approved **disposable Debian 12 amd64 VM** with full
signed bundle and current A owner approval, **before** starting:

\`\`\`bash
# Verify the signed B1 unit, host ABI, service identity and path origin.
systemd-analyze verify /etc/systemd/system/aegis-platform.service
systemctl show aegis-platform.service \
  -p LoadState -p FragmentPath -p User -p Group \
  -p SupplementaryGroups -p RuntimeDirectory -p RuntimeDirectoryMode \
  -p ReadWritePaths -p ActiveState -p SubState -p MainPID
getent passwd aegis
getent group aegis
# Optional external operator enrollment only if explicitly signed/reviewed:
getent group aegis-mgmt
stat -c '%u:%g %a %n' /var/lib/aegis \
  /etc/systemd/system/aegis-platform.service
namei -l /opt/aegis/releases/REVIEWED_SIGNED_RELEASE_PATH
\`\`\`

Independently inspect all actual B1 receipt paths, including the bundled
Python runtime, and the *signed* entire chain of SHA256 artifacts; do not
assume the examples above are the installed paths. The SQLite state parent
must exactly match the sole \`ReadWritePaths\`, and must already be
private, service-owned and writable. No new permission is granted by
running these read-only commands.

After a **real A SAFE-approved** B1-native service install/start, capture:

\`\`\`bash
systemctl show aegis-platform.service \
  -p LoadState -p FragmentPath -p ActiveState -p SubState \
  -p MainPID -p Result -p ExecMainStatus -p NRestarts
journalctl -u aegis-platform.service -b -n 100 --no-pager
bash packaging/installers/observe-debian12-service.sh \
  --expected-unit-sha256 ACTUAL_SIGNED_B1_UNIT_SHA256
\`\`\`

Journal content may contain private context: retain raw output only in
the approved isolated E test environment, report bounded failure class
and hash externally. **Do not claim READY from \`ActiveState=active\`.**
A's authenticated, current SAFE-enrolled \`platform.status\` must bind
Platform UUID, RUN epoch, STOP, actual service UID/primary GID, operator
credential and socket inode. Stop/restart, stale socket, revoked grant,
foreign owner/group, duplicate writer and second boot must be witnessed.
Then C's compiled native Rust reader can be configured ONLY through an
independently reviewed installed B1 profile, not arbitrary CLI paths,
environment flags or unsigned Hub-provided identity.

## Actual local tests, NOT Debian12 installed-host acceptance

In the current Debian 13 container without a running systemd manager,
without GitHub clone/DNS or Rust/Cargo/QEMU, Team B executed:

- \`runuser -u nobody -- test -x <signed-like-file>\` under foreign
  0700 ancestor: correctly denied; after changing the ancestor to
  traversable 0711: allowed. Two genuine kernel-level tests passed.
- \`python3 -m pytest -q /tmp/test_aegis_b008_kernel.py\`:
  **5 passed in 0.09 s**. Real temporary AF_UNIX socket inode, service
  UID/GID/mode checks, wrong parent/socket mode rejection, foreign UID
  rejection and same-path socket replacement detection. These are
  independent OS semantic tests, **not** the original repository's
  \`test_ops_platform_installer_native_profile.py\` or host acceptance.
- Original-repository complete pytest and actual Debian12 installed
  systemd tests **NOT RUN**, unavailable checkout/guest/toolchain.

## Exact unsatisfied blockers

1. Only canonical **approved** publisher may issue actual Ed25519 whole
   capsule and manifest signatures; the draft has no approved publisher
   key, fresh signed revocation status or independent real packaged
   native installer SHA256. Synthetic CI keys never count as release.
2. The self-contained, stock-Debian12 verifier/extractor must establish
   independent root trust and full signed asset closure before bundled
   interpreter execution. OpenSSL and unzip must be explicitly present
   or provisioned from independently signed offline OS media, never via
   silent WAN or unsigned fallback.
3. A actual SAFE owner enrollment and one-use native install/STOP
   proof with exact service UID/GID/operator endpoint, and B signed
   provisioning of those principals and full runtime/state paths, is
   still missing for live host execution.
4. No approved disposable Debian12 installed host or original-repo
   build/Rust toolchain is available in this environment. No genuine
   B-008 journal, READY, signer receipt, reboot/UUID or C TUI live
   status evidence can be claimed.
5. Team E must overlay the exact current B blobs and run the next
   first failing original-repo assertion in the E009 isolated tree.
   Full exact-combined-SHA CI remains an IG-001 milestone gate,
   not development waiting.

**Platform 1.0 NO-GO. No merge/main/production/Core/Hub mutations.**
