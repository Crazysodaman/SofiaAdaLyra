# PKG-MEM | readiness roadmap

**Accepted gate: 2026-09-24 | PR #9 merged to main.**

## Accepted implementation

The original/provenance gate is integrated on `main`. It now provides exact persisted conversation-original retrieval scoped to one authorized session; durable provenance-backed memory candidates; explicit propose/promote/reject/revoke lifecycle; promoted-only cognition projection and deterministic relevance retrieval; source invalidation propagation; and a reviewed workflow that can create a candidate only from exact persisted source messages.

Evidence recorded at acceptance: **54/54 focused PKG-MEM tests passed** on the user's Windows Python 3.12 environment after one test-fixture correction, followed by a reported **full repository pytest pass**. Production `state/sofia.db` was not intentionally modified or committed by this gate.

## Remaining gates

1. Bind memory/session access to authenticated PKG-SOCIAL principals and audiences rather than relying only on caller-provided session authorization.
2. Decide and implement retention, erasure, encryption, export and derived-index propagation policy.
3. Add opt-in, deduplicated archive migration with source hashes, dry-run, rollback and disposable-database acceptance.
4. Add backup/restore, corruption/recovery and deletion/correction integration acceptance across restart.
5. Integrate promoted retrieval into the final cognition path with measured provider/token budgeting and supervised live memory-quality tests.
6. Keep canonical identity and Constitution protected from recalled or imported text.

**Current state:** original/provenance gate accepted and merged. PKG-MEM as a whole remains active until the remaining privacy/migration/recovery/live-quality gates are accepted.
