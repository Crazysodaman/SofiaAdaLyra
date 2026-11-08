# D028-00 | cross-team contract decision ledger (A/B/C/D/E)

**Status: UNFROZEN. NO RELEASE AUTHORIZATION.** Source draft: PR #241;
canonical spec: PR #248 + issue #250. Teams B/C/D/E must explicitly sign
the **same pinned source SHA + named immutable fixture blob IDs** after
passing tests. A GitHub PR comment asking for ACK is not the other team's ACK.

| Decision | Proposed versioned rule | Accountable teams | Disposition |
|---|---|---|---|
| D00-1 Envelope | `aegis.platform.library.request.v1` / `response.v1` only, protocol `1.0`, 12 exact keys, <=32KiB UTF-8 control, reject duplicates/unknown, matching request/correlation/target/current RUN+revision, <=5s observation and 60s request validity, no auto downgrade | A+C+E | REQUEST CHANGE/ACK pending |
| D00-2 Artifact identity | **Immutable bytes** are exact lowercase `content_digest` SHA-256 + byte length, signed publisher manifest has independent `manifest_digest` SHA-256; logical `artifact_id` and version/revision are human/catalog selectors only, never substitutes for digest; pinned publisher key ID/independent trusted root and target OS/arch/ABI/SDK. No Hub-provided signer string can verify a signature | B+D+A | PENDING |
| D00-3 Signed catalog origin | Per-index signed metadata binds catalog revision, primary Platform/Library identity and epoch, snapshot time/expiry, source installation provenance, antirollback floor, publisher root or separate index key trust and revocation. Hub mTLS proves sender only; receiver re-verifies signature+root after catalog retrieval. No replay on new primary epoch or RUN generation | A+B+E | PENDING |
| D00-4 Dependency plan | Advisory `library.plan.acquire.v1` returns explicit selected immutable digests, dependency-first deterministic closure, missing/conflicting/incompatible/unselected, OS/ABI/SDK/license/data class, predicted bytes/quota, issuer and separate signed proof refs; `OK` plan never queues transfer/install | D+B+C | PENDING, successful projection not enabled |
| D00-5 State ladder | INDEXED (catalog) ≠ CACHED_UNVERIFIED ≠ VERIFIED (recipient B1 signature+hash) ≠ STAGED (B receipt) ≠ INSTALLED (B install receipt) ≠ ACTIVE (current D lifecycle receipt). PAUSED, ROLLBACK_PINNED, OUTCOME_UNKNOWN separately. Unknown receipts => null/UNKNOWN, never fabricated false or zero | B+D+C+E | PENDING, UI OfflineReader |
| D00-6 Transfer progress | received/verified/total independently counted, received=total may still be VERIFYING. Resume token is opaque, deadline+source/target+manifest/content digest+catalog rev+byte range/chunk SHA bound, recipient authoritatively checks offset/order/overlap/parent SHA/quota/signer/license, no untrusted path or network URL | A+B+D+E | PENDING, transfer disabled |
| D00-7 SAFE and mutation | Single existing Platform SAFE owner proof/STOP system, host- and operation-scoped one-time approval consumed atomically with B1 effect and current RUN revision; STO/P/revocation/rotation after approval but before admission denies. Unknown/never enrolled peer gets EOF, not typed existence hint. Long transfer rechecks each chunk and prior to final admission | A+B+D+E | PENDING, effects disabled |
| D00-8 Mutual network identity | TLS1.3 CERT_REQUIRED with pinned independently enrolled **both** Platform installation keys/peer audiences; sender certificate does not authorize artifact bytes, signer or recipient install. No implicit LAN/mDNS/IP admission, no WAN fallback, no second owner secret/writer/Hub approval | A+B+E | PENDING, no listener |
| D00-9 Denial/version/retry | Only `NOT_PERMITTED, REVOKED, STOPPED, STALE_GENERATION, EXPIRED, UNAVAILABLE` envelope denials, `data:null`; operation-specific QUOTA/CONFLICT/etc only in signed current receipts, not invented envelope codes. Reconnect uses new OS/mTLS session + new request/correlation/revision; no stale token, no hidden retry of an effect with OUTCOME_UNKNOWN | A+C+D+E | PENDING |
| D00-10 Retention & huge assets | Existing B CAS is sole store. Revision-atomic pin graph ACTIVE/STAGED/INSTALLED_DISABLED_DEPENDENCY/ROLLBACK_RETAINED/IN_FLIGHT_VERIFICATION/OPERATOR_PIN. No delete on uncertain pin. Individual SDK chunk <=512MiB, larger parent signed manifest binds chunks and final whole SHA, must stream and independently verify. No LRU override of rollback | B+D+A+E | PENDING |

## Files held stable pending review

- Rust candidate `rust/crates/sofia-contracts/src/library.rs`.
- Python candidate `src/sofia/sdk/platform_library.py`.
- Shared `contracts/platform/library-*preview-v1.json` fixtures.
- B1 signer/installation authority from Team B, SDK recipient/verifier
  from Team D, pure read-only display from Team C, independent W7/W-EMPTY/
  W-PEER/D-HUB/D-CLIENT verification from Team E.
- No additional signer, installer, owner-auth system, writable UI, shared
  SQLite writer, Hub listener or Core activation may arise from this draft.

## Signoff ledger

| Reviewer | Versioned request submitted | Written final same-SHA ACK | Exact CI + native signed-host evidence |
|---|---|---|---|
| Team A | Candidate implementation only | **NO** | **NO** |
| Team B | PR #244 | **NO** | **NO** |
| Team C | PR #243 | **NO** | **NO** |
| Team D | PR #251 | **NO** | **NO** |
| Team E | PR #245 | **NO** | **NO** |

**D028-00 freeze verdict: NO. Original acceptance 0/38; LIB 0/16.**
