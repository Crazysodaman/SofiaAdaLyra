# Workstream 2 • Phase 06 source-to-sink audit, batch 1

**Date:** 2026-10-11  
**Branch:** `main` only  
**Acceptance status:** production-source audit and coding, **no tests, CI, live migrations, or host operations executed**.  
**Authority:** Venus is the sole canonical writer until separately approved, independently fenced migration.  
**Classification:** `partial_wiring` means concrete live source exists, but complete original V18 requirement has **NOT** been established. Do not translate it to percent complete.

## Production change: Item 63, bounded clothing/wardrobe conversation context

`ConversationService._respond_once()` used `ConversationStore.list_messages(self._session.id)` after persisting each user turn, and then scanned that entire tuple for previous assistant/user content. This was independent of `_build_request()`, which already used `recent_messages(..., limit=96)` to bound LLM context. The clothing/wardrobe route thereby materialized potentially decades of data even when no historical search was requested.

The actual production `src/sofia/application/conversation_service.py` call now uses the existing SQL ordered `recent_messages(..., limit=64)`; the entire canonical transcript remains preserved and available through separately authorized history, exact-source and retrieval routes. Commit `03ff01b5d9103322ff91246cb368b357c1f54b76`, regression source `test/test_ws2_bounded_wardrobe_context.py` `02d191832272a514a7a822f4fa663d484920428e`. Tests **authored, not run**.

## Exact original V18 requirements audited

| ID | Verified code path and behavior | Remaining full production / acceptance gap | Audit state |
| --- | --- | --- | --- |
| CA-301 | `life/model.py:ExperienceRecord`; `life/store.py:record_experience, project_experiences, experiences` persist original audience-scoped, typed LIFE episodes with evidence references | No established non-project autobiographical episode bridge or ordinary conversation retrieval for non-project experiences; avoid a competing episode store | Partial |
| CA-4201 | `cognition/v2/contracts.py:ConversationFocus`, `cognition/v2/focus.py`, `application/conversation_service.py:_coordinate_turn` and bounded recent context establish typed focus and context windows | Working memory as a separate ephemeral bounded focus stack, lifecycle/teardown and measurable latency/token ceiling not end-to-end established | Partial |
| CA-4204 | `application/conversation_learning.py:observe_user_message` creates proposed source-bound candidates; `application/memory_review.py:promote` rechecks exact authorized original bytes and private reviewer; `memory/provenance_store.py` retains candidate/correction/revocation | Fully typed temporal truth, per-claim semantic validity/conflict logic and broad source class corrections still incomplete | Partial |
| CA-4207 | `conversation/store.py:recent_messages, list_messages_page, exact_originals`; `application/conversation_service.py:_build_request` uses recent 96; new Item 63 removes another unbounded hot-path read | Context cost tests, archive tiering and long-term disk/retention budgets not accepted; explicit export/history paths may still intentionally materialize originals | Partial |
| CA-5001 | `application/conversation_service.py:_build_request` performs bounded recent selection and `HistoryPolicy.RETRIEVE_SPECIFIC`; fallback uses `conversation/fulltext_search.py` and `ConversationStore.search_messages` | Unified deterministic cross-layer temporal/episodic/procedural budget and verified benchmark costs not complete | Partial |
| CA-5002 | `conversation/fulltext_search.py:rebuild_offline` maintains canonical external-content FTS5 with insert/delete/update triggers and `keyword_search` scopes source rows to current principal, audience, session | Index state maintenance, multilingual/alias typo tests, offline repair acceptance and sustained 1M+-event performance unverified | Partial |
| CA-5603 | `conversation/store.py:list_messages_page, exact_originals, recent_messages`; `memory/originals.py:ConversationOriginalRetriever.retrieve`; Item 63 closes another live unbounded path | Full all-callsite audit, archive keyset paging and verified scale/retention tests remain; original ledger status was **already partial**, so no new completion claim | Partial (already) |
| CA-5604 | `application/conversation_service.py:_build_request` authorization-aware full text source selection, `conversation/fulltext_search.py:keyword_search` SQL audience revalidation and canonical original rows, `memory/originals.py` exact retrieval | Full temporal/correction-aware lifetime cross-thread source-class authorization and evidence fallback still incomplete | Partial |
| CA-5805 | `application/conversation_learning.py` proposes source-linked candidates; `application/memory_review.py` requires private owner for promotion; `memory/provenance_store.py` owns status transitions, corrections, revocation | Independent long-horizon knowledge evaluation, candidate ranking/duplicate consolidation and full UI acceptance unproven | Partial |

**Audit math:** This batch inspects 9 requirements: 8 previously `unassessed` now have concrete partial code evidence, 1 (CA-5603) was already partially assessed and gains a new production evidence commit. No item becomes `accepted` or `code_complete`. The other Phase 06 requirements must still be individually traced before percentages are credible.

## Next source-to-sink gaps

1. CA-302/CA-303/CA-304 and CA-307: typed non-project observations, identity/audience-safe episode references and ordinary conversation retrieval using existing LIFE ownership.
2. CA-1701–1704 / CA-5901 onward: correction propagation, bitemporal validity and independently reviewed relevance feedback; no unverified memory promotion or self-reward.
3. CA-4208 / CA-5004–5005: derived summary invalidation/repair and sourced rolling snapshots, never overwrite originals.
4. CA-5603 and CA-5002: full original/history API caller audit, memory/CPU benchmarks and recoverable index repairs.
5. Phase 03 privileged cross-host writer fencing remains incomplete and blocks live migration regardless of source-only fixes.

No platform test was executed. All above statements describe inspected code paths and unverified gaps, not feature acceptance.
