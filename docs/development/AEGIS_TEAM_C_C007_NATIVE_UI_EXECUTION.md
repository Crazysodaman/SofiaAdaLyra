# Team C C-007 | Development-first native UI and IG-001 read-only proof

**Branch:** `chatgpt/team-c-platform-ui-consolidation-20261108`, draft #243, no main write.
**Intent:** preserve source development while queued CI remains noncertifying; no new IPC, owner grant, installer, Hub or Core.
**Team A reference at review:** #241 `5bc8f9c2269ac2ac2b5b0e6c8c9bd1d769cba2a9`.
**Corpus blob:** `b63eeafe40b7895468f7ac8e0060c3bebfababa9`, exact 29 shared wire vectors, expected **9 accept/20 reject**, not yet executed jointly.
**Source only != release proof.** Run commands on an independently obtained **full repo checkout**, never substitute a source-code excerpt for native execution.

## 1. Actual available local environment in Team C's execution session

`uname -srm`: Linux 6.18.57 x86_64. `python --version`: 3.13.5.
`python -m pytest --version`: pytest 9.0.2.
`command -v cargo/rustc/rustfmt/cargo-clippy/pwsh`: all unavailable.
`git ls-remote https://github.com/Crazysodaman/SofiaAdaLyra.git HEAD`: failed `Could not resolve host: github.com`.
No repository checkout exists under `/mnt/data/SofiaAdaLyra`.
Actual `python -m pytest -q /mnt/data/SofiaAdaLyra/test/test_ui_aegis_team_c_policy.py` returned **exit 4**, file not found; **0 tests executed**. This is an environment BLOCKER, not a source-test FAIL/PASS. No native WinForms, Cargo, ABI/OS, installed-host or service-origin evidence available in this sandbox.

## 2. Commands for an actual developer checkout (never mark unrun commands PASS)

From exact Team C branch HEAD, first run `git rev-parse HEAD`; save output with every log.

```bash
set -e
git rev-parse HEAD
cargo fmt --all --check
cargo clippy --locked -p sofia-ui-broker --all-targets -- -D warnings
cargo test --locked -p sofia-ui-broker
cargo build --locked -p sofia-ui-broker --bin aegis_tui
python -m pytest -q test/test_ui_aegis_team_c_policy.py test/test_ui_aegis_tui_binary_smoke.py
./target/debug/aegis_tui --help
NO_COLOR=1 ./target/debug/aegis_tui --plain
```

Explicit offline negatives use nonzero expected exit code 3, NOT a successful authenticated service:
```bash
NO_COLOR=1 ./target/debug/aegis_tui --status
NO_COLOR=1 ./target/debug/aegis_tui --status-json
NO_COLOR=1 ./target/debug/aegis_tui --library-status
NO_COLOR=1 ./target/debug/aegis_tui --library-json
NO_COLOR=1 ./target/debug/aegis_tui --install   # expect exit 2
```
The headless status JSON must show `source=UNVERIFIED`, `platform_generation=null`, `operator_stop=null`, `core_started=null`, `actions_enabled=false` while offline. A STOP, revoked, denied, restarted or stale generation may NEVER expose previously cached live fields or return a successful status code.

On a **native Windows developer machine**, NOT a production host:
```powershell
git rev-parse HEAD
cargo fmt --all --check
cargo clippy --locked -p sofia-ui-broker --all-targets -- -D warnings
cargo test --locked -p sofia-ui-broker
cargo build --locked -p sofia-ui-broker --bin aegis_tui
python -m pytest -q test/test_ui_aegis_windows_gui_shell.py test/test_ui_aegis_team_c_policy.py test/test_ui_aegis_tui_binary_smoke.py
powershell.exe -NoProfile -NonInteractive -File packaging/gui/Start-AegisControlCenter.ps1 -Check
powershell.exe -STA -NoProfile -NonInteractive -File packaging/gui/Start-AegisControlCenter.ps1 -UiProbe
.\target\debug\aegis_tui.exe --status-json
```

`-UiProbe` must emit `LIBRARY_PAGE_VERIFIED=Library > ...;SOURCE=UNVERIFIED;ACTIONS=DISABLED` for **all seven** Catalog, Sources, Downloads, Installed, Storage, Hub and History pages and `LIBRARY_NAVIGATION_PROBE=PASS` only if native control checks actually execute. A headless WinForms probe is NOT a photographed signed installed-host GUI acceptance.

## 3. Mandatory 29-vector A/C shared Rust/Python contract execution

In a **separate exact Team A checkout**:
```bash
git rev-parse HEAD  # must equal the explicitly reviewed A SHA
python -m pytest -q test/test_ui_platform_management_response.py -k shared_29_case_rust_python_management_wire_corpus
cargo test --locked -p sofia-contracts shared_29_case_rust_python_management_wire_corpus -- --nocapture
```
Save both unabridged logs, actual test counts, checked-out SHA, parser blobs, corpus blob, OS/toolchain, C1 U+0085, surrogate halves, 6 denial mappings and all 29 accept/reject verdicts. The two test functions each aggregate 29 assertions; one pytest PASS and one Rust unit PASS are **not 29 independent pytest test results**. No A/C final signoff without actual same-SHA matching execution and independent OS-enrolled service origin.

## 4. IG-001 read-only Platform boot-and-answer protocol, E independent evidence

Only after A/C management v1 **same-SHA signoff** and B independently provisions approved exact Windows SidTypeUser pipe DACL / Debian UID-GID + 0750/0660 operator socket:

1. E starts an independently publisher-verified Core-free Platform release on disposable W-EMPTY and D-CLIENT. Record signed binary/manifest SHA, OS/ABI, service Platform ID and RUN generation. Do NOT use the personal Sofía VM, owner secret or production network.
2. Independently authenticate the actual A service native socket/pipe peer and enrolled current SAFE permission. The TUI is a **consumer** of A's exact management.read.v1 request+response parser and session. No client-supplied UID/SID or `source=PLATFORM_SESSION` can prove identity.
3. Make one `platform.status` read with a fresh bounded request ID, target, expected generation, created/deadline; require a strict matched response with fresh observed time, `operator_stop=false`, `core_started=false`, no action grant. Capture a **real service-origin** transcript and status JSON, not a fixture.
4. Drop service/unplug socket: nonzero status, source UNVERIFIED, cached generation and install state excluded from current values; no auto-start, retry-of-effect or new writer.
5. Repeat with independently enrolled but STOPPED, REVOKED, NOT_PERMITTED, STALE_GENERATION, EXPIRED, UNAVAILABLE. Unenrolled/revoked may receive EOF (not identity disclosure). Record actual return code, wire denial or EOF, no protected action, generation/age fences.
6. E proves Windows WinForms + native Windows TUI + Debian 12 TUI/headless CLI read the **same A-owned service** and consistent snapshots, and UI closure does not terminate service. Do not claim GUI/TUI native acceptance on source-probe alone.
7. Only after separate A/B/D/E D028-00 freeze, extend those reads to `library.catalog.snapshot.v1` and `library.inventory.snapshot.v1`; never infer VERIFIED from received bytes, an unsigned Hub pointer or constructible receipt ref. Protected operations remain disabled.

Current Team C branch deliberately contains **NO live enrolled reader or socket connector**. `DisplayReadSource` is a contract seam, `OfflineReader` remains the only connected source. This is a missing integration dependency, not a fake live transcript.

## 5. D028-00 C field-level disposition

- **D00-1 Envelope:** architecture ACK for A's exact protocol `1.0` and single 12-key service envelope; **HOLD final** on A/C same-SHA 29-vector results and approved native service origin.
- **D00-4 Dependency plan:** **REQUEST CHANGE** to bind immutable signed manifest bytes SHA separately from Team D's unsigned identity digest, selected closure, ABI/SDK/license and excluded/unselected items, revisions and typed plan receipt. Advisory only, never queues install.
- **D00-5 State ladder:** conditional source ACK distinct INDEXED/CACHED_UNVERIFIED/VERIFIED/STAGED/INSTALLED/ACTIVE/PAUSED/ROLLBACK_PINNED; **HOLD final** until issuer, target, digest, current B/D signer receipt and A observer time/revision are verified. UI display refs are not cryptographic proof.
- **D00-9 Denial/retry:** **REQUEST CHANGE** for canonical six denials + unenrolled EOF, cursor replay/expiry, restart ambiguity, observed-time regression, atomic idempotency/OUTCOME_UNKNOWN reconciliation. No hidden effect retry.
- **Others D00-2/3/6/7/8/10:** A/B/D/E remain accountable; C does not sign producer-owned digest/cert/GC semantics without installed-host proof. B owns ONE governed installer and existing CAS, D SDK/recipient, E independent W7/IG-001.

**Certifications:** Platform original 0/38, mandatory Library 0/16. No GO, merge, Hub/Core activation, release PASS or real-host mutation.
