# Team C C-003 | Contract signoff and native UI conformance review

**Status:** DRAFT, CONTRACT FREEZE **NOT SIGNED**; native UI release **NOT ACCEPTED**.
**Team C draft PR:** #243, branch `chatgpt/team-c-platform-ui-consolidation-20261108`.
**Scope:** canonical WinForms GUI + existing `aegis_tui`, D028-00 contract review / D028-06 presentation, LIB-14 / LIB-16.
**Main / production:** unchanged; no Hub, installer or personal Core activation.

## P1: Actual CI failure and remedy

Prior Team C head `6388aee0b545cbaa04d399b891f8ed45ef72ac8a` ran Windows and Linux TUI Clippy and failed at `control_center_session.rs:58`, `clippy::missing_errors_doc` on `DisplayReadSource::next`; `-D warnings` stayed enabled. The source-level fix and fresh TUI native test runs are in this PR. The component suite must demonstrate `cargo fmt --all --check`, `cargo clippy --locked -p sofia-ui-broker --all-targets -- -D warnings`, `cargo test --locked -p sofia-ui-broker`, compiled `aegis_tui`, and native Windows GUI `-UiProbe`. No PASS until **exact-final-head** CI succeeds.

## P2: Management response v1, explicit Team C review

Team A's reviewed candidate SHA was `46642fb9b018ee96f2fe4236eca866f6cfda9100` at source inspection; Team A is actively advancing draft #241, so THIS IS NOT an immutable freeze SHA. The A-owned files are `rust/crates/sofia-contracts/src/management.rs`, `src/sofia/sdk/platform_management_response.py`, `contracts/platform/management-read-response-valid-v1.json`, `management-read-response-denied-v1.json`, and `management-read-response-invalid-c1-v1.json`.

- Canonical request schema `aegis.platform.management.read.v1`; response `aegis.platform.management.read-response.v1`, exact protocol `1.0`, max 32 KiB, no downgrade/unknown fields/duplicates, no self-asserted principal/owner.
- Exact request ID, operation, Platform identity and RUN generation must correlate; received observation must be fresh (<=5s), within request lifetime, non-future and from **independently authenticated native service**.
- A now uses Python `unicodedata.category(c) == "Cc"` and Rust `char::is_control` for values, with a shared escaped U+0085 negative corpus and accepted U+2028 control-case. This addresses the earlier C1 discrepancy **in source** but cannot replace exact SHA Rust/Python CI evidence.
- Team C pure display-only mapping after a separate verified A response: `NOT_PERMITTED => DENIED`, `REVOKED => REVOKED`, `STOPPED => STOP_ACTIVE`, `STALE_GENERATION => UNKNOWN_GENERATION`, `EXPIRED => STALE`, `UNAVAILABLE/EOF => OFFLINE`. Invalid/unknown codes are never accepted; no parser or authorization implementation added by C.
- Verified STOP denial is **not** an OK status snapshot and cannot be used as an install/activation permission. Expired/revoked/offline status invalidates editors and blocks all actions. Cached installed state must not become REMOVED.
- A must supply exact-head passing native Windows/Linux OS-peer, Rust/Python strict fixture and revocation/STOP tests, independently enrolled Windows operator SID and Debian systemd runtime socket, then written A+C review signoff. Parser-valid text `source=PLATFORM_SESSION` is NOT OS authentication.

**C management contract decision: CONDITIONAL REVIEW / HOLD.** Do not label A+C joint freeze or connect a production reader yet.

## P3: Library D028-00 proposal, Team C REQUEST CHANGE before freeze

Draft #248/#250 and A's `AEGIS_D028_TEAM_A_AUTHENTICATED_LIBRARY_CONTRACT_PROPOSAL.md` propose **one** broker-associated `aegis.platform.library.request.v1` / `aegis.platform.library.response.v1`, exact protocol 1.0, strict 12-key request/response envelopes and separately authenticated principal/audience. C ACKs reuse of A's single Rust-owned Platform broker and SAFE/STOP; C does NOT create another IPC, REST auth, publisher signing root, B1 installer or Hub owner authority.

The A-owned *preview* fixtures are `contracts/platform/library-request-catalog-preview-v1.json`, `library-response-catalog-preview-v1.json`, `library-response-transfer-preview-v1.json` and `library-response-stop-preview-v1.json`. **No production parser or live client is authorized from these inert JSON examples.**

Before C can sign: B/D/A must freeze typed per-target catalog signed index revision, publisher key and signed manifest/content digests, OS/arch/ABI/SDK/license/redistribution restrictions, source freshness and cursor loss; advisory exact dependency plans; separately evidenced `downloaded`, `verified`, `staged`, `installed`, `paused`, `active`; transfer `received_bytes` vs `verified_bytes`; lease/generation/revision/idempotency and STOP/revocation/EOF mapping; exact native installed lifecycle receipts. A must supply negative Rust/Python fixtures and original authenticated principal/SAFE authorization boundary. Never let Hub claims prove publisher verification or target installation.

**C D028-00 decision: ARCHITECTURE ACK / FIELD-SEMANTICS CHANGE REQUESTED / FREEZE BLOCKED.**

## P4: Present implementation and intentionally closed authority

- One maintained WinForms shell at `packaging/gui/Start-AegisControlCenter.ps1`; #222/#228 remain reference variants only. Native `-UiProbe` checks 15 navigation entries, seven Library selection/content states, exact unknown source and disabled buttons. Actual interactive Windows desktop screenshot is NOT AVAILABLE in this review; do not substitute an illustration.
- One native `rust/crates/sofia-ui-broker/src/bin/aegis_tui.rs`, with seven Library pages, `--library-status` ASCII and `--library-json` machine-readable **UI-only** offline status; in JSON, unknown inventory/progress is `null`, never zero/false `INSTALLED`. Both noninteractive library probes use exit code 3 when unavailable and emit no ANSI.
- `DisplayReadSource` stays connected only to `OfflineReader`. `from_verified_denial` is a pure display mapping for an already correlated/authenticated Team A reply, not a JSON parser, service client, owner grant or live mutation path. There are NO real read, cache, acquisition, verification, download, installation, signed receipt or activation calls from Team C.
- Seven pages: Catalog, Sources, Downloads, Installed, Storage, Hub, History. Offline/stale/unknown is NOT empty; bytes received != bytes verified; 100% received does not mean VERIFIED; cached != installed != active. Internet fallback is disabled in this offline UI. All GUI actions disabled pending canonical A/B/D authority.

## P5: External packaging and Team E evidence gates

B owns AG-D011 ONE native signed Windows SCM/Debian systemd installer, optional signed GUI/TUI component manifests and signature provenance, operator SID/socket provisioning, no Git/Python/Cargo/Core prerequisite. D owns Core/module package dependency, SDK/ABI/license and worker lifecycle receipts. E owns independent four-host Windows/Debian LIB-14/16 GUI/TUI/CLI parity and installed-host evidence, plus all LIB-01..16. #201 still has 38 original acceptance rows. Component/mock tests DO NOT certify LIB cases.

**No merge, no main modification, no personal Core, no production Hub enrollment/activation, no release PASS.**
