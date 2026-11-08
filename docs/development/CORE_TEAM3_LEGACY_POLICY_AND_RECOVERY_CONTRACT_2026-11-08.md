# CORE-003-C001 | Legacy memory policy and continuity evidence contract

Status: **PROPOSAL, NOT APPROVED**. Scope: source audit and disposable regression design; no mutation of protected memory or identity. Review target: Core Coordinator, Core Teams 1/2/5 and Platform A. Date: 2026-11-08.

## Verified source behavior, not a release guarantee

- `DurableMemoryCandidateStore.is_recall_eligible()` checks `PROMOTED` and approved expiration, then returns **True** when there is no `memory_candidate_source_review` row (the historical compatibility branch). `_verify_reviewed_originals_in_writer()` also returns early when that guard is missing. These are current behavior; neither proves historical approval or authorizes arbitrary runtime writes.
- New reviewed promotion through `MemoryReviewService` independently checks authenticated private owner identity, current session audience, exact originals and immutable source metadata, and creates the extra review attestation before the atomic promote.
- `MemorySystem` independently checks principal and audience, status and expiration before entering cognition, but the legacy missing-attestation exception remains reachable for a scoped old candidate. A missing review attestation is not equivalent to proof that the candidate is malicious.
- Existing `test_memory_review_source_revalidation.py::test_legacy_unattested_candidate_is_not_silently_deleted_by_migration` explicitly preserves this compatibility behavior. New T3 characterization asserts that a low-level promoted legacy fixture can be retrieved despite lacking attested current originals. This marks **a security policy gap**, not release acceptance.

## Proposed coordinator policy: legacy evidence retained, default cognition quarantine

**Recommendation P3-LEGACY-01: fail-closed on cognition use, preserve bytes for review.** Apply only after coordinator authorization and an independently tested migration plan.

1. Classify every promoted candidate with a missing or malformed `memory_candidate_source_review` as `LEGACY_UNATTESTED` in an additive, versioned eligibility projection. Do not confuse the historical `PROMOTED` status with a fresh attestation.
2. **Block automatic recall and cognitive projection** of unattested candidates by default. Preserve existing canonical originals, candidate IDs, source copies, correction links, timestamps, statuses, and audit data exactly as stored. Do not silently delete, backfill, regenerate, or automatically promote anything.
3. Permit an **authenticated owner, private-audience, explicit re-review** flow only when current exact originals can be matched and bound to a current principal/audience and a single canonical writer. Record evidence hash, reviewer identity, original IDs, scoped audience, decision timestamp, policy revision and writer generation in an append-only event. Re-attest using governed transactions, not direct model output.
4. If originals were deleted or changed, the session no longer has valid authority, or the candidate is revoked/expired, keep it quarantined and ineligible. A blank/missing original is not permission to invent provenance. If retention forbids keeping the source, the deletion/erasure ledger takes precedence.
5. Imported ChatGPT history remains **historical source evidence only**, not automatically a reviewed memory. A private-channel flag does not authorize cross-audience egress.
6. During compatibility rollout, inventory counts per audience and version without exposing raw content in logs; compare old vs proposed eligibility in a sandbox. Require negative tests for missing review, forged reviewer/audience, source deletion, owner revocation, correction precedence and backup resurrection. Quarantine state must survive restart/restore and must not be downgraded by old clients.
7. Never overwrite `memory_candidate` status to a made-up enum value without a backward-compatibility plan. Use a separate effective-eligibility policy/version first. Require explicit coordinator and owner approval before enabling it against canonical state.

### Open policy questions for approval

- How should owner-confirmed legacy memories without surviving original transcripts be treated: permanently excluded from cognition, or admitted as **new, separately sourced owner testimony** with their old candidate retained for audit? Recommend the latter only via a new approved candidate, never forged historical provenance.
- Does earlier low-level `PROMOTED` mean an authorized reviewed act, or only historical import? Do not infer the former.
- When an old backup predates the new policy, what artifact and external ledger pins the minimum supported eligibility policy version?
- Which audiences are allowed to review a legacy item, and can local owner approval authorize later remote egress? Recommend **no implicit cross-audience carry-over**.
- Who signs the policy revision and its authoritative migration receipt?

## Core restart / backup / restore acceptance evidence required

A disposable success case must produce a cryptographically linked receipt with **exact repository SHA, test ID, OS build, interpreter version, run ID, timestamp, input fixture digest, output digest**, not just a unit-test count.

### Team 1 + Platform A single-writer fence

- Show exact authority issuer, `core_identity_id`, persisted identity UUID, canonical SQLite home file identity/digest, lease/term, generation and owner-host enrollment. No worker, standby, backup restorer or model may write without current authority.
- Exercise concurrent startup and stale lease, dead child with stale READY marker, crash before/after commit, split-brain attempted attach, STOP/revoked authority and attempted return of former host. Each negative must deny publication and show **zero extra writers**.
- Joining or rebuilt host always `REQUIRE_EXISTING`, never `FIRST_BOOTSTRAP`; preserve the same logical UUID. Restore replacement must validate current signed authority before any publication.
- Writer-generation change and state promotion must be atomic or provably fenced; a read-only shadow cannot become an independent writer.

### Team 5 backup / restore evidence

- Confirm full protected bundle scope: Constitution and trusted pin, canonical identity JSON, personality JSON and owner override store, canonical SQLite with conversation originals, scoped sessions, candidate/review/correction/expiry status, preferences and history, schemas, externally held erasure journal and applicable authorization metadata.
- Manifest must bind each file to immutable bytes and version and bind the logical Core UUID, source host, writer generation and backup chronology. Authenticate publisher/operator, not just a matching SHA-256.
- Prove encrypted snapshots from a quiesced/authorized writer or consistent SQLite snapshot. Verify `PRAGMA integrity_check`, `foreign_key_check`, no uncommitted partial rows and no broken audience references.
- Restore is staged and verified off-line before publishing. Protected replacement requires exact target + backup manifest + single-use owner authorization, live STOP checks, explicit source/recipient trust, no source symlinks or path redirects, and no second writer.
- The independently held, signed deletion/erasure ledger must replay **before restored content becomes recallable**. A pre-deletion snapshot cannot resurrect a deleted candidate, source, or derived scorer projection.
- Verify failure cases: corrupted manifest, wrong identity UUID, incorrect host enrollment, policy downgrade, changed Constitution hash, missing personality file, schema mismatch, truncated SQLite, interrupted stage/rename, revoked receipt, STOP mid-restore, lost journal and cross-audience source exposure. Reject or remain unavailable; never fall back to fresh identity or defaults.
- Capture pre/post state digest, identity UUID, exact conversation IDs and times, corrected memory eligibility set, audience constraints and signed receipt. Original writer remains fenced until authorized cutover; no Venus migration is in scope.

### Team 2 cognitive consumption evidence

- Provide authoritative Core request trace with *hashes and bounded redacted evidence*, showing Constitution + persistent profile reaches assembled prompt, and that private owner preferences and only eligible promoted memories are projected under correct principal/audience.
- Use a real supported Ollama model; record model tag/digest, provider configuration, context provenance and exact model response. Fake provider, mock or deterministic fixture responses do not satisfy genuine behavior.
- Reboot the same disposable state and prove a real multi-turn reply still observes approved preference and correction without inventing memories. Test fabricated user/model text attempting Constitution/personality rewrite and unauthorized promotion; prove neither caused a canonical write.

## Current scoped tests

`test/test_core_team3_disposable_continuity.py` covers:
- identity/Constitution/personality/session/pending memory persistence;
- pre-promotion altered original or audience rejection;
- post-promotion original or audience revocation of recall;
- corrected-memory replacement across two restarts;
- SQL trigger abort mid-correction with rollback of both statuses;
- failed atomic identity/personality file replace preserving previous bytes;
- current legacy memory eligibility characterization.

**Not yet acceptance:** actual process kill; signer trust-root verification; full host relocation; complete protected bundle restore; independent installed Windows SCM / Debian systemd proof; real model-generated use. G8 stays **0/16**.

## Request for decisions

Core Coordinator: decide P3-LEGACY-01 before changing runtime eligibility. Teams 1/5/Platform A: provide SHA-pinned agreement on receipt fields and writer/restore sequencing; Team 2: provide traceable cognitive consumption evidence. Until then: **draft only, no merge, NO-GO**.


## C-002-T3 approved disposable implementation (2026-11-08)

Coordinator authorized P3-LEGACY-01 **for disposable engineering implementation only**. This approval does not authorize any protected-state migration, runtime policy activation, real identity modification, production install or merge.

### Implemented isolation and version behavior

- `core.memory.eligibility_v1.ReviewedMemoryEligibilityV1` is an explicit per-consumer opt-in on `MemorySystem`. Production composition continues to construct `MemorySystem` **without** this policy. Existing legacy behavior remains intact on deployed configurations.
- The policy checks an explicitly installed canonical SQLite `core_memory_eligibility_policy` V1 marker. If marker is absent, including a pre-policy restored snapshot, the strict consumer raises `MemoryEligibilityVersionError` before providing memory. A different version or attempted downgrade also rejects. Installation needs private owner principal and expected-version compare-and-swap.
- V1 requires both `PROMOTED` and current `memory_candidate_source_review` owner/audience equality. It rejects unattested memories **before** ranking and rechecks before projection and at final `MemorySystem` handoff. Revocation, expired validity and original/audience integrity remain governed by pre-existing canonical checks.
- `MemoryReviewService.re_review_legacy_promoted` requires the owner-bound private audience and exact unchanged conversation originals. `DurableMemoryCandidateStore.reattest_legacy_promoted_originals` writes a current-source attestation and SHA-256 audit receipt inside **one BEGIN IMMEDIATE transaction**, revalidating exact source metadata again inside the same writer transaction. Failure leaves historical status and sources unchanged and produces no attestation.
- For missing originals, `MemoryReviewService.propose_owner_testimony` creates a **new** candidate from a freshly authored, authenticated owner USER message in a current bound session. The separate `core_memory_owner_testimony` source pointer persists and still requires explicit owner promotion; it never fabricates historical attestation or mutates the old candidate.
- Historical rows, originals, corrections and history remain in their original tables. There is no destructive backfill and no automatic provenance promotion.

### Boundaries not yet proven

- An in-SQLite V1 marker is **not** an independently authenticated external policy floor. A restored backup containing older marker bytes cannot be evaluated against a trusted monotonic external policy record until Team 1/Platform A/Team 5 define that contract. With strict V1 explicitly enabled, missing/downgraded marker fails closed; but production has **not** enabled strict V1. Do not count this as installed-host restore/no-resurrection certification.
- `PrincipalContext` validation is a necessary application-layer check, not proof of cryptographic enrollment by itself. Single-writer authority and operator credentials are still owned by external Platform/SAFE admission.
- SHA-256 source digest is integrity evidence inside a governed canonical write, **not** an independently signed external receipt.
- Tests are synthetic. Team 2 must prove genuine Ollama model consumption; Team 5 must independently replay restores and external erasure journals.

### Proposed supervised migration sequence (NOT authorized to execute on protected state)

1. Pin current HEAD, signed artifacts, schema, identity UUID, Constitution expected digest, owner enrollment, lease/generation, and authorized offline snapshot; obtain Team 1/Platform A writer-fencing ACK plus Team 5 restore policy.
2. Stop the authorized writer, capture integrity-protected backup + separately authenticated erasure journal and external minimum policy version. Verify snapshot consistency, record hashes and ensure old authorizations are fenced.
3. On **disposable clone only**, install V1 using an explicit owner-issued decision and version compare-and-swap. This does not auto-promote historical candidates. Inventory attestations and ineligible legacy candidates without leaking source text.
4. Re-review each eligible legacy record only if its unchanged exact originals and current private audience remain provable; record new attestation/receipt atomically. Quarantine all others.
5. Where originals are absent, record a fresh owner USER testimony in a newly authenticated session, create a **new** candidate with truthful present-day source and require separate approval to promote it. Keep old candidate quarantined.
6. Test revoked, corrected, expired, erased, cross-audience, interrupted-write, duplicate-writer and pre-policy backup restores; replay externally signed deletion ledger before any recall. Enforce external policy floor even if restored SQLite is older.
7. Require independent Teams 1, 2, 5 and Platform A ACK, exact signed artifact bytes, verified negative-test receipts, and an **explicit separate owner authorization** for any later protected migration/activation. None is granted by C-002-T3.

### Exact implementation tests (pending verified CI)

`test/test_core_team3_legacy_policy_v1.py`: quarantine without deletion; owner re-review persistence; missing/edited/audience-rebound original denial; cross-audience owner denial; fresh owner testimony; old snapshot no-policy denial; downgrade rejection, owner scope and expected-version checks; interrupted attestation rollback; corrected/revoked/expired exclusion.

Additional existing `test_memory_deletion_restore.py` must prove independent operator erasure-journal precedence, but passing it does not prove real-host backup installation. Combined Team 3 CI includes that fixture and whole-application restart tests.

**Policy version:** V1 / `P3-LEGACY-01`; approval: disposable engineering only; activation: OFF; G8: 0/16; Core shakedown: NO; production GO: NO.
