# Workstream 2 / Phase 03 • Recovery and relocation source-to-sink audit

**2026-10-11. Branch `main` only.** User has deferred tests/CI/host changes. Audit categorizes **11** original V18 requirements, including **9** previously unassessed. **Partial wiring is not acceptance.**

## Current architecture and fixed operator decisions

- Venus remains sole active writer of canonical `sofia.db`. The future Debian VM named `Sofia` on Artemis may become the single writer ONLY through a separately verified, operator-authorized exclusive writer lease/fencing and explicit cutover. Venus can provide remote GPU inference over authenticated communication; no silent fallback, dual writable SQLite, or automatic failover.
- A trusted external deletion journal and external pointer authority exist outside the state home. A full encrypted candidate may be **staged** to a verified nonactive destination, never automatically promoted.
- No verified privileged broker supporting cross-host atomic lease issuance and old-writer fencing has been demonstrated. Local SQLite locks and signed manifests do NOT substitute for a cross-host writer fence.

## Original requirements and actual production owners

| ID | Existing inspected production sources | What remains before code-complete/acceptance |
|---|---|---|
| CA-3704 | `ops/state_relocation.py:stage_verified_state_home`, `state_promotion.py:prepare_pending_state_pointer`, `config/state_home_pointer.py:read_verified_state_home` have typed approval, verified staged candidate and nonactive signed handoff | Privileged old-writer fence/epoch broker, device re-pair/PKI failback, active-pointer transaction, audited rollback and chaos proof |
| CA-3707 | `ops/recovery.py:RecoveryObjectives/RecoveryGuard`, synthetic fault-injection contracts in `test/test_venus_artemis_relocation_evidence.py`, `test/test_state_relocation_atomic_publish.py` and `test/test_ws2_pending_pointer_handoff_recheck.py` | Full isolated network partition, disk pressure, stale cert and skew matrix with defined blast-radius/RPO/RTO measurement; fixtures not run |
| CA-5202 | `ops/backup.py:BackupEngine.create/restore`, `state_relocation.py`, `memory/deletion_ledger.py` handle online SQLite snapshot, encrypted component manifest, protected identity, external signed erasure replay and failure-domain staging | True consistent epoch across cold/warm archives, attachments/media, dual backup copies, key epoch and all external mutation producers |
| CA-5204 | `BackupEngine.verify/restore`, `ops/recovery.py:RecoveryGuard` and synthetic restore/erasure fixtures | Genuine clean-machine restore drill with missing keys, broken WAL, newest erasures, OS migration and observed RPO/RTO, not a successful test claim |
| CA-5205 | `ops/recovery_export.py:export_portable_conversations` provides reviewed, bounded, open structured source export with hashes plus `ops/backup.py:BackupManifest` | Independent standalone parser/validator, complete schema/codec interoperability over all protected assets and human-readable cold recovery runbook acceptance |
| CA-6101 | `state/canonical_sqlite.py:CanonicalSQLiteGuard`, `config/state_home_pointer.py`, `ops/state_relocation.py` prevent missing-state silent bootstrap and keep staging nonactive | Independent host writer lease, fencing epoch and deliberate active-authority cutover; prior classification already partial |
| CA-6105 | `BackupEngine._sqlite_snapshot/_collect_files/create`, `BackupManifest`, `memory/deletion_ledger.py`, `state_relocation.py` cover core snapshot, protected assets, component manifest, separate erasure replay | Archive/attachment generation binding, cryptographic keys/recovery catalog, independent multi-domain checkpoints and monotonic epoch |
| CA-6108 | `BackupEngine.restore` replays signed journal into restored SQLite; `memory/deletion_ledger.py:verify_applied` enforces anti-resurrection; `state_relocation.py` stages only under fresh fence witness | Complete archive tombstone propagation, re-pair and external action uncertainty resolution, cross-host old-writer fence, no active authority implied |
| CA-6803 | `ops/state_mobility.py:discover_local_state_candidates/inspect_state_relocation` inventories owner-selected roots and emits candidate evidence without activating by filename | Full Settings UI workflow, trusted identity/epoch lineage provenance for every discovered provider/root and delegated operator approval |
| CA-6805 | `config/state_home_pointer.py:read_verified_state_home`, `ops/state_promotion.py` sign nonactive pending handoff without modifying live locator | All startup entrypoints/tray/watchdog using one externally validated active locator; post-fence active pointer publication/rollback and env precedence acceptance |
| CA-6807 | `ops/state_mobility.py:inspect_state_relocation`, `state_relocation.py`, `state_promotion.py` block redirected destinations, unsuitable filesystem, missing assets, low confidence | Robust privileged Windows/Linux ACL, removable disk, space/headroom, case/collision and concurrent ancestor replacement checks; prior classification already partial |

## New production changes in this audit continuation

- **Item 82** fixed post-rename staging cleanup masking a typed durability-uncertain publication receipt: `8a72fb269e8a8a142e7b9e7bc543fba61f02e316`. Deferred regression: `25395ae1a0f22f0d60cfabef9fbc15a3ac7eecfd`.
- **Item 83** rechecks privileged pending-handoff approval at output-creation boundary, rejects symlinked staged database/protected identity: `4b583eee6b45fca6c083a4e26fadd96b0afc0ed1`. Deferred regression: `d006827a13da5139872a5beb7511bf451afe4398`.
- **Item 85** revocation-safe external signed erasure request: `6a01ecc4b64cbbe36bfd6e5f0a2d63c08d5d1281`. Deferred regression: `4135c1586eba49409716e4f27b5ffe646816132a`.

## Blocking gates

**The cross-host single-writer broker is still missing production proof.** Do not authorize any cutover or host-wide migrations based on these source-only changes. All 11 requirement statuses remain `partial_wiring` and `accepted=false`; no tests/CI, original owner files, active VM, PKI, pointer, physical recovery copy, backup rotation or erasure operations were performed.
