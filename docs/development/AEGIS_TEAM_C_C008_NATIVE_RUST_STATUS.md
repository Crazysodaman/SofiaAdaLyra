# Team C C-008 | Native Rust management.status adapter / IG-001 handoff

**Status:** isolated development on draft PR #243, NO signed installed-host release, NO A/C management freeze. Platform **NO-GO**. Current canonical Team A PR #241 reviewed source SHA: `16f616a786fd5f800f72a79f8c0fae3cfe5cbc52`.

## Source boundary and what was built

- Copy-on-branch of **byte-identical Team A** `rust/crates/sofia-contracts/src/management.rs` Git blob `608b6966169441df8688c83b37d5bca9a6bdc602` and six existing canonical fixtures (29-vector corpus blob `b63eeafe40b7895468f7ac8e0060c3bebfababa9`). This is NOT a new v1 parser, contract freeze, schema fork or new authority. Reconcile once against A exact blob in Team E's isolated IG-001 integration branch. The original Team C checkout had an older request-only parser; a response parser must be present to compile the native reader.
- `rust/crates/sofia-ui-broker/src/native_management.rs` exports a Linux-only `NativeLinuxManagementReader` implementing **the same** `DisplayReadSource` as `OfflineReader` and using A's unmodified `UntrustedManagementRead::parse` and `UntrustedManagementResponse::parse` for bounded v1 request+response. No private JSON decoder, owner-grant store, second service, signer, or permission authority.
- Native kernel `SO_PEERCRED` via safe `nix` syscall wrapper. Client checks absolute B-pinned AF_UNIX path; symlink-free path ancestry, B-trusted runtime UID/GID/modes and socket dev+inode before and after read, kernel peer service UID+primary GID and optional exact PID, 2-s monotonic read/write, <=32KiB response, one newline, random 128-bit request ID, exact target/operation/current RUN generation, 5-s request deadline and fresh response. EOF or untrusted socket is **not** typed authorization.
- `InstalledNativeServicePins::from_externally_verified_installation` checks only data shape; it **DOES NOT cryptographically verify** B1 signing or SAFE enrollment. A trustworthy B1 installation-profile provider is STILL MISSING, so the CLI does not expose user-selected UID/GID/PID/path as a flag and does not activate native service access. The Rust kernel checks themselves prove OS provenance only, not installed publisher signature or existing owner SAFE grant. The A broker must independently verify owner's scoped SAFE/STOP before and after response.
- Separate **service primary GID** and **optionally enrolled management socket GID** are honored. Private profile: exact 0700 parent / 0600 socket, owned by service UID and service primary GID. Explicit B-installed enrolled profile: exact 0750 parent / 0660 socket with independently pinned `aegis-mgmt` group; kernel peer GID still matches actual service PRIMARY GID. No chmod/chgrp, no group enumeration, no discovery, no self-enrollment or broad access.
- `aegis_tui` now routes `--status`, `--status-json` and interactive terminal pages through **one injected DisplayReadSource**, re-reads on interactive navigation and drops stale values on source failure. The existing `run()` still passes `OfflineReader` until B1 signed installed-service pin and native enrollment are independently supplied. No actual external operator response has entered the CLI; there is no live transcript. A valid A `OK` observation may disclose `core_started=false`; all disconnected/STOP/revoked fields remain null/unverified. Installation/activation/Hub/peer actions remain disabled.
- One validated A `OK` reply generates a **locally monotonic display sequence** after each fresh random correlation, never a service-issued sequence or installation receipt. Strict parser refuses correlation replay. Unknown/wrong ID/target/generation is UNVERIFIED; only authenticated typed `STALE_GENERATION` becomes UNKNOWN_GENERATION. Six exact denial codes map to existing display states.

## Native synthetic tests, NOT installed-host evidence

The Rust `native_management::linux::tests` module exercises a **disposable same-process AF_UNIX listener**, never production. Cases: correlated OK; typed STOPPED/REVOKED/NOT_PERMITTED/UNAVAILABLE/EXPIRED/STALE_GENERATION; EOF; incorrect request ID, forged generation, duplicate JSON key, STOP asserted inside a purported OK; incorrect service UID/GID/PID; unexpectedly broad socket permissions; symlink substitution/missing socket; private versus explicitly enrolled group mode. The Linux test creates sockets locally and does NOT simulate genuine B-signed service identity, actual second-user B enrollment, independent SAFE database, OS-bound signed publisher or Windows native SID. Team A independently reports its **own** executed 29/29 Python and 13/13 plus cross-UID native tests (A-010); Team C has not independently reproduced those.

## Exact developer commands and evidence requested from Team E

In a disposable **full checkout** of this PR's exact SHA, with Rust 1.88 and Python 3.12:

```bash
set -euo pipefail
git rev-parse HEAD | tee c008-source-sha.txt
git hash-object rust/crates/sofia-contracts/src/management.rs
git hash-object contracts/platform/management-response-parity-corpus-v1.json
cargo fmt --all --check
cargo clippy --locked -p sofia-ui-broker --all-targets -- -D warnings
cargo test --locked -p sofia-contracts shared_29_case_rust_python_management_wire_corpus -- --nocapture
cargo test --locked -p sofia-ui-broker native_management -- --nocapture
cargo test --locked -p sofia-ui-broker
cargo build --locked -p sofia-ui-broker --bin aegis_tui
python -m pytest -q test/test_ui_aegis_team_c_policy.py test/test_ui_aegis_tui_binary_smoke.py
NO_COLOR=1 ./target/debug/aegis_tui --status
NO_COLOR=1 ./target/debug/aegis_tui --status-json
NO_COLOR=1 ./target/debug/aegis_tui --library-status
NO_COLOR=1 ./target/debug/aegis_tui --library-json
```

**Expected CLI while no verified B1 installed-service profile is connected:** `--status` / `--status-json` return **3** (UNAVAILABLE, UNVERIFIED, null generation, null operator STOP, null core status), not 0. `--install` returns 2. A real connected transcript is **blocked** until B supplies signed profile and A approves one native Rust consumer activation route. Do not mark these commands as PASS without executing on a correct host.

For Windows native WinForms mandatory parity:
```powershell
git rev-parse HEAD
cargo fmt --all --check
cargo clippy --locked -p sofia-ui-broker --all-targets -- -D warnings
cargo test --locked -p sofia-ui-broker
cargo build --locked -p sofia-ui-broker --bin aegis_tui
python -m pytest -q test/test_ui_aegis_windows_gui_shell.py test/test_ui_aegis_team_c_policy.py test/test_ui_aegis_tui_binary_smoke.py
powershell.exe -STA -NoProfile -NonInteractive -File packaging/gui/Start-AegisControlCenter.ps1 -UiProbe
.\target\debug\aegis_tui.exe --status-json
```
The Windows Rust *client* is **not implemented** because Team A/B still owe the separately authenticated named-pipe client interface and signed individual operator SidTypeUser DACL. WinForms currently has no live authenticated management source.

At IG-001, E must inspect independently signed B1 executable digest, install manifest, current Platform ID, canonical service process UID and primary GID, pinned optional management socket GID (not confused with service primary), expected current RUN generation/PID, current SAFE owner enrollment grant and STOP, then witness actual cross-user **allow and deny** via A's canonical service. Connect the C compiled reader ONLY through an A-reviewed B1 verified profile source, not environment variables, ad hoc CLI paths or unsigned JSON. Preserve real request/response timestamps and ids, native peer credential evidence, restart/EOF, STOP, revocation, stale generation, replay, no hidden Core start, and B1 signer trust. E independently compares Windows GUI, native Windows/Linux TUI and headless CLI on the same signed installed Platform version. LIB-14/16 and #201 31–38 acceptance are blocked until genuine receipts.

## Actual Team C local execution, fail/NOT EXECUTED details

Local runtime: Linux 6.18.57 x86_64, Python 3.13.5, pytest 9.0.2; **no mounted full GitHub checkout, no cargo/rustc/rustfmt/Clippy, no PowerShell, shell GitHub DNS unavailable**.

```text
cargo fmt --all --check                  exit 127  cargo: command not found
cargo clippy --locked -p ...            exit 127  cargo: command not found
python -m pytest -q /mnt/data/SofiaAdaLyra/test/test_ui_aegis_team_c_policy.py
                                         exit 4    file or directory not found; 0 executed
pwsh -NoProfile -Command ...            exit 127  pwsh: command not found
```

Locally authored Rust tests: **NOT EXECUTED**, no binary artifact, NO real external enrolled service transcript, no WinForms screenshot. GitHub exact SHA CI still pending. Team A's independently reported local Python corpus match does not substitute for local Rust results or signed host GO.

**Formal A/C management v1 freeze: HOLD** until both languages same SHA executed and signoff. **D028-00: HOLD** (signed manifest bytes/publisher root vs unsigned identity digest and lifecycle/plan/provenance unresolved). **Platform acceptance 0/38; Library 0/16. No merge, main change, unauthorized owner grant, Hub/Core activation, production or release PASS.**
