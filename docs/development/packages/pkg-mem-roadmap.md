# PKG-MEM | Durable memory, provenance and reviewed learning

**Branch:** `feature/pkg-mem-foundation`, forked from `main` at `2141879`. **Status:** independent planning and pure proposal validation only. The package follows an accepted PKG-INTERACT release; no database schema change or migration has occurred on this branch.

## Outcome and reuse
Preserve original messages with stable session, author, timestamps and IDs; make derived memories traceable and correctable. Reuse the existing conversation store, memory system, emotional journal and interaction evidence rather than creating an incompatible second database. Historical conversation, inferred emotion, lab fixtures and a user's pats must not silently become Sofía's standing preferences. The existing stores are foundations, not proof of complete archive import or recall.

## Implementation slices
1. **M0 inventory:** pin exact SHA; catalog existing tables, indexes, source IDs, retrieval limits, schema versions, backup path and retention policy. Confirm which past conversations actually exist; do not invent missing history.
2. **M1 originals and derivations:** immutable preserved content and per-source provenance, ordering, author, timestamp and separately marked inference. Write append-only corrections or tombstones with auditable lineage. Avoid storing sensitive plaintext in debug exports.
3. **M2 retrieval:** scoped relevance and recency, explicit memory budget and omissions, conflict and uncertainty handling. When the model has no supporting original, do not claim recall. Test that summary text cannot supersede canonical identity.
4. **M3 reviewed learning:** propose candidate preference or relationship revisions with actual supporting saved-message IDs, reviewer identity, explicit approve/reject, expiry/revocation and provenance. `src/sofia/package_foundations/mem.py` is only an eligibility prototype; its reviewer field is not authentication and it writes nothing.
5. **M4 archive import:** staging parser for ChatGPT archive, deduplication, timestamp/role validation, privacy classification, dry-run manifest, reversible commit and crash/resume. Never import private material into an unrelated user's scope.
6. **M5 recovery and integration:** migration on **copies**, rebuildable indexes, backup/restore, deleted-source behavior, scoped interaction/REL context and bounded runtime latency.

## Acceptance, risks and ownership
- Run `python -m pytest -q -x test/test_pkg_mem_foundation.py` on this branch. Add negative tests for forged source IDs, tampered reviewer identities, duplicate imports, contradictory memories, deletion and power-loss replay before integration. No tests have been run against this new branch yet.
- Full suite on pinned SHA, multi-restart live recall citing an actual original, safe wrong-user denial and independently reviewed migration/rollback. Record actual provenance and retrieval omissions, not just model plausibility.
- **Dependencies:** INTERACT supplies source-linked gestures; CORE supplies canonical trust order; REL supplies optional reviewed interpretations; SAFE controls privacy and erase; VERIFY owns measured evidence. Do not cherry-pick unmerged package prototypes as if APIs were accepted.
- **Prohibited shortcuts:** production DB reset, inferred consent from frequency, automatic preference promotion, rewriting originals or claiming historical knowledge without provenance.

**Release:** explicit schema/privacy review and separate merge approval. All milestones except the tiny pure prototype remain pending.
