# Phases 02 and 03: first source-code foundations (no tests yet)

**2026-10-10, main-only.** Phase 02 reuses `sofia.safe.permissions` policy and existing `PermissionStore`; `sofia.safe.review` reports static capability classification and active-grant concerns without granting access or interpreting LLM text as authority. Settings SAFE panel can review configured standing capabilities; this is not a full runtime registry coverage guarantee.

Phase 03 reuses `sofia.ops.backup.BackupEngine` and canonical `config.layout`. `sofia.ops.state_mobility` performs a read-only preflight: verifies source state presence, local destination form, symlinks, overlap, destination emptiness, conservative free space and expected protected files. Settings Advanced has **Preview state relocation**. It never moves, rewrites, attaches a second DB, or changes a bootstrap pointer.

**Not yet coded:** authenticated external location pointer; approved and fenced offline cutover, full asset/secret manifest, backup restore to empty destination with checksums/semantic integrity, rollback, human acceptance, cross-host split-brain protection, independently verified model-evaluation promotion, per-channel SAFE runtime audit.

**Not tested:** any source in this pass, per user instruction. Production use is prohibited until verified.
