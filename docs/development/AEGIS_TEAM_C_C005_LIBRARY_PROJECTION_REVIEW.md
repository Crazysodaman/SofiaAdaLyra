# Team C C-005 | Library display projection and source-trust hold

**Status:** Team C draft #243, implementation candidate only. D028-00 and management read v1 **NOT JOINTLY FROZEN**.
**Main:** no Team C change; no Core or Hub activation; no production installation or release PASS.

## New presentation-only contract

`rust/crates/sofia-ui-broker/src/library_display.rs` implements an inert `LibraryObservationSource` seam and `OfflineLibraryReader`. The latter is the **only supplied implementation** and cannot yield an invented online observation. It creates no new REST/IPC transport, signer, privileged owner grant, cache, Hub, installation writer or management service. This projection is **not** `aegis.platform.library.response.v1` and does not parse the A-owned JSON envelope. The only actor permitted to supply a nonoffline observation in future is the exact Team A/B/D reviewed, OS-enrolled, SAFE/STOP-fenced client, after independent service and publisher receipt verification.

`LibraryDisplaySession` pins a target Platform ID, service RUN generation, state revision and strictly increasing response sequence within a generation. A changed Platform, old RUN generation, decreasing revision, duplicate sequence, missing identity, malformed catalog signer/index/source or host/content-mismatched lifecycle receipt marks the status stale or unverified. Its existing internal historical snapshot is never exposed as current after disconnect, STOP, revocation, denial, restart or timeout. A successful reply claiming STOP-active/unknown SAFE is rejected, rather than displayed as current.

The separate receipt slots are `downloaded`, `verified`, `staged`, `installed`, `active` and `rollback_pinned`. **None means NOT OBSERVED**, not absent, zero or revoked. Each is target-Platform/content-digest bound; an active receipt without an installed receipt is contradictory. These are *UI references to independently verified A/B/D receipts*, not raw signatures or cryptographic verification by Team C. Until A/B/D freeze provenance, no producer can legitimately populate these slots in production.

`TransferProgress` separately presents `received_bytes`, `verified_bytes` and `total_bytes`. It refuses `verified > received` or `received > total` and does NOT infer VERIFIED from 100% received. Signed catalog index revision, signer key and source ID remain distinct from install/service authority. A Hub or remote sender cannot mark a target installed or active.

Rust tests exercise offline/no-observation, received-complete/verified-zero, independent receipt progression, wrong-host receipt, restart and sequence/generation/revision rollback, STOP/revoked/denied/stale, malformed catalog/transfer, and active-without-install. The TUI and WinForms remain read-only/offline pending contract freeze; this new module is not yet connected to a live UI renderer and must not be counted as feature-complete D028-06.

## Release gates and trust responsibilities

- **Team A PR #241:** exact canonical management.read-response.v1 SHA, full Rust/Python C0/C1/surrogate/missing-null/portable numeric/UTC precision strict parity, correlation/generation/freshness/denials, and enrolled SID/Unix-socket service origin. The A-owned library.request/response.v1 contract must freeze target+source identity, pagination/cursors, provenance, operation-scoped receipts and error semantics. No second socket or JSON-asserted principal.
- **Team B PR #244:** single signed B1 Core-free installer, actual independently pinned publisher root/revocation, cache byte-verification authority and per-target lifecycle receipts, optional GUI/TUI component signed manifests and native operator SID/GID provisioning. HASH_MATCH_ONLY does not establish signer trust.
- **Team D PR #251:** exact dependency closure/ABI/SDK/license/recipient signature recheck and staged/active/rollback pin ownership; its constructible Python dataclass is not an authenticated catalog or executable receipt.
- **Team E PR #245:** independent four-host signed installed Windows/Debian 12 GUI/TUI/CLI parity plus LIB-14/16 and all 38 release rows, including STOP/revoked/stale/peer and recovery negatives. A CI unit test, shell probe or unsigned binary digest cannot advance acceptance.
- **Team C PR #243:** keep the one WinForms GUI and native Rust TUI, offline readers, disabled mutation buttons and exact-PR-head CI/receipts. Migrate live reads ONLY through the A-owned enrolled and reviewed service when that immutable contract is signed.

**Current acceptance:** original Platform rows **0/38**; mandatory Library cases **0/16** certified. No merge, production Hub/Platform/Core action or PASS.
