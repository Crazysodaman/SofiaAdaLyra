# Phase 00 CA-003/CA-1208: partial multi-question trust isolation

Revision target: 2026-10-14. The production runtime preserves recognized
deterministic self/environment answers within a composite user question.
Previously it also placed each **verbatim user-authored question clause**
inside the trusted SYSTEM message. An adversarial second clause could
therefore appear as privileged prompt instructions while remaining plain
user content.

The same canonical `respond_with_runtime_context` now keeps deterministic
host answers in SYSTEM and serializes original clauses into a separate
USER-role JSON quotation before the genuine current USER turn. It does
not treat the metadata quotation as a new user command. Existing response
routing and real source resolvers are unchanged. A production runtime
integration test checks a multi-question payload with a spoofed
`SYSTEM:` clause and verifies that it appears only in lower-trust input.

The earlier Phase 00 patch similarly lowered untrusted conversation
history from SYSTEM to USER JSON data; the two changes close related
prompt authority-crossing paths, not all prompt injection vectors.
Do not award Gate 4 without pinned CI, other retrieval/memory channel
audits and independent safety review.
