# IG-001 | Team B native Debian SQLite state READY blocker

**Status:** isolated draft PR #244, implementation changed; native Debian 12
installed-host READY remains NOT EXECUTED and release remains NO-GO.

## First concrete Team B startup defect corrected

The generated `aegis-platform.service` uses `ProtectSystem=strict`.
Before the IG-001 correction it lacked any `ReadWritePaths=` carve-out or
`StateDirectory=` for the existing canonical `PlatformLocalStore` SQLite
database. The Core-free Python worker acquires a process lock, writes
SQLite/WAL/SHM and renews its RUN lease in the B1-selected state directory.
Even if signed B1 binaries exist and the service account can read them, a
strict read-only systemd filesystem sandbox can prevent that worker from
reaching genuine READY.

`src/sofia/platform/ops/platform_installer_native_service.py` now emits
exactly one write exception:
`ReadWritePaths=<SIGNED_B1_LOCAL_STATE_PARENT>`.

No permission is granted to `/`, `/var`, `/opt`, `/home`,
the Core state or the signer. It verifies the exact state parent is already
a private, owner-traversable and **owner-writable** directory owned by the
dedicated non-root `aegis` UID before writing a native unit. It also
rechecks every signed runtime/interpreter ancestor before registration.
No implicit `chown`, user creation, ACL broadening, socket mutation or
owner permission bypass occurs.

**Source regression tests, not locally run from full checkout:**

- `test_systemd_strict_sandbox_allows_only_verified_platform_state_wal_path`
- `test_systemd_refuses_nonwritable_or_foreign_sqlite_parent[wrong-uid]`
- `test_systemd_refuses_nonwritable_or_foreign_sqlite_parent[not-writable]`

## Actual local OS checks (Debian 13 disposable container)

Local host is **Debian 13**, not Debian 12 systemd PID1, and GitHub checkout
is not mounted (direct GitHub DNS fails). No production or external
service was touched.

- A source-equivalent generated unit with `ProtectSystem=strict`,
  exactly `ReadWritePaths=/var/lib/aegis`, and `RuntimeDirectoryMode=0700`
  was passed to `systemd-analyze verify`: **exit code 0**.
  Local independent source-equivalent single exception, no broad-path,
  service/group/runtime-mode assertions: **PASS**.
- Actual kernel non-root `nobody` process executed SQLite WAL creation
  and insert using a dedicated 0700 owned directory: **PASS**.
  Changing its state directory to mode 0500 caused
  `sqlite3.OperationalError: attempt to write a readonly database`,
  process exit 1, as expected: **denial PASS**.
- A Python 3.13 parsing/execution sanity check verified adjacent literal
  concatenation in the updated service-unit string: **PASS**.

These results validate OS assumptions and systemd fragment syntax.
They do **not** prove execution of the original repository's pytest,
a Debian 12 host with active systemd, Team A owner enrollment/SAFE
or genuine Platform READY.

## Team E current combined checkout instructions

Use the isolated current Team B SHA and latest precise Team A/C/D sources
as reconciled by Team E. The target is an **explicitly authorized disposable
Debian 12 amd64 system**, never protected Venus/Artemis/Sofia VM.

```bash
set -euo pipefail
git rev-parse HEAD
python -m pytest -q \
  test/test_ops_platform_installer_native_service.py \
  test/test_ops_platform_installer_native_transaction.py \
  test/test_ops_platform_installer_native_update.py \
  test/test_ops_platform_installation.py \
  test/test_platform_service_session.py

# After verified publisher/B1 install AND attended current Team A
# owner enrollment and one-use SAFE approval, inspect the generated
# native unit before any authorized start:
systemd-analyze verify /etc/systemd/system/aegis-platform.service
grep -F 'ProtectSystem=strict' /etc/systemd/system/aegis-platform.service
grep -F 'ReadWritePaths=' /etc/systemd/system/aegis-platform.service
systemctl show aegis-platform.service \
  --property=LoadState,FragmentPath,ActiveState,SubState,MainPID,Result,ExecMainStatus
```

The exact state-directory write exception must match the reviewed signed B1
installation receipt. Verify the directory's actual service UID/GID,
owner-only 0700, writable mode and no redirection. Team A's native
broker owns authoritative owner enrollment/STOP/revocation and current
`platform.status`. Only that authenticated fresh response can assert
READY, RUN generation and Platform UUID; `systemd active` alone cannot.

**Remaining blockers:** production-approved independently pinned signing
root and signed whole capsule/manifest with current revocation, Team A
current genuine enrolled one-use SAFE install permission and restricted
aegis/aegis-mgmt groups/socket, secure offline extraction into the SAME
B1 engine, and Team E actual Debian12 install/start/READY/restart
journal/UUID receipts. No completed IG-001 combined-source acceptance,
no Windows native host acceptance and no release PASS.
