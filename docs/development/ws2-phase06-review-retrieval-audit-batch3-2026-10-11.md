# Workstream 2 • Phase 06 source-to-sink audit, batch 3

**Date:** October 11, 2026  
**Branch:** `main`  
**Authority:** unchanged Venus sole canonical writer until independently authorized host fencing.  
**Acceptance:** none; production source commits and deferred tests are unexecuted.

## Four original requirements with existing partial production implementations

| Requirement | Actual source route inspected | Code present | Missing to count fully code-complete |
| --- | --- | --- | --- |
| CA-4206 | `ConversationService._build_request` → `HistoryPolicy.RETRIEVE_SPECIFIC` → `ConversationFullTextSearch.keyword_search` → `ConversationStore.search_messages` → original text | Explicit recent-window versus bounded historical retrieval exists; Item 65 requires the current social principal/audience in the fallback SQL statement | Complete cross-session/type/time/skill/episode routing, hard latency budgets, cited exact-source final answer and objective recall evaluation |
| CA-5006 | Same `ConversationService._build_request`, `memory/originals.py`, optional FTS and source guard | Host-injected context labels retrieved originals as conversation evidence, not instructions; no unbound historical recall; old indexed sources cannot grant permission | Explicit no-evidence abstention for all eligible memory categories, independently approved cold archive retrieval, source revalidation UX, channel-specific provenance |
| CA-4806 | `MemoryReviewService`, `DurableMemoryCandidateStore`, external `MemoryDeletionLedger` | Private reviewer controls promotion, rejection, revocation, source-scoped expiry, correction and separately approved deletion; Item 68 checks the original candidate audience for **all review mutations** | Complete user-facing inspect/export/hide semantics across archive/cache/offline replicas and independent provider copies; cross-device owner-control acceptance |
| CA-5903 | `ConversationLearningCoordinator._is_learnable` → `MemoryReviewService.link_correction/promote` → `DurableMemoryCandidateStore.promote` | Explicit dated user corrections are proposed, not automatically trusted. Reviewed promotion atomically revokes a same-scope former promoted fact and promotes the new proposed candidate in one `BEGIN IMMEDIATE` transaction; original source rows remain preserved | Generalized bitemporal interpretation/validity intervals, cascading derived-summary/NEURO/vector invalidation, ambiguous contradiction triage and full as-of-time recall |

## Source findings and concrete code produced in this audit continuation

- **Item 65** fixed the original source-scope fallback race: `src/sofia/conversation/store.py` and `src/sofia/application/conversation_service.py`; production commits `65e801fa556df6e072e6cb7dcfc404a2911688c7`, `d71df32f637f832d94c71a1175040dac9cfe51e4`; deferred regression `854e0a9cf31963e1169a051689ec105edec37e95`.
- **Item 66** normalized new aware source timestamps and keyset cursors to UTC, and compared session activity by real instant; production commits `f35040afd44f790215793e131af45a977d480ef8`, `5e7cd961dbe6dc670e631f969c699a57ddfa85d8`; deferred regression source `5b73d82329f533f5c694531acf53e171ae4a14ca`. Historical mixed-offset rows remain untouched pending separately reviewed repair.
- **Item 67** prevents clearly fictional/roleplay claims from becoming automatic memory candidates; production `342fd21a85ef507840eaef70f89674fc94c34c5c`; deferred regression `c1e08d36b77e7c32ed1d7a772af5ff0692d4c10a`.
- **Item 68** requires current original private audience authorization for reject, revoke, expiry and correction, not only promotion; production `5010ea99910f1a1e08443c17c91fbafa5cfd00fe`; deferred regression `aca9a2fd5f98223c915c25e509a6fc94b7418b0c`.

Do not change an original requirement's `accepted` value from false or count these four as completed original tasks. The audited source is real; missing architectural and runtime coverage is also real.

## Next gates

1. CA-301/304/307: non-project autobiographical LIFE experience capture and read-only context injection, using independent source/authority validation without copying deleted or unreviewed memory text into a competing owner.
2. CA-4208/5004/5005/5903: derived summary and semantic index invalidation on corrections, revocations and erasure; reviewer and caller scope must remain original-bound.
3. CA-5901/5902/5905: actual bitemporal current/historical status, as-of-time source verification and contradiction abstention. UTC timestamp ordering alone does not satisfy these.
4. CA-5606/5607: offline archive segmentation and owner retention/forgetting rights with two separately verified retained encrypted snapshots per actual protected restore target.
5. Final tests/CI and privileged host migration remain deferred per owner instruction. No tests, migrations, builds, mobile dispatch or live deletions were run.
