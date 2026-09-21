# PKG-MEM: original-message retrieval preflight and review

**Status:** isolated candidate, not integrated, deployed, or accepted. Base branch `main`; preserve all production state and backups.

## Coded slice

`src/sofia/memory/retrieval_projection.py` projects existing `ConversationMessage` originals by stable message ID within one caller-provided session. It preserves exact original text, timestamps, role, and input position, deduplicates requested IDs, rejects duplicate originals and unzoned timestamps, and returns separate missing/omitted IDs. Character budget is a deliberately honest approximation, **not a token count**. No original is silently truncated. Other-session IDs are indistinguishable from absent IDs in results.

**Focused command:** `PYTHONPATH=src python -m pytest -q test/test_memory_retrieval_projection.py`. Isolated Python 3.13.5 / pytest 9.0.2 test run: **23 focused cases passed**, alongside VERIFY's 20, **43 combined passed** using a local test-only stand-in for the fetched existing `ConversationMessage` class. The uploaded GitHub source and tests must be checked against a real checkout, including Windows and full suite. The stand-in was never committed.

## Review at package gate

- Authenticate the owner and session *outside* this pure function. Existing `ConversationMessage` contains a session ID but not a verified user principal. **This function is not sufficient multi-user access control**; bind a session to Sparks before passing originals and implement per-principal isolation when multi-user is authorized later.
- Reconcile with existing `sofia.conversation.store` and `sofia.memory` rather than copying original-message databases. Bind to read-only session-scoped queries; test malicious IDs, duplicate IDs, deletion, correction and summaries against actual stored evidence.
- Add durable original preservation, archive import, controlled promotion of candidates, explicit retention/deletion including derived indexes and restore, migration/rollback on disposable DBs, and privacy-negative tests. These are **not implemented here**.
- Evaluate true provider token budgeting with measured tokenizer; this slice only counts Python characters. Verify evidence omission is displayed, and unauthorized material is filtered before retrieval and prompt assembly.
- Run focused, integration, pinned full-suite, restart/recovery and supervised live memory-quality checks after INTERACT is accepted. Record revision/environment/results accurately. No identity/Constitution edits or DB migration are authorized.
