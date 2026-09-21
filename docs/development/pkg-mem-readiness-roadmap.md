# PKG-MEM | branch readiness roadmap

**2026-09-21 | draft PR #9 | baseline head `5b411cccc8c661d2abf3586360fe5633061f31ba` before this update. Offline slice, not an integrated memory product.** Also read `pkg-mem-original-retrieval-review.md` and root `ROADMAP.md` for the original-memory/learning outcome.

## Existing, evidence and limitations

Read-only source-preserving selection of `ConversationMessage` originals by ID in a caller-authorized session with explicit omitted/missing IDs and timestamp validation. **23 focused tests passed on equivalent staged code with a test-only conversation-model stand-in**, not on an actual GitHub checkout; no verified auth, persistent user memory or archive import. Existing conversation and emotional journals on main are separate foundations; don't introduce a second database.

## Next code and test gates

1. Inspect/pin actual `ConversationMessage`, conversation store, emotional/reflection journals, schema/migrations, source timestamps and auth/session boundaries. Reconcile interface against INTERACT PR #2 rather than copying its parser or state.
2. Implement/store **immutable original content**, stable actor/session/order/time and source pointers; derivations, summaries and reflection hypotheses must link to originals, declare omissions/uncertainty and never replace the original. Keep protected canonical identity and Constitution independent of recalled text.
3. Add reviewed preference-candidate lifecycle (propose, evidence, correct/reject, promote, revoke); source changes, contradictions and deletion propagate into indexes and workbench pages. Private reflections remain unshared until an independently authorized audience is granted.
4. Plan/test an opt-in, deduplicated ChatGPT archive importer with source hashes, provenance, dry-run and reversible migration on **disposable DB copies only**; malformed, cross-session and duplicated imports fail safely. Decide retention/export/delete policy with Sparks at this gate, not by guessing.
5. Run on actual branch + Windows Python 3.12.9: `python -m pytest -q test/test_memory_retrieval_projection.py`; targeted conversation/MEM regression; restart/reopen, corruption, correction, deletion, unauthorized retrieval, prompt-injection and backup/restore negatives. Then coordinated full repo pytest after INTERACT acceptance.

## Decisions requiring review

Choose encryption/retention/erasure and original-versus-derived record longevity; verified single-account session binding; archive location/consent; retrieval token-budget behavior; how modeled emotional appraisals can influence responses without being treated as authoritative facts. No second-user memory until future SOCIAL scope is explicitly approved.

**Exit:** isolated retrieval slice tested only. GitHub checkout, current Windows/full suite, persistent database and restart tests, private/audience review and migration acceptance = **NOT RUN**. No prod `state/sofia.db` changes, merge or deployment.
