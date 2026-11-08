# C-006 Team C | SHA-pinned management and D028-00 contract review

**Review state:** SOURCE-ACK WITH HOLDS; A/C MANAGEMENT **NOT FROZEN**; A/B/C/D/E D028-00 **NOT FROZEN**.
**Team C:** PR #243, isolated draft; production readers still `OfflineReader` and `OfflineLibraryReader`.
**Team A inspected source:** PR #241 SHA `5bc8f9c2269ac2ac2b5b0e6c8c9bd1d769cba2a9` (a newer exact head than coordinator's `66a805338679c3363fe2f0085d1284ba97662ba5`).

## 29-case Rust/Python management corpus, what is and is not proven

The canonical fixture at A HEAD above is
`contracts/platform/management-response-parity-corpus-v1.json`
**Git blob SHA `b63eeafe40b7895468f7ac8e0060c3bebfababa9`**.

Source inspection counted **29 distinct vectors, 9 expected ACCEPT and 20 expected REJECT**, 19 `platform.status` and 10 `settings.inspect`. Independent source inventory includes positive OK/STOPPED/NOT_PERMITTED/REVOKED/STALE_GENERATION/EXPIRED/UNAVAILABLE, settings U+2028, maximum portable integer; negative missing explicit fields, malformed/extra denial, minor/major versions, stale/future/nanosecond observations, generation mismatch, C1 U+0085, C0 newline, two unpaired surrogate halves, non-ASCII key, numeric overflow, float overflow and duplicate key.

- Rust parser `rust/crates/sofia-contracts/src/management.rs`: blob `608b6966169441df8688c83b37d5bca9a6bdc602`.
- Python parser `src/sofia/sdk/platform_management_response.py`: blob `69b5a375dc14453572dcca5a7ff6885de3b069d7`.
- Both source suites contain `shared_29_case_rust_python_management_wire_corpus` using the **same raw vector strings** and named expectations. The source also implements 32-KiB limit, exact protocol 1.0 with no downgrade, strict C1/surrogate rejection, request ID/operation/target/generation and 5-second observation freshness, and six typed denials.
- **NOT PROVEN:** No 29/29 runtime verdict or Rust/Python exact-A-head simultaneous pass has been observed, even though test definitions exist. All six #241 workflows at this A SHA were queued/pending at inspection. Do not infer a signing authority or current enrolled operator from JSON `source`.
- **A/C signoff HOLD** until native and SDK CI complete on the SAME A commit, pinned contract blob hashes are co-acknowledged, and Windows individual SidTypeUser pipe identity/Debian enrolled Unix-socket UID/GID SAFE/STOP/revocation/freshness/generation negative and positive receipts are independently witnessed. Source-only fixtures do not authorize live reader connection.

## D028-00 Library contract exact pinned candidate (NOT frozen)

A HEAD `5bc8f9c2269ac2ac2b5b0e6c8c9bd1d769cba2a9`:
- Rust `rust/crates/sofia-contracts/src/library.rs` blob `5db05bbcc1e5cc52aa03471bd5f680327eefe530`.
- Python `src/sofia/sdk/platform_library.py` blob `dc3735f46656e0ca92412644d521fdd8eee3b63d`.
- Preview catalog response blob `9a329856860519236e10511740fabf0bef0f9e2c`.
- Preview transfer response blob `0b68f93055e66402830f01e80fd29e6c9a21fb91`.
- Preview STOP response blob `0493e22d20babc1566c6d639eae14e209e1854c1`.
- Exact protocol `aegis.platform.library.request.v1/response.v1` with 12 mandatory keys, 32-KiB response, request/correlation/target/generation/revision/time fences and separately authenticated service origin. Catalog/transfer syntax and six denial codes are reviewed; **NO live dispatch, signed index origin, native installed receipt or cache authority is proved.**
- **REQUEST CHANGE before freeze:** final verified publisher root/revocation/manifest+content digests, source identity and epochs; B signed cache/install/stage receipts and target/issuer/time binding; D dependency/ABI/SDK/license/retention pins and idempotent lifecycle receipts; transfer received vs verified bytes, resumable cursor and OUTCOME_UNKNOWN; stale/STOP/revoked/restart invalidation; coordinated A/B/D/E exact SHA and installed-host adversarial evidence.

## Team C C-006 display-security change

`rust/crates/sofia-ui-broker/src/library_display.rs` remains a NO-TRANSPORT, NO-CRYPTOGRAPHY display-only seam. It now checks each *referenced service evidence context* against issuer, target Platform, content digest, active RUN generation, revision and observation timestamp; rejects duplicated lifecycle receipt IDs, impossible progress, stale time, replayed sequence and mismatched target/digest. The label is **RECEIPT_REFERENCE_NOT_AUTHORITY** so even a constructible fake reference never claims verification by itself. Negative Rust tests cover all six forged evidence fields. An untrusted JSON string or in-process display struct is not an owner grant or signed B1 receipt.

**Critical caveat:** The UI's receipt fields are still freely constructible in tests. Their format checks DO NOT authenticate origin or signature. Only A's *future approved enrolled client*, plus B/D independent evidence checks, may provide actual trusted observations. Therefore NO production `platform.status` or `library.catalog` connection was authorized or implemented.

## Exact-head CI and installed-host acceptance gates

Team C's native Windows GUI and Windows/Linux Rust TUI CI includes exact PR HEAD checkout assertion and component-only artifacts (native WinForms seven-page `-UiProbe`; TUI binary SHA-256, NO_COLOR, denied mutation and headless offline JSON). At the C-006 checkpoint GitHub Actions were queued/pending at current C exact head; **no CI PASS, no actual binary/screenshots and no signed installed-host receipt**. Local runtime lacks Cargo/Rustc and PowerShell; source-only tests are not equivalent to executing CI.

Team B retains the one governed signed optional GUI/TUI installer and Windows SID / Debian UID/GID provisioning. Team D retains Core/module, dependency and rollback semantics. Team E independently certifies disposable installed-host LIB-14/16 and the original #201 rows 31–38. All LIB-01..16 **0/16** and original Platform acceptance **0/38**; NO-GO. No merge, main change, production deployment, Hub activation, personal Core startup or private-data transfer.
