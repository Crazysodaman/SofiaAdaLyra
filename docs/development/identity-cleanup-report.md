# Phase 6: identity cleanup

## What was there / what it does

Four files own identity values, bootstrap/recovery persistence, package exports and the protected source identity seed. Original Python symbols/imports/reference candidates follow below; the JSON asset is inventoried explicitly in the table.

Production chain: RuntimeStorageLayout.provision seeds protected identity from identity/identity.json -> composition constructs IdentityStore with configured path/bootstrap mode -> runtime loads -> verified core/cognitive state. Backup restore verifies protected identity. Distributed services consume the resulting instance identity; they do not mint independent Sofía identities.

## File decisions

| File | Decision | Evidence |
|---|---|---|
| `__init__.py` | KEEP | Canonical identity/store/bootstrap-mode exports. |
| `identity.json` | KEEP | Storage layout explicitly provisions this protected source seed. Its existing UUID is preserved. |
| `model.py` | KEEP | Validated SofiaIdentity/IdentityBootstrapMode serve persistence, runtime and distribution. |
| `store.py` | KEEP | Runtime canonical persistence; first-bootstrap creation/legacy upgrade and require-existing recovery are live contracts. |

## What was wrong / merged / deleted / renamed or moved / fixed

No source change inside identity was justified. Store helpers all serve load/save, model validation guards canonical values, and exports remain active. No merge, deletion, move or rename is needed. Trace found a separate data/identity.json with a different UUID and no provisioning/import reader; handle that duplicate in the adjacent data asset checkpoint rather than modifying the canonical identity seed.

## What remains

IdentityStore is the canonical identity owner. The protected provisioned identity is independent from process/host/model identity. FIRST_BOOTSTRAP and REQUIRE_EXISTING are different required lifecycle modes, not an obsolete compatibility layer; existing recovery/legacy-upgrade tests remain. Save is used internally by actual bootstrap/upgrade. No replacement UUID is minted by cleanup.

## Tests / checkpoint

Compile and diff checks passed. Identity, durable/distributed identity, core/cognitive self-state and composition gate: **86 passed**. Source/tests unchanged from preceding full-suite snapshot: **3469 passed, 8 failed, 2 skipped**; five require unavailable Ollama and three are existing platform assumptions.

Checkpoint: `git log -1 --format=%H -- docs/development/identity-cleanup-report.md` identifies the containing commit.

## Original inventory


## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/identity/__init__.py`

Production/test importers: none in direct absolute imports.

Imports:

- `from sofia.identity.model import IdentityBootstrapMode, SofiaIdentity`
- `from sofia.identity.store import IdentityStore, IdentityStoreError`

Definitions:


Module declarations: `__all__ = ['IdentityBootstrapMode', 'IdentityStore', 'IdentityStoreError', 'SofiaIdentity']`.

- Non-Python asset: `src/sofia/identity/identity.json`

### `src/sofia/identity/model.py`

Production/test importers: `src/sofia/cognition/context.py`, `src/sofia/config/layout.py`, `src/sofia/config/model.py`, `src/sofia/identity/__init__.py`, `src/sofia/identity/store.py`, `src/sofia/ops/backup.py`, `src/sofia/runtime/runtime.py`, `src/sofia/self_model/model.py`, `test/test_cognitive_assembler.py`, `test/test_cognitive_benchmark_contract.py`, `test/test_cognitive_context.py`, `test/test_cognitive_context_assembler.py`, `test/test_cognitive_self_state.py`, `test/test_cognitive_self_state_assembler_contract.py`, `test/test_conversation_workspace_projection.py`, `test/test_conversational_context_projection.py`, `test/test_embodiment_semantic_contract.py`, `test/test_identity.py`, `test/test_production_storage_boundary.py`, `test/test_self_model.py`.

Imports:

- `from dataclasses import dataclass, field`
- `from enum import Enum`
- `from uuid import UUID, uuid4`

Definitions:

- `IdentityBootstrapMode` (line 6): `src/sofia/config/layout.py:24,84,92,94`; `src/sofia/config/model.py:281,313`; `src/sofia/identity/store.py:26,28,66,101`; `src/sofia/ops/backup.py:431`; `test/test_production_storage_boundary.py:105,133`.
  Data declarations: `FIRST_BOOTSTRAP = 'first_bootstrap'`; `REQUIRE_EXISTING = 'require_existing'`.
- `SofiaIdentity` (line 12): `src/sofia/cognition/context.py:44,80`; `src/sofia/identity/store.py:33,34,64,71,108,117`; `src/sofia/runtime/runtime.py:219,263`; `src/sofia/self_model/model.py:92,100,161,171`; `test/test_cognitive_assembler.py:31,32`; `test/test_cognitive_benchmark_contract.py:25`; `test/test_cognitive_context.py:91,92`; `test/test_cognitive_context_assembler.py:138,539,571,622,662`; `test/test_cognitive_self_state.py:22`; `test/test_cognitive_self_state_assembler_contract.py:36`; `test/test_conversation_workspace_projection.py:44`; `test/test_conversational_context_projection.py:19`; `test/test_embodiment_semantic_contract.py:23,24`; `test/test_identity.py:12,13`; `test/test_self_model.py:14,15`.
  Data declarations: `name: str`; `instance_id: UUID = field(default_factory=uuid4)`.
- `SofiaIdentity.__post_init__` (line 28): no external lexical candidates.

### `src/sofia/identity/store.py`

Production/test importers: `src/sofia/composition/root.py`, `src/sofia/evolve/executor.py`, `src/sofia/identity/__init__.py`, `src/sofia/ops/backup.py`, `src/sofia/runtime/runtime.py`, `src/sofia/verify/interaction/ab_probe.py`, `src/sofia/verify/interaction/architecture_compare.py`, `src/sofia/verify/interaction/boundary_counterfactual_probe.py`, `src/sofia/verify/interaction/decision_expression_probe.py`, `src/sofia/verify/interaction/focused_probe.py`, `src/sofia/verify/interaction/route_boundary_probe.py`, `test/test_identity.py`, `test/test_interaction_ab_probe.py`, `test/test_interaction_decision_expression.py`, `test/test_interaction_focused_probe.py`.

Imports:

- `import json`
- `from pathlib import Path`
- `from uuid import UUID, uuid4`
- `from sofia.identity.model import IdentityBootstrapMode, SofiaIdentity`
- `from sofia.state.atomic_file import atomic_write_text`

Definitions:

- `IdentityStoreError` (line 9): `test/test_identity.py:146,162,178,194,210,248,264`.
- `IdentityStore` (line 13): `src/sofia/composition/root.py:138`; `src/sofia/evolve/executor.py:227`; `src/sofia/ops/backup.py:429`; `src/sofia/runtime/runtime.py:100`; `src/sofia/verify/interaction/route_boundary_probe.py:98`; `src/sofia/verify/interaction/focused_probe.py:102`; `src/sofia/verify/interaction/architecture_compare.py:98`; `src/sofia/verify/interaction/decision_expression_probe.py:68`; `src/sofia/verify/interaction/ab_probe.py:102`; `src/sofia/verify/interaction/boundary_counterfactual_probe.py:93`; `test/test_identity.py:56,67,84,96,109,127,144,160,176,192,208,224,246,262`; `test/test_interaction_ab_probe.py:28`; `test/test_interaction_decision_expression.py:32`; `test/test_interaction_focused_probe.py:25`.
- `IdentityStore.__init__` (line 22): `src/sofia/application/emotional_conversation.py:97`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:60`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `IdentityStore.save` (line 33): `src/sofia/application/bootstrap.py:912`; `src/sofia/application/conversation_service.py:510,656`; `src/sofia/avatar/presentation_runtime.py:101,156,202`; `src/sofia/avatar/presentation_store.py:110,132`; `src/sofia/config/user_settings.py:413`; `src/sofia/discord/live.py:109`; `src/sofia/environment/settings_cli.py:83,139`; `src/sofia/interaction/chat.py:468,504`; `src/sofia/interaction/live_offer_service.py:117`; `src/sofia/interaction/question_clarification_service.py:48`; `src/sofia/machine/capability.py:111`; `src/sofia/machine/persistence.py:118`; `src/sofia/memory/import_chatgpt.py:88,116`; `src/sofia/ui/control_center.py:192`; `src/sofia/ui/settings_window.py:845,846,881`; `src/sofia/ui/text.py:120`; `src/sofia/ui/tray_agent.py:425`; `src/sofia/verify/interaction/disposable_live_offer_probe.py:145`; `test/test_avatar_clothing_action.py:55`; `test/test_avatar_presentation_routine.py:36`; `test/test_avatar_presentation_runtime.py:146`; `test/test_avatar_presentation_store.py:63,73,97,153,188`; `test/test_chatgpt_export_import.py:196,197`; `test/test_chatgpt_memory_import.py:45,95,96`; `test/test_conversation.py:30,67,68,108,109,152,184,198,229`; `test/test_discord_provisioning.py:108,144,178,194,217`; `test/test_embodiment.py:130,143`; `test/test_environment_factory.py:217`; `test/test_environment_hot_reload.py:47,98`; `test/test_identity.py:60,73,115,129`; `test/test_interaction_live_stop_repetition.py:48`; `test/test_machine_inventory_persistence.py:296,325,339,406`; `test/test_machine_location_inventory.py:89`; `test/test_machine_regression.py:292,297`; `test/test_memory_conversation_originals.py:22,29,30,45,46,61,62`; `test/test_memory_reviewed_workflow.py:16`; `test/test_memory_runtime_wiring.py:350,391,429`; `test/test_personality_store.py:34,64,81,102,138`; `test/test_production_dual_cognition.py:19`; `test/test_runtime_user_settings.py:55`; `test/test_runtime_user_settings_defaults.py:57,97,114,146,179,204,228`; `test/test_ui_control_center.py:46,58`; `test/test_ui_drafts.py:14,37,42,47,73,79,112,131`.
- `IdentityStore.load` (line 64): `src/sofia/application/bootstrap.py:120,391`; `src/sofia/avatar/presentation_runtime.py:149,157,187`; `src/sofia/config/defaults.py:315`; `src/sofia/discord/live.py:103`; `src/sofia/discord/provisioning.py:131`; `src/sofia/distributed/agent_tools.py:90`; `src/sofia/environment/factory.py:43`; `src/sofia/environment/settings_cli.py:68,130,133`; `src/sofia/evolve/executor.py:227,231`; `src/sofia/machine/capability.py:53`; `src/sofia/machine/location_cli.py:42`; `src/sofia/machine/persistence.py:116,119`; `src/sofia/ops/backup.py:418,429`; `src/sofia/runtime/runtime.py:517,523,524,525`; `src/sofia/ui/control_center.py:184`; `src/sofia/ui/service_control.py:152`; `src/sofia/ui/settings_window.py:111`; `src/sofia/ui/text.py:114`; `src/sofia/ui/tray_agent.py:172,202,422,485`; `src/sofia/verify/interaction/route_boundary_probe.py:96,98,99,100`; `src/sofia/verify/interaction/focused_probe.py:100,102,103,104`; `src/sofia/verify/interaction/architecture_compare.py:96,98,99,100`; `src/sofia/verify/interaction/decision_expression_probe.py:66,68,69,70`; `src/sofia/verify/interaction/ab_probe.py:100,102,103,104`; `src/sofia/verify/interaction/boundary_counterfactual_probe.py:91,93,94,95`; `test/test_avatar_clothing_action.py:60`; `test/test_avatar_presentation_runtime.py:18,60`; `test/test_avatar_presentation_store.py:64,117,143`; `test/test_avatar_self_fact_query.py:22`; `test/test_canonical_embodiment.py:72`; `test/test_constitution_integrity.py:32,105,106,107,117,118`; `test/test_constitution_store.py:17`; `test/test_embodiment.py:132,157,176`; `test/test_environment_behavior_matrix.py:213`; `test/test_environment_hot_reload.py:21`; `test/test_environment_settings_cli.py:21,33,47`; `test/test_evolve_executor.py:163`; `test/test_identity.py:75,86,98,99,117,147,163,179,195,211,226,231,249,265`; `test/test_interaction_ab_probe.py:28,29,30,31,54`; `test/test_interaction_avatar_world.py:25`; `test/test_interaction_behavior_matrix.py:30`; `test/test_interaction_chat_projection.py:46,142`; `test/test_interaction_consent_followup.py:64,103,141`; `test/test_interaction_contextual_all_regions.py:19`; `test/test_interaction_decision_expression.py:32,33,34,35,41`; `test/test_interaction_focused_probe.py:25,26,27,28`; `test/test_interaction_i5_i7_batch.py:22,154`; `test/test_interaction_i7_compound_regression.py:16`; `test/test_interaction_lab.py:17`; `test/test_interaction_live_boundaries.py:38`; `test/test_interaction_live_claims.py:73`; `test/test_interaction_live_discussion.py:26,44`; `test/test_interaction_live_phrase_coverage.py:18`; `test/test_interaction_live_stop_repetition.py:35,123`; `test/test_interaction_region_cue_collision.py:13`; `test/test_interaction_registry.py:19`; `test/test_interaction_shared_engine.py:17`; `test/test_interaction_v2_cross_modal.py:16,27`; `test/test_interaction_v2_live_grammar.py:19`; `test/test_interaction_world_observation.py:92`; `test/test_interaction_world_text.py:92,114`; `test/test_machine_inventory_persistence.py:298,340,355,410`; `test/test_machine_regression.py:294,299`; `test/test_ollama_unload.py:29`; `test/test_personality_pipeline.py:28,40`; `test/test_personality_store.py:66,83,104,128,149,165,181,200,220`; `test/test_runtime_user_settings.py:57,200,259,299`; `test/test_ui_control_center.py:30,47`; `test/test_ui_desktop_storage_authority.py:82`; `test/test_ui_drafts.py:23,53,57,61,86,100,119,140`.
- `IdentityStore._load_name` (line 123): no external lexical candidates.
- `IdentityStore._load_instance_id` (line 144): no external lexical candidates.
