# Phase 03: staged relocation, without an unauthorized cutover

`sofia.ops.state_relocation.stage_verified_state_home` reuses the **existing** `BackupEngine.create/verify/restore`, rather than inventing raw SQLite copying. It requires an independently authenticated control-plane callback to verify both an exact owner approval and a fenced writer. The method rejects known missing/unclassified source-home files, nonempty destination roots, overlapping backup roots and inadequate space. It then creates a consistent encrypted backup, verifies the backup manifest, and restores to a fresh destination using existing semantic and protected-identity checks.

**It is not a Move button.** It neither changes the signed external home pointer nor activates or starts a new writer. The returned `StagedStateHome.activated` is always `False`. The trusted migration broker, persistent exclusive lease/writer epoch, signed location-pointer promotion, authenticated client reconnection, independent rollback and full asset inventory are still required before a user-approved cutover.

**Coding only; no test or actual file movement performed.** The callback must be owned by a privileged operator host, never replaced with an LLM assertion or a boolean from conversational text. Do not run this on live production state without a confirmed externally fenced writer and tested recovery.
