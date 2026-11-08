# AG-D028 / Team A D028-00: one authenticated Artifact Library contract

**Status:** CROSS-TEAM CANDIDATE ONLY; A/C/B/D/E freeze is **NOT** signed. The canonical release design is [AG-D028 #248](../roadmaps/AG_D028_PLATFORM_1_0_RELEASE_SPEC.md) and [issue #250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250). The signed installed-host LIB-01–16 acceptance tests remain unpassed. This document proposes a protocol for review; it installs no Hub, broker, downloader, signer, grant, listener, database or Core.

## 1. Trust and package ownership

Use the **existing** Rust-owned Platform management service and native OS authenticated admission, same single SAFE/STOP permission system and current approved enrollment, generation and revision fencing as #241. The library envelope is a distinct typed application contract **on that broker**, NOT a second management socket, another signing root, another Core writer, Hub-admin owner-secret flow or Internet-facing privilege API.

Team B owns independently pinned publisher roots, signed Platform-only offline seed, B1 installation/repair/rollback and existing `OfflineArtifactCache`. Team D owns Core/module signed dependency closure, compatibility and synthetic reference lifecycle. Team C receives only verified redacted observations, never a self-authorizing display value. Team E independently witnesses signed installed-host receipts. Team A owns envelope, transport identity, peer enrollment, SAFE/STOP, expiry, revocation and cross-host audience pinning. Cached/verified/installed/active each need **separate evidence authorities**; Hub TLS only authenticates *sender*, NEVER publisher signature, installer authorization or active Core identity.

## 2. Version and strict wire envelope

Proposal: `aegis.platform.library.request.v1` / `aegis.platform.library.response.v1`, protocol **exactly** `"1.0"` (no implicit minor acceptance, negotiation from unknown peer, fallback to #232/#234 or auto-downgrade). Fields are exact, bounded UTF-8 strict JSON with duplicate keys/nonfinite values rejected. No raw pathname, URL, credential, executable command, owner grant, session token, arbitrary class or unknown key. Source+transport authenticated **outside** the JSON on the same canonical service; `caller_principal`, `audience`, `peer_sid`, `peer_uid` MUST NOT appear as asserted client fields. The session owner derives target + audience from native OS token or fresh mutually authenticated enrolled Platform TLS/peer binding and compares the request's target against that **current** source of truth.

### Request v1 (candidate exactly 12 keys)

`schema,protocol,request_id,correlation_id,operation,target_platform_id,expected_generation,expected_revision,idempotency_key,created_at,deadline,parameters` (12 keys). IDs have bounded ASCII forms and must be unique per request/session; idempotency is **null on reads** and a scoped exact-operation key on effectful requests. `expected_generation` positive; `expected_revision` nonnegative; both re-read immediately before publishing any response, starting data transfer, or consuming one-time authority. RFC3339 aware time (0–6 fractional digits), bounded created/deadline at most 60s, checked on both ends. `parameters` is an operation-specific allowlisted bounded object; never treats submitted principal/role/target as authenticated.

### Response v1 (candidate exactly 12 keys)

`schema,protocol,request_id,correlation_id,operation,platform_id,platform_generation,state_revision,observed_at,outcome,data,denial`. Match all IDs, operation, target, generation, revision against the exact outstanding request and the **current** signed/locally owned service session. Response `observed_at` must be inside the original request window, no future time, and within five seconds of trusted client receipt. A correct-looking JSON is not service authentication; clients check native service origin or mTLS trust independently. Maximum 32 KiB for control response; large bytes move **only** on an independently authenticated bounded chunk data-plane with separate size/timeout/quota caps.

`OK` means `data` is a reviewed per-operation object and `denial=null`; `DENIED` means `data=null` and `denial={"code":...}` only. Base codes: `NOT_PERMITTED,REVOKED,STOPPED,STALE_GENERATION,EXPIRED,UNAVAILABLE`; operation-specific failures appear as typed, scrubbed current receipt outcomes (e.g. `CONFLICT,QUOTA_EXCEEDED,REJECTED,PAUSED,OUTCOME_UNKNOWN`) and do NOT assert privileges or completed verification. For never-enrolled/revoked clients the service returns EOF/no disclosure, not a typed identity-enumeration hint. Wrong schema, future time, stale revision, replayed cursor/duplicate ID, unsupported operation or malformed response cannot be rendered as healthy/installed. There is no success response from a Hub asserting installation.

## 3. Typed operations and result objects

**Read-only, no side effects:** `library.catalog.snapshot.v1`, `library.inventory.snapshot.v1`, `library.sources.snapshot.v1`, `library.transfer.status.v1`, `library.history.snapshot.v1`. The first page/cursor and revision must be server-owned and bounded. `catalog` returns independently pinned signed index revision/generation/freshness, source kind/last observation and page of exact artifact ID, release version/revision, manifest/content SHA-256 and size, kind, signer key ID/publisher provenance (not just certificate subject), OS/arch/ABI/SDK/license/data-class restrictions; never an install claim. Cursors bind target Platform, principal/audience, role, filters, generation, index revision, expiry, max page size; cursor loss/metadata expiry => `STALE/UNKNOWN`, not empty catalog.

`inventory` returns **separate** per-target/cache verification state, staged state and B/D signed installed/lifecycle receipt state. `INDEXED, CACHED_UNVERIFIED, CACHED_VERIFIED, QUARANTINED, STAGED, INSTALLED_DISABLED, ACTIVE, PAUSED, ROLLBACK_PINNED, REMOVED_RETAINED, MISSING` may not collapse into one invented Boolean. If target receipt not verifiable, `installed=null,active=null`; Hub metadata can never assert those values. Distinguish `received_bytes` from `verified_bytes`; zero or transfer 100% does not imply VERIFIED, INSTALLED or ACTIVE.

`sources` returns LOCAL_VERIFIED_CACHE, OFFLINE_MEDIA, OWNER_SELECTED_HUB, AUTHORIZED_PEER, OFFICIAL_REMOTE with explicit `internet_enabled=false` by default, each source ID, authentication/verification **evidence reference**, last observed time and freshness; a source URL or local network address never grants trust. No WAN auto-fetch.

`library.plan.acquire.v1` is **advisory only**: exact selected artifacts/digests, deterministic pinned dependency closure, denied/missing/incompatible/unselected separate, total transfer and expansion space, license, issuer trust, permitted source set, current revisions, expiry and required approvals. No implicit install/activation, no wildcard authority.

**Effects blocked until later B/D/A signed signoff:** `library.acquire.v1`, `library.transfer.cancel.v1`, `library.verify.v1`, `library.pin.v1`, `library.unpin.v1`, `library.retire.cache.v1`, `library.hub.offer.v1`, `library.peer.fetch.v1`. Each uses an exact one-time owner-approved operation scope where required, current SAFE/STOP and revocation at the boundary, typed receipt and idempotency fence, no id/URI-selected path. `library.install.execute.v1` and activation have no new executor: delegate exclusively to B/D existing governed signed installer and owner ceremony. Data-plane resumable tokens are bound to publisher digest, two current independently enrolled Platform identities, class/license/role, catalog generation, expiry and data offsets. Revalidate peer mTLS/enrollment, owner grant, quota and STOP before and during **each chunk**. Receiver always independently rechecks digest, signature, publisher root/revocation, OS/ABI, license and installer approval.

## 4. UI display and recoverability

Every client (WinForms, Rust TUI, CLI) uses the **same** typed trusted Platform result. Denied/EOF/revoked/STOP/disconnected/stale generation invalidates any editor or pending effect assumption. Recent catalog data may be displayed only as **STALE/UNVERIFIED** with last observed time; it cannot drive executable actions. A transfer can have `received_bytes==total_bytes` while `verified_bytes==0`, pending independent release verification. `PAUSED/CANCELLED/OUTCOME_UNKNOWN` must reconcile with exact persisted B1/cache/transfer receipt, not retry install blindly. A new connection needs new OS/mTLS verified session, nonce, correlation ID, current generation and revision. Owner-approved Internet fallback is OFF unless separately configured and rechecked at each source change.

## 5. Candidate fixtures and reviewed negative requirements

These fixtures are **NOT** signed catalog, real response, operational proof or parser acceptance:
- `contracts/platform/library-request-catalog-preview-v1.json`
- `contracts/platform/library-response-catalog-preview-v1.json`
- `contracts/platform/library-response-stop-preview-v1.json`
- `contracts/platform/library-response-transfer-preview-v1.json`

Reject unauthenticated/injected principal, remote Hub authority as owner approval, unknown/major-minor versions, arbitrary URLs/paths, duplicate JSON keys, massive list/cursor, wrong host/generation/revision, stale response, unsigned/untrusted/wrong-OS/private/nonredistributable source, partial chunk admit, replay/idempotency collision, revoked publisher/peer midstream, STOP between plan/transfer/verify/install, wrong license, secret leakage, shared `sofia.db`, same-Core duplicate writer, surprise WAN fallback, non-B1 native install, unpinned GC, uninstall that loses identity. Team E owns independent four-host LIB-01–16 evidence with signed installer/source/digest/OS/host identity and negative receipts; neither these fixtures nor earlier component tests mean a #201 row PASS.

## 6. Review and hold points

**BLOCKED:** Existing A/C `read-response.v1` joint signoff, then B's signed artifact index/verified cache/install receipts, D's typed Core/module dependency/license/ABI manifest, C's exact UI projections, E's independent evidence contract. This D028-00 document and fixtures can evolve only by reviewed SHA; no executable service actions until every authority boundary is accepted. No merge, no production Hub, no personal Core startup, no second signer/writer/grant.
