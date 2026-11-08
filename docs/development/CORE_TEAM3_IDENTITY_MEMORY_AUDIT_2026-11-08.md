# CORE-003 | Team 3 identity, personality, memory and continuity audit

Date: 2026-11-08. Base: `main@dd7020ce48c06e82684d3439779266de9ea965b4`.
Scope: source inspection plus new isolated regression tests; **no real-host G8 acceptance**.
Only disposable `tmp_path` identity, personality, constitution, conversation and SQLite state.
No production Core startup, secret inspection, migration, release, merge or canonical-writer change.

## Evidence classification

- **INSPECTED** means implementation and existing tests reviewed, not an execution claim.
- **NEW TEST / UNVERIFIED** means a regression was committed but an exact-head test result is still required.
- **BLOCKED** means host proof or cross-team contract is missing.
- Existing G8 real-host acceptance remains **0/16**, notwithstanding unit tests.

## Source findings

1. `src/sofia/core/constitution/store.py`: normalized LF/CRLF content is SHA-256 checked against an expected 64-hex digest. A malformed or mismatched digest raises `ConstitutionIntegrityError` (INSPECTED). This is integrity against a trusted pin, *not a cryptographic publisher signature*; trusted pin protection and approval remain external operational requirements.
2. `src/sofia/core/identity/store.py`: persistent logical UUID survives normal loads; `REQUIRE_EXISTING` rejects a missing/malformed UUID and refuses a missing file. `FIRST_BOOTSTRAP` intentionally mints the UUID on an absent file and upgrades legacy identity without one (INSPECTED). REQUIRE_EXISTING is mandatory for joining/rebuilt nodes. A raw `save()` does not itself implement generation-fenced compare-and-swap; writer authority must be proved in runtime/Platform contracts.
3. `src/sofia/core/personality/store.py`: JSON save uses same-directory atomic replacement; loader validates field types and fails on missing/corrupt JSON (INSPECTED). There is no per-profile cryptographic hash, signature, or monotonic revision in the store itself. Durable behavioral propagation to actual provider replies requires Team 2's inference observations.
4. `src/sofia/core/conversation/store.py` and `src/sofia/platform/state/canonical_sqlite.py`: canonical SQLite file identity is pinned, reopened paths are checked, and message-ID collisions with changed bytes or time raise errors (INSPECTED). An authorized session binding remains an application-layer requirement.
5. `src/sofia/platform/application/memory_review.py`: owner/private review scope, exact current originals, original bytes/order/time, and current audience are checked before promotion. `src/sofia/core/memory/provenance_store.py` checks current-original linkage again for reviewed candidates at recall (INSPECTED). Model text does not itself serve as owner approval.
6. **Legacy provenance decision required:** `DurableMemoryCandidateStore.is_recall_eligible()` returns true for a promoted candidate lacking the newer `memory_candidate_source_review` guard. Existing `test_memory_review_source_revalidation.py::test_legacy_unattested_candidate_is_not_silently_deleted_by_migration` explicitly covers this compatibility path. This is not by itself proof of an exploit, but Team 3 needs a policy for legacy recall without current original attestation before certification.
7. Existing `test/test_application_restart_continuity.py` covers app-level messages, reviewed candidate promotion, preference revision, durable goal and one negative authorization path on synthetic state. This is historical source evidence, not a new execution receipt.

## New cross-store disposable tests

File: `test/test_core_team3_disposable_continuity.py`.

| ID | Scenario | Status |
| --- | --- | --- |
| T3-01 | Identity UUID, personality traits/style, same session original and pending reviewed candidate persist through closed-store restart, then owner promotion | NEW TEST / UNVERIFIED |
| T3-02 | Change original bytes between shutdown/reopen; deny promotion, keep proposed state | NEW TEST / UNVERIFIED |
| T3-03 | Rebind original audience between shutdown/reopen; deny promotion, keep proposed state | NEW TEST / UNVERIFIED |
| T3-04 | Invalid UUID, malformed personality and Constitution hash mismatch are rejected without minting a new canonical identity | NEW TEST / UNVERIFIED |

**Exact-head CI, runtime, Python matrix and host receipts have not yet been observed.** No green claims until GitHub workflow result is checked against the final head SHA.

## Verification matrix

| Capability | Source contract | New execution | Required proof |
| --- | --- | --- | --- |
| Constitution hash mismatch | INSPECTED | UNVERIFIED | Exact-head CI and trusted-pin lifecycle |
| Logical identity / UUID | INSPECTED | UNVERIFIED | Cross-host fenced restore, same UUID |
| Personality store restart | INSPECTED | UNVERIFIED | Provider-consumed profile and stable behavior with Team 2 |
| Preferences and opinions | Existing tests INSPECTED | NOT RUN | Owner override persistence + cognitive observation |
| Conversation history | INSPECTED | UNVERIFIED | T3-01 plus real runtime restart |
| Reviewed memory promotion | INSPECTED | UNVERIFIED | T3-01/02/03, audit receipt |
| Corrections / revocation / expiry | Existing tests INSPECTED | NOT RUN | Retrieval before/after correction under same audience |
| Privacy / audience | INSPECTED | UNVERIFIED | Cross-channel negative tests and owner scopes |
| Deletion / retention | Existing erasure code INSPECTED | NOT RUN | Backup restore no resurrection with Team 5 |
| Portable state and writer fencing | Existing code INSPECTED | BLOCKED | Team 1 + Platform A writer-generation receipts |

## Cross-team handoffs

- **Team 1:** verify process lifecycle, writer lease, generation/token fencing and `REQUIRE_EXISTING` on recovered/joined nodes, including restart after partial file write.
- **Team 2:** prove personality traits/preferences actually enter provider cognition and alter observed replies without pretending output text is authoritative state; test memory-injection denial in live conversation.
- **Team 4:** define canonical state portable manifest: logical UUID, constitutional trusted pin, personality revision, conversation original IDs/times, memory status and source attestations, deletion ledger, audience bindings, app schema, generation/fencing and source/recipient verification. No second writer.
- **Team 5:** prove encrypted backup, erasure journal, restore atomicity and no post-restore resurrection; sign real host receipts.
- **Platform A:** coordinate single-writer and enrollment authority for any later test relocation.

## Coordinator planning baseline (unchanged)

Batch percent: C01 45; C02 50; C03 40; C04 30; C05 25; C06 35; C07 15.
Maturity percent: Runtime 45; Identity/cognition 55; Memory/continuity 40; Link/mobility 30; Safety/auth/recovery 35; Channels/companion 35; Release QA 20.
Core engineering planning estimate **40%** (range **35–45%**, remaining **60%**).
G8 installed real-host acceptance **0/16**. These are coordinator estimates, not measured percentages.

## Release decision

**NO-GO for Core identity/continuity certification.** Tests are useful engineering evidence after exact-head CI passes but never a substitute for independent installed-host acceptance or proof of canonical owner authorization.
