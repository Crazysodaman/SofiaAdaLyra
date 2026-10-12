# V18 continuation: Phase 01 release/SQLite evidence and Phase 03/06 import authority

**Status:** source fixes committed directly to `main`; exact-revision CI and live acceptance pending.
**Original task inventory:** unchanged 700 IDs, 17 phases, 69 source topics.
**Latest shared ledger inspected:** `docs/development/v18-task-evidence.json` blob `f9160450268e6a4ef2d8699a02ea5e63f62e0324`, reviewed source `b3461b677fcf8464a100a956f224ea0d6a73bd75`.

## Conservative task counts

Ledger snapshot: **6** code-present/unverified, **194** partial, **500** unassessed, **0** accepted. 700 original IDs present. These states are not a measure of coding percentage; newly committed WS1–WS4 source evidence is not reflected automatically, and 500 unassessed does not mean absent features. This report does not reclassify a task or mutate the shared master ledger.

## Exact source commits in this continuation

| Commit | Production/test paths | Original task relevance | Status |
|---|---|---|---|
| [`bfdb28be8b9569d875777838d29a348e34619e71`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/bfdb28be8b9569d875777838d29a348e34619e71) | `test/test_production_dual_cognition.py`, `src/sofia/verify/cognition_v2_baseline.py`, `test/test_verify_v18_roadmap.py`, `test/test_verify_package_selection.py`, `test/conftest.py` | CA-3004/3005 plus Phase 01 nonempty package/roadmap verification | Source regression repair, **not accepted** |
| [`b7ce674758055d07776a36ee380355be0b57d727`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/b7ce674758055d07776a36ee380355be0b57d727) | `test/test_state_component_schema.py`, `test/test_state_replication.py`, `test/test_state_replica_seed.py`, `test/test_memory_correction_semantic_integrity.py` | Phase 01/03 SQLite source guard and fencing tests | Regression repair, **not accepted** |
| [`a43933626a3112fd44df0035d8d0565e0082b232`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/a43933626a3112fd44df0035d8d0565e0082b232) | `src/sofia/memory/import_chatgpt.py`, `test/test_chatgpt_memory_import.py`, `test/test_memory_reviewed_corrections.py`, `test/test_production_storage_boundary.py` | Phase 03 canonical state protection, Phase 06 evidence and reviewed memory import, Phase 01 test parity | Production CLI authority preflight plus regression repair, **not accepted** |

**Important production distinction:** The canonical SQLite and protected identity requirements added in earlier source commits remain in force. This work does not revert the state owner no-create safety rule. Disposable CI tests now bootstrap via `bootstrap_canonical_sqlite` or first-install `RuntimeStorageLayout` explicitly. The ordinary import CLI requires preexisting canonical state on both mutation branches; `--dry-run` does not create state. A separate independent approval for promotions and authenticated single-writer host topology remain necessary production acceptance gates.

## Actual CI observation vs extrapolation

At previous source `08a8718deca00a4cad444db5509364e5229fd59f`, Matrix Tests failed with production-configuration seed errors after protected-authority hardening, Windows package tests had a fixture overwriting its own ledger, synthetic pytest markers not matching real pytest items, 11 unclassified source tests, and widespread missing disposable SQLite initialization. The source commits above target these *specific* observed failures rather than globally enabling implicit database creation.

Actions were triggered for newer revisions, but earlier runs were cancelled as `main` advanced. No exact-SHA success has yet been verified by this report for `a43933626a3112fd44df0035d8d0565e0082b232`. Unrelated package failures and true application regressions must be diagnosed after a stable run. No run that was cancelled or failed is recorded as a pass.

## Workstream coordination

- WS1 remains the serialized owner of `docs/development/v18-task-evidence.json`. This separate report records evidence without overwriting concurrent WS2/WS3/WS4 progress.
- No changes to Artemis/Hyper-V controller, Sofia VM, Hephaestus VM, real host services, database migration, hardware usage, live model selection or canonical writer authority.
- Task counts are unchanged until each exact original CA requirement is traced end-to-end, tested and appropriately accepted.
- Next concrete gate: exact installed wheel and release provenance, run the repaired Windows matrix, verify deterministic first-install tests, then isolate remaining true package regressions. Never solve CI by weakening missing-state security.

**Known security follow-up:** Command-line `--approved-by Sparks` is still a caller-provided name, not independently authenticated human authorization. A full promotion-authorization audit must trace `ChatGPTMemoryMigrationService.promote_batch` and the SAFE owner-proof gate before CA-specific memory import authorization can be considered complete. No new authorization claim is made here.
