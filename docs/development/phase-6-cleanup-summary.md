# Phase 6 cleanup summary

Completed memory, knowledge, state, self_model, identity, and the adjacent data assets. All work is on work; folder checkpoints are pushed. Stop after this phase as requested. Phases 7–10 and the full-cleanup merge to main remain pending.

The table lists every original file in these folders. KEEP decisions follow actual ownership/caller evidence; retained bounded inspection APIs are described candidly in the individual reports. Folder reports include symbol/import inventories, dependency repairs, remaining contracts and test results.

| File | Decision | Production usage / ownership evidence |
|---|---|---|
| `memory/__init__.py` | KEEP | Export supported import values and parser. |
| `memory/chatgpt_export.py` | KEEP | Import CLI parses full exports, visible branches, attachments and exclusions. |
| `memory/chatgpt_export_store.py` | KEEP | Import CLI persists history; runtime retrieves private scoped evidence. Delete zero-caller messages_for_conversation. |
| `memory/chatgpt_import.py` | KEEP | Import CLI parses text/JSON memory dumps. |
| `memory/chatgpt_import_store.py` | KEEP | Exact imported evidence supports migration and integrity checks. Delete zero-caller has_batch. |
| `memory/chatgpt_migration.py` | KEEP | Import CLI proposes deterministic reviewed candidates and explicitly promotes them. |
| `memory/cognition_projection.py` | MERGE | Budgeted promoted projection belongs with promoted_retrieval.py. |
| `memory/conversation_originals.py` | MERGE | Durable exact retrieval belongs with source selection in originals.py. |
| `memory/historical.py` | KEEP | Historical evidence values are distinct from reviewed MemoryRecord claims. |
| `memory/import_chatgpt.py` | KEEP | Explicit production operator import entry point. |
| `memory/matrix.py` | KEEP | Default matrix registry invokes MEMORY routing. |
| `memory/model.py` | KEEP | MemoryRecord is the cognition-facing projection value. |
| `memory/promoted_retrieval.py` | KEEP / MERGE | Runtime retrieval owns ranking, scope and budgeted projection together. |
| `memory/promoted_view.py` | DELETE | Test-only view/supersession facade; production retrieves through current durable status. |
| `memory/provenance.py` | KEEP / DELETE | Retain candidate values; delete duplicate prototype MemoryCandidateRegistry. |
| `memory/provenance_store.py` | KEEP | Canonical durable candidate/source/status owner; remove exclusive retired invalidator query. |
| `memory/retrieval_projection.py` | MERGE / RENAME | SourceMessage, projection and source selection now in originals.py with durable retriever. |
| `memory/reviewed_workflow.py` | KEEP | Application review constructs it; proposals require exact session originals. |
| `memory/source_invalidation.py` | DELETE | Test-only bulk revocation bridge without production source-deletion wiring. |
| `memory/store.py` | DELETE | Superseded unreviewed writer/retrieval store; no production remember/recall calls. |
| `memory/system.py` | KEEP / FIX | Reviewed candidate store is required; remove legacy fallback and unused mode flags. |
| `knowledge/__init__.py` | KEEP | Export canonical SQLite stores, lifecycle and active service contracts; retire old exports. |
| `knowledge/access.py` | KEEP | Production service checks this canonical audience-policy table. |
| `knowledge/capability.py` | KEEP | Composition binds authorized ingest/search/document/write capabilities and cognitive tools. |
| `knowledge/ingest.py` | DELETE | Standalone local-file prototype had no production caller; bounded service ingestion supersedes it. |
| `knowledge/lifecycle.py` | KEEP / DELETE | SQLite freshness owner is live; remove competing JSON writer and unused flush. |
| `knowledge/matrix.py` | KEEP | Matrix defaults register KNOW routing. |
| `knowledge/model.py` | KEEP | Validated provenance values used by service, persistence and retrieval. |
| `knowledge/persistence.py` | KEEP / MERGE / DELETE | Retain SQLite durability, merge small index, replace old JSON writer with pure import reader. |
| `knowledge/repository_ingest.py` | DELETE | Standalone repository helper only had its own tests; production service owns bounded ingestion. |
| `knowledge/retrieval.py` | KEEP | Service searches active/trusted facts with provenance. |
| `knowledge/service.py` | KEEP | Production capabilities invoke bounded ingestion, search and document authoring. |
| `knowledge/store.py` | MERGE | Small index becomes KnowledgeStore inside persistence.py; canonical subclass uses it as its cache. |
| `state/__init__.py` | KEEP | Canonical active exports; remove prospective runner/lease exports. |
| `state/atomic_file.py` | KEEP / MERGE | Active authoritative file writes; shared collision-free legacy retirement now lives here. |
| `state/component_schema.py` | KEEP / MERGE | Production startup/backup schema gate; compatibility value moved beside its actual owner. |
| `state/inventory.py` | DELETE | No source/test caller; stale catalog marked retired knowledge/location JSON authoritative. |
| `state/json_repository.py` | KEEP / DELETE | Live scoped relationship/habit repository; remove compare_and_put used only by retired lease. |
| `state/migration_lease.py` | DELETE | Prospective runner was its only production-code consumer; no entry point reached either. |
| `state/migration_runner.py` | DELETE | Only its own tests constructed it; no production bootstrap, CLI or operational invocation. |
| `state/model.py` | KEEP | Validated classes/keys/records used by all active state owners. |
| `state/namespaces.py` | KEEP / DELETE | Live relationship/habit catalog; remove exclusive migration-lease namespace and zero-caller lookup catalog. |
| `state/plane.py` | KEEP | Backend-neutral durable read/write/delete/scoped-list contract with revision checks. |
| `state/schema.py` | MERGE / DELETE | Preserve SchemaCompatibility in component_schema.py; delete unused generic migration planning. |
| `state/sqlite_plane.py` | KEEP | Production SQLite implementation, transactions and optimistic conflict handling; backup restore reads its schema revision. |
| `self_model/__init__.py` | KEEP | Exports active typed core/operational contracts. |
| `self_model/model.py` | KEEP | Runtime creates core state from verified identity/constitution; cognition projects its identity, self-concept, foundational values and relationships. All validators/factory fields serve these live values. |
| `self_model/operational.py` | KEEP | Runtime creates current operational/continuity/workspace projection for cognitive context. |
| `identity/__init__.py` | KEEP | Canonical identity/store/bootstrap-mode exports. |
| `identity/identity.json` | KEEP | Storage layout explicitly provisions this protected source seed. Its existing UUID is preserved. |
| `identity/model.py` | KEEP | Validated SofiaIdentity/IdentityBootstrapMode serve persistence, runtime and distribution. |
| `identity/store.py` | KEEP | Runtime canonical persistence; first-bootstrap creation/legacy upgrade and require-existing recovery are live contracts. |
| `data/avatar.json` | MOVE | RuntimeStorageLayout.provision seeds configured embodiment design from this asset; EmbodimentStore and runtime/test fixtures load it. Move unchanged to embodiment/avatar.json, beside its design owner. |
| `data/identity.json` | DELETE | No source/test provisioning or import path reads this duplicate UUID. Canonical protected provisioning uses identity/identity.json, which remains unchanged. |

Reports: [memory](memory-cleanup-report.md), [knowledge](knowledge-cleanup-report.md), [state](state-cleanup-report.md), [self_model](self_model-cleanup-report.md), [identity](identity-cleanup-report.md), [data](data-cleanup-report.md).

Final verification: **3470 passed, 8 failed, 2 skipped** (113.04s). Five failures require unavailable Ollama; three existing platform-assumption failures remain in filesystem/config/UI. Compile and dependency checks passed; no new failure remains.

Folder gates: memory 206 passed; knowledge 171 passed; state 276 passed; self_model 162 passed; identity 86 passed; data/asset dependencies 504 passed.

Checkpoints: memory `f742d71d`, knowledge `e2c1b937`, state `d6bcecb5`, self_model `619b3eb1`, identity `f8432e7c`. The asset/summary checkpoint is returned by `git log -1 --format=%H -- docs/development/data-cleanup-report.md`.

No merge to main was performed. Stop after Phase 6 as requested.
