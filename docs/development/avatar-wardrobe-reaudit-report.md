# Avatar wardrobe re-audit after main update

Base: `db50ec27d1615dcfb70fd2ccc167b8583abd03a7` (Phase 6 merge with external wardrobe update).

The updated folder had 18 Python files and 7,036 lines. It owns garment design metadata,
headless presentation authority, durable settled snapshots, contextual proposals and grounded
self-fact responses. The new wardrobe profiles and creator requests are preserved.

| Original file | Decision | Responsibility and production reachability |
| --- | --- | --- |
| `__init__.py` | KEEP | Inert package marker; no re-export or initialization side effects. |
| `authoring.py` | KEEP, remove unused cache | Updated main deliberately adds structured creator APIs; preserve explicit programmatic authoring, remove unused type map and correct false frontend-wiring comment. |
| `clothing_action.py` | KEEP, remove dead field | Application bootstrap wires `handle` into conversation; mutations go through the presentation store. |
| `clothing_intent.py` | KEEP | Parser, typed intents and target normalization used by the clothing action service. |
| `matrix.py` | KEEP | Matrix defaults register the AVATAR evaluator; conversation routing invokes it. |
| `presentation.py` | KEEP | Sole revisioned presentation authority; runtime, routine, store and clothing service consume it. |
| `presentation_routine.py` | KEEP | Application startup and pre-response/background hooks evaluate trusted daily context. |
| `presentation_runtime.py` | KEEP | Application startup loads/bootstrap state and attaches the bundle to runtime. Includes actively invoked state migrations. |
| `presentation_store.py` | KEEP | SQLite persistence and durable-or-rollback mutations used by runtime bootstrap, clothing actions and routines. |
| `private_grant.py` | KEEP | Runtime and clothing actions resolve trusted host/session/stop evidence. |
| `self_fact_query.py` | KEEP | Runtime responds to grounded outfit/body/appearance queries before LLM inference. |
| `wardrobe.py` | KEEP | Canonical slot/layer metadata, normalization, selection validation and future renderer display gate. |
| `wardrobe_autonomy.py` | KEEP | Clothing service evaluates contextual choice; bootstrap supplies the context provider. |
| `wardrobe_catalog.py` | SPLIT | Keep authored inventory/profiles and starter assembly; move validated prebuild containers, preferences and manifest handoff to `wardrobe_prebuild.py`. |
| `wardrobe_matrix.py` | KEEP | Runtime bundle derives slot/layer cells from the catalog and current item IDs. |
| `wardrobe_planner.py` | KEEP | Application routine and clothing autonomy propose context-compatible outfits without changing state. |
| `fit.py` | KEEP | Production catalog and prebuild validation use canonical fit anchors; retired body snapshot contract stays retired. |
| `wardrobe_design.py` | SPLIT | Keep structured profiles and design validation; move garment type definitions/catalog to `wardrobe_types.py`. |

New files: `wardrobe_types.py` owns type definitions, creator constraints and the immutable type
catalog; `wardrobe_prebuild.py` owns validated prebuild metadata, source-backed preferences,
serialization and default IDs. All moved definition bodies have identical ASTs. No compatibility
shim or duplicate owner was added. Source/test imports now target their canonical modules.
The static reviewed item profiles remain with their authored inventory rather than being scattered.
The planner remains one cohesive proposal/scoring subsystem; authority, persistence and policy
remain separate.

Production trace: application bootstrap → presentation runtime → starter catalog → prebuild
validation → wardrobe authority/store. Application context/routine and clothing action handlers
→ planner/autonomy → authority transition → durable-or-rollback store. Runtime self-fact answers
and wardrobe matrices derive audience-safe projections from that authority. Default matrix registry
registers the AVATAR evaluator. The updated material, environment, context and comfort profiles
flow through catalog designs to planner suitability scoring; their manifest is an offline handoff.

`WardrobeStudio` has no current frontend caller. It is retained as the explicitly enhanced public
creator API from the external update, not because tests make it production code. It requires an
explicit authority for registration and optionally the canonical store for durability. Remove its
unused `_garment_types` cache and the misleading production-wiring comment. The old
`BodyAuthoringContract` remains retired. No other unexplained production orphan was identified;
Python hooks/local callbacks and the previously documented bounded/offline APIs remain.

State: PresentationAuthority is the only live presentation owner; PresentationStore persists it
in canonical SQLite. Profiles, blueprint manifests and planner proposals are metadata/projections,
not another mutable current-state model. Embodiment remains the body source. Supported legacy
snapshot migrations remain reachable through production bootstrap.

Validation: compile source/tests passed; avatar/environment/application gate **268 passed**.
Full suite **3,475 passed, 8 failed, 2 skipped** (63.62s), identical to merged baseline: five
unavailable Ollama checks and three diagnosed Windows/path assumptions assigned to UI,
filesystem and config phases. No newly skipped tests. Diff whitespace check passed.

Checkpoint: `git log -1 --format=%H -- docs/development/avatar-wardrobe-reaudit-report.md`.
The earlier avatar report is historical; this report supersedes its creator/catalog decisions
following the external wardrobe update.

## Original file, definition and import inventory

### `src/sofia/avatar/__init__.py`

6 lines.

Definitions:

Imports:

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):


### `src/sofia/avatar/authoring.py`

196 lines.

Definitions:
- `GarmentDesignRequest` (line 27)
- `WardrobeStudio` (line 56)
- `__init__` (line 59)
- `compose` (line 84)
- `design_piece` (line 147)
- `mutate` (line 127)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass, field`
- `from .presentation import PresentationAuthority`
- `from .presentation_store import PresentationStore`
- `from .wardrobe import Garment, WardrobeError`
- `from .wardrobe_design import ComfortProfile, ContextProfile, EnvironmentProfile, GarmentDesign, GraphicDesign, MaterialProperties, all_garment_types, validate_design`
- `from .wardrobe_planner import Activity, OutfitPlan, Season`
- `from .wardrobe_catalog import WardrobePrebuild`
- `from .wardrobe_catalog import GarmentBlueprint`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `src/sofia/composition/root.py`
- `src/sofia/verify/dual_cognition.py`
- `test/test_avatar_authoring.py`
- `test/test_avatar_wardrobe_creator.py`
- `test/test_avatar_wardrobe_environment_profiles.py`
- `test/test_capability_composition_scope.py`
- `test/test_composition.py`
- `test/test_default_runtime_provider_boundary.py`
- `test/test_embodiment_prompt_regression.py`
- `test/test_embodiment_runtime_projection.py`
- `test/test_memory_runtime_wiring.py`
- `test/test_ollama_integration.py`
- `test/test_runtime_action_integration.py`
- `test/test_tools_completion_acceptance.py`

### `src/sofia/avatar/clothing_action.py`

669 lines.

Definitions:
- `ClothingActionService` (line 43)
- `__init__` (line 46)
- `handle` (line 105)
- `_handle_locked` (line 122)
- `_hypothetical_reply` (line 195)
- `_decline_private` (line 210)
- `_private_grant` (line 219)
- `_commit_nude` (line 228)
- `_wear` (line 263)
- `_remove` (line 298)
- `_add` (line 330)
- `_add_blueprint` (line 364)
- `_swap` (line 387)
- `_resolve_outfit` (line 452)
- `_resolve_blueprint` (line 489)
- `_commit_candidate` (line 522)
- `mutate` (line 236)
- `mutate` (line 627)

Imports:
- `from __future__ import annotations`
- `from collections.abc import Callable`
- `from dataclasses import replace`
- `import re`
- `from threading import RLock`
- `from sofia.safe.operator_stop import OperatorStopStore`
- `from sofia.social.model import PrincipalContext`
- `from .clothing_intent import ClothingActionIntent, ClothingActionKind, ClothingActionParser, _clean_target, _normalize`
- `from .presentation import PrivatePresentationGrant, PresentationState`
- `from .private_grant import PrivatePresentationGrantResolver`
- `from .presentation_runtime import PresentationRuntimeBundle`
- `from .wardrobe import WardrobeConflict, WardrobeError, normalize_slots`
- `from .wardrobe_autonomy import WardrobeAutonomyContext, WardrobeAutonomyPolicy`
- `from .wardrobe_planner import OutfitPlan, OutfitPlanner`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `test/test_avatar_clothing_action.py`
- `test/test_idle_reflection_application.py`
- `test/test_internal_workspace_awareness.py`

### `src/sofia/avatar/clothing_intent.py`

173 lines.

Definitions:
- `_normalize` (line 9)
- `_clean_target` (line 15)
- `ClothingActionKind` (line 22)
- `ClothingActionIntent` (line 31)
- `ClothingActionParser` (line 47)
- `__post_init__` (line 36)
- `parse` (line 99)
- `is_followup` (line 126)
- `_parse_direct` (line 131)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass, replace`
- `from enum import Enum`
- `import re`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/wardrobe_autonomy.py`

### `src/sofia/avatar/fit.py`

141 lines.

Definitions:
- `BodyContractError` (line 14)
- `BodyRegion` (line 18)
- `AuthoringLandmark` (line 53)
- `FitAnchor` (line 98)
- `__post_init__` (line 104)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from enum import Enum`
- `import re`

Top-level constants:
- `_ID`
- `REQUIRED_AUTHORING_LANDMARKS`
- `DEFAULT_FIT_ANCHORS`

Candidate reference files (lexical evidence, not production reachability):
- `test/test_avatar_fit.py`

### `src/sofia/avatar/matrix.py`

39 lines.

Definitions:
- `AvatarMatrixEvaluator` (line 19)
- `evaluate` (line 22)

Imports:
- `import re`
- `from sofia.cognition.matrix.model import DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance`

Top-level constants:
- `_AVATAR`

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/act/__init__.py`
- `src/sofia/act/delivery.py`
- `src/sofia/act/outreach.py`
- `src/sofia/act/system_notice.py`
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_matrix.py`
- `src/sofia/application/conversation_service.py`
- `src/sofia/authority/matrix.py`
- `src/sofia/authorization/evaluator.py`
- `src/sofia/avatar/presentation_routine.py`
- `src/sofia/body/matrix.py`
- `src/sofia/continuity/matrix.py`
- `src/sofia/dev/matrix.py`
- `src/sofia/distributed/inference.py`
- `src/sofia/emotion/matrix.py`
- `src/sofia/environment/matrix.py`
- `src/sofia/external/adapter.py`
- `src/sofia/habits/matrix.py`
- `src/sofia/integrate/matrix.py`
- `src/sofia/interaction/matrix.py`
- `src/sofia/knowledge/matrix.py`
- `src/sofia/machine/matrix.py`
- `src/sofia/memory/matrix.py`
- `src/sofia/ops/failure_matrix.py`
- `src/sofia/ops/matrix.py`
- `src/sofia/rel/matrix.py`
- `src/sofia/social/matrix.py`
- `src/sofia/verify/compatibility_matrix.py`
- `src/sofia/voice/matrix.py`
- `src/sofia/voice/runtime_matrix.py`
- `src/sofia/cognition/matrix/coordinator.py`
- `src/sofia/cognition/matrix/defaults.py`
- `test/test_act_outreach.py`
- `test/test_authority.py`
- `test/test_authorization_evaluator.py`
- `test/test_avatar_presentation_routine.py`
- `test/test_capability_composition_scope.py`
- `test/test_cognition_matrix.py`
- `test/test_conversation_service.py`
- `test/test_filesystem_orchestrator.py`
- `test/test_ops_failure_recovery_matrix.py`
- `test/test_rel_habit_matrix.py`
- `test/test_release_compatibility_matrix.py`
- `test/test_semantic_domain_matrix.py`
- `test/test_voice_matrix.py`
- `test/test_voice_runtime_matrix.py`

### `src/sofia/avatar/presentation.py`

676 lines.

Definitions:
- `PresentationError` (line 28)
- `PresentationConflict` (line 32)
- `PresentationDenied` (line 36)
- `AudienceScope` (line 40)
- `AttireMode` (line 45)
- `_id` (line 50)
- `_text` (line 56)
- `_color` (line 64)
- `PrivatePresentationGrant` (line 72)
- `AppearanceState` (line 103)
- `PresentationState` (line 123)
- `PresentationChange` (line 160)
- `PresentationProjection` (line 173)
- `PresentationAuthority` (line 187)
- `__post_init__` (line 81)
- `require` (line 91)
- `__post_init__` (line 109)
- `__post_init__` (line 132)
- `__init__` (line 192)
- `current` (line 247)
- `last_daily` (line 251)
- `pending` (line 255)
- `available_outfit_ids` (line 259)
- `register_outfit` (line 262)
- `propose_outfit` (line 293)
- `propose_nude` (line 330)
- `propose_appearance` (line 356)
- `commit_text` (line 384)
- `cancel` (line 419)
- `projection` (line 426)
- `snapshot` (line 466)
- `restore` (line 488)
- `restore_snapshot` (line 571)
- `_begin` (line 598)
- `_require_pending` (line 607)
- `_validate_clothed_state` (line 613)
- `_state_dict` (line 629)
- `_appearance_from_dict` (line 646)
- `_state_from_dict` (line 659)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from enum import Enum`
- `from typing import Any`
- `import re`
- `from .wardrobe import Wardrobe`

Top-level constants:
- `_ID`
- `_HEX`

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/action/system.py`
- `src/sofia/application/act_service.py`
- `src/sofia/application/background_runtime.py`
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_matrix.py`
- `src/sofia/application/conversation_service.py`
- `src/sofia/application/emotional_conversation.py`
- `src/sofia/application/idle_reflection.py`
- `src/sofia/authorization/evaluator.py`
- `src/sofia/avatar/authoring.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/matrix.py`
- `src/sofia/avatar/presentation_routine.py`
- `src/sofia/avatar/presentation_runtime.py`
- `src/sofia/avatar/presentation_store.py`
- `src/sofia/avatar/private_grant.py`
- `src/sofia/avatar/self_fact_query.py`
- `src/sofia/avatar/wardrobe_autonomy.py`
- `src/sofia/avatar/wardrobe_catalog.py`
- `src/sofia/avatar/wardrobe_matrix.py`
- `src/sofia/avatar/wardrobe_planner.py`
- `src/sofia/capability/catalog.py`
- `src/sofia/clean/__main__.py`
- `src/sofia/clean/recovery.py`
- `src/sofia/codebase/analyzers.py`
- `src/sofia/cognition/assembler.py`
- `src/sofia/cognition/context.py`
- `src/sofia/cognition/context_evidence.py`
- `src/sofia/cognition/conversation_assembler.py`
- `src/sofia/cognition/grounding.py`
- `src/sofia/cognition/model.py`
- `src/sofia/cognition/quality_repair.py`
- `src/sofia/cognition/repetition_guard.py`
- `src/sofia/cognition/self_state.py`
- `src/sofia/cognition/system.py`
- `src/sofia/cognition/tools.py`
- `src/sofia/composition/authorization.py`
- `src/sofia/composition/root.py`
- `src/sofia/config/defaults.py`
- `src/sofia/config/user_settings.py`
- `src/sofia/continuity/model.py`
- `src/sofia/dev/capability.py`
- `src/sofia/dev/git_workspace.py`
- `src/sofia/dev/release_store.py`
- `src/sofia/dev/workflow.py`
- `src/sofia/dev/workspace.py`
- `src/sofia/discord/binding.py`
- `src/sofia/discord/discordpy.py`
- `src/sofia/discord/operator.py`
- `src/sofia/discord/outbound.py`
- `src/sofia/discord/provisioning.py`
- `src/sofia/distributed/capability.py`
- `src/sofia/distributed/durable.py`
- `src/sofia/distributed/inference_client.py`
- `src/sofia/distributed/knowledge.py`
- `src/sofia/distributed/reachability.py`
- `src/sofia/distributed/state_paths.py`
- `src/sofia/embodiment/model.py`
- `src/sofia/embodiment/store.py`
- `src/sofia/emotion/catalog.py`
- `src/sofia/emotion/clarification.py`
- `src/sofia/emotion/journal.py`
- `src/sofia/emotion/matrix.py`
- `src/sofia/emotion/projection.py`
- `src/sofia/environment/config.py`
- `src/sofia/environment/factory.py`
- `src/sofia/environment/home_assistant.py`
- `src/sofia/environment/matrix.py`
- `src/sofia/environment/model.py`
- `src/sofia/environment/nws.py`
- `src/sofia/environment/prompt.py`
- `src/sofia/environment/provider.py`
- `src/sofia/environment/query.py`
- `src/sofia/environment/query_forms.py`
- `src/sofia/environment/query_sources.py`
- `src/sofia/environment/service.py`
- `src/sofia/environment/settings_cli.py`
- `src/sofia/evolve/executor.py`
- `src/sofia/evolve/revision.py`
- `src/sofia/evolve/state_plane_adapter.py`
- `src/sofia/external/knowledge.py`
- `src/sofia/filesystem/change_capability.py`
- `src/sofia/filesystem/change_filter.py`
- `src/sofia/filesystem/changes.py`
- `src/sofia/filesystem/observation.py`
- `src/sofia/habits/continuity.py`
- `src/sofia/habits/engine.py`
- `src/sofia/habits/expectations.py`
- `src/sofia/habits/model.py`
- `src/sofia/habits/pattern_store.py`
- `src/sofia/integrate/governed.py`
- `src/sofia/integrate/policy.py`
- `src/sofia/integrations/capabilities.py`
- `src/sofia/integrations/discord.py`
- `src/sofia/interaction/atomic_offer_release.py`
- `src/sofia/interaction/body_discussion.py`
- `src/sofia/interaction/chat.py`
- `src/sofia/interaction/conversation_offer_context.py`
- `src/sofia/interaction/core.py`
- `src/sofia/interaction/decision_expression.py`
- `src/sofia/interaction/decision_reason_audit.py`
- `src/sofia/interaction/expanded_service.py`
- `src/sofia/interaction/goal_journal.py`
- `src/sofia/interaction/live_guard.py`
- `src/sofia/interaction/live_offer_service.py`
- `src/sofia/interaction/preference_context.py`
- `src/sofia/interaction/world.py`
- `src/sofia/interaction/world_observation.py`
- `src/sofia/interaction/world_setup.py`
- `src/sofia/interaction/world_text.py`
- `src/sofia/knowledge/lifecycle.py`
- `src/sofia/machine/capability.py`
- `src/sofia/machine/comparison.py`
- `src/sofia/machine/discovery.py`
- `src/sofia/machine/hardware.py`
- `src/sofia/machine/inventory.py`
- `src/sofia/machine/inventory_codec.py`
- `src/sofia/machine/persistence.py`
- `src/sofia/memory/chatgpt_export.py`
- `src/sofia/memory/reviewed_workflow.py`
- `src/sofia/memory/system.py`
- `src/sofia/operational/model.py`
- `src/sofia/operational/status_queries.py`
- `src/sofia/ops/activity.py`
- `src/sofia/ops/agent_discovery.py`
- `src/sofia/ops/backup.py`
- `src/sofia/ops/backup_cli.py`
- `src/sofia/ops/bootstrap.py`
- `src/sofia/ops/capability.py`
- `src/sofia/ops/discovery.py`
- `src/sofia/ops/failover.py`
- `src/sofia/ops/failure_matrix.py`
- `src/sofia/ops/lease.py`
- `src/sofia/ops/maintenance.py`
- `src/sofia/ops/matrix.py`
- `src/sofia/ops/orchestrator.py`
- `src/sofia/ops/placement.py`
- `src/sofia/ops/reconcile.py`
- `src/sofia/ops/recovery.py`
- `src/sofia/ops/remote.py`
- `src/sofia/ops/telemetry.py`
- `src/sofia/personality/expression.py`
- `src/sofia/personality/influence.py`
- `src/sofia/personality/observation_bridge.py`
- `src/sofia/personality/reflection.py`
- `src/sofia/personality/thought_agent.py`
- `src/sofia/run/active_release.py`
- `src/sofia/run/heartbeat.py`
- `src/sofia/run/lease.py`
- `src/sofia/run/periodic.py`
- `src/sofia/run/release.py`
- `src/sofia/run/windows_acceptance.py`
- `src/sofia/runtime/clock.py`
- `src/sofia/runtime/evidence.py`
- `src/sofia/runtime/internal_workspace.py`
- `src/sofia/runtime/response.py`
- `src/sofia/runtime/runtime.py`
- `src/sofia/safe/approve_execution.py`
- `src/sofia/safe/dev_approve.py`
- `src/sofia/safe/evolve_approval.py`
- `src/sofia/safe/evolve_approve.py`
- `src/sofia/safe/operator_stop.py`
- `src/sofia/safe/operator_stop_cli.py`
- `src/sofia/self_model/model.py`
- `src/sofia/self_model/operational.py`
- `src/sofia/social/model.py`
- `src/sofia/state/component_schema.py`
- `src/sofia/state/sqlite_plane.py`
- `src/sofia/system/linux.py`
- `src/sofia/ui/delivery.py`
- `src/sofia/ui/desktop.py`
- `src/sofia/ui/desktop_controller.py`
- `src/sofia/ui/quick_tools.py`
- `src/sofia/ui/remote_client.py`
- `src/sofia/ui/remote_transport.py`
- `src/sofia/ui/runtime_authority.py`
- `src/sofia/ui/settings_window.py`
- `src/sofia/ui/theme.py`
- `src/sofia/ui/tray_agent.py`
- `src/sofia/ui/tray_launcher.py`
- `src/sofia/ui/windows_tray.py`
- `src/sofia/ui/workbench.py`
- `src/sofia/verify/reflection_audit.py`
- `src/sofia/verify/semantic_integrity.py`
- `src/sofia/voice/matrix.py`
- `src/sofia/cognition/matrix/classifier.py`
- `src/sofia/cognition/matrix/context_plan.py`
- `src/sofia/cognition/matrix/coordinator.py`
- `src/sofia/cognition/matrix/evidence.py`
- `src/sofia/cognition/matrix/influence.py`
- `src/sofia/cognition/matrix/model.py`
- `src/sofia/cognition/matrix/privacy.py`
- `src/sofia/cognition/matrix/response.py`
- `src/sofia/cognition/matrix/tool_exposure.py`
- `src/sofia/verify/interaction/ab_probe.py`
- `src/sofia/verify/interaction/architecture_compare.py`
- `src/sofia/verify/interaction/avatar_world_probe.py`
- `src/sofia/verify/interaction/boundary_counterfactual_probe.py`
- `src/sofia/verify/interaction/live_behavior_probe.py`
- `src/sofia/verify/interaction/route_boundary_probe.py`
- `test/conftest.py`
- `test/test_application.py`
- `test/test_application_background.py`
- `test/test_avatar_authoring.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_presentation.py`
- `test/test_avatar_presentation_routine.py`
- `test/test_avatar_presentation_runtime.py`
- `test/test_avatar_presentation_store.py`
- `test/test_avatar_private_grant.py`
- `test/test_avatar_runtime_projection.py`
- `test/test_avatar_self_fact_query.py`
- `test/test_avatar_wardrobe_context_projection.py`
- `test/test_avatar_wardrobe_environment_context.py`
- `test/test_capability_composition_scope.py`
- `test/test_clean_package.py`
- `test/test_cognition_matrix.py`
- `test/test_cognitive_activity.py`
- `test/test_cognitive_assembler.py`
- `test/test_cognitive_context_assembler.py`
- `test/test_cognitive_grounding_contract.py`
- `test/test_cognitive_routing.py`
- `test/test_cognitive_self_state_assembler_contract.py`
- `test/test_composition.py`
- `test/test_contextual_influence_matrix.py`
- `test/test_continuity_events.py`
- `test/test_conversation_provider_live_regressions.py`
- `test/test_conversation_service.py`
- `test/test_conversation_workspace_projection.py`
- `test/test_conversational_context_projection.py`
- `test/test_current_emotional_state.py`
- `test/test_discord_operator.py`
- `test/test_discord_recovery.py`
- `test/test_distributed_authorization.py`
- `test/test_distributed_durable.py`
- `test/test_distributed_peer_knowledge.py`
- `test/test_distributed_reachability.py`
- `test/test_embodied_expression_plan.py`
- `test/test_embodiment.py`
- `test/test_embodiment_prompt_regression.py`
- `test/test_emotional_behavior_matrix.py`
- `test/test_emotional_clarifications.py`
- `test/test_emotional_conversation_integration.py`
- `test/test_environment_acceptance.py`
- `test/test_environment_behavior_matrix.py`
- `test/test_environment_prompt.py`
- `test/test_environment_query.py`
- `test/test_environment_runtime_projection.py`
- `test/test_environment_service.py`
- `test/test_evolve_revision.py`
- `test/test_external_integration_verification.py`
- `test/test_external_knowledge.py`
- `test/test_filesystem_changes.py`
- `test/test_filesystem_orchestrator.py`
- `test/test_habit_foundation.py`
- `test/test_idle_reflection_worker.py`
- `test/test_interaction_ab_probe.py`
- `test/test_interaction_avatar_offer_scene_probe.py`
- `test/test_interaction_avatar_world.py`
- `test/test_interaction_chat_projection.py`
- `test/test_interaction_consent_followup.py`
- `test/test_interaction_context_hygiene.py`
- `test/test_interaction_decision_expression.py`
- `test/test_interaction_focused_probe.py`
- `test/test_interaction_goal_journal.py`
- `test/test_interaction_provider_request_path.py`
- `test/test_interaction_world_internal_noise.py`
- `test/test_interaction_world_location.py`
- `test/test_interaction_world_observation.py`
- `test/test_interaction_world_text.py`
- `test/test_internal_workspace_awareness.py`
- `test/test_internal_workspace_string_path_regression.py`
- `test/test_live_behavior_probe_quality.py`
- `test/test_machine_inventory_lifecycle.py`
- `test/test_machine_inventory_persistence.py`
- `test/test_machine_inventory_refresh.py`
- `test/test_machine_regression.py`
- `test/test_memory_promoted_retrieval.py`
- `test/test_memory_runtime_wiring.py`
- `test/test_observation_bridge.py`
- `test/test_observation_bridge_self_noise.py`
- `test/test_ollama_repetition_guard.py`
- `test/test_ops_agent_discovery.py`
- `test/test_ops_backup_cli.py`
- `test/test_ops_backup_restore.py`
- `test/test_ops_waves3_5_acceptance.py`
- `test/test_personality_embodiment_contract.py`
- `test/test_personality_emotional_gestures.py`
- `test/test_reflection_conversation_integration.py`
- `test/test_reflection_journal.py`
- `test/test_rel_habit_matrix.py`
- `test/test_response_quality_hardening.py`
- `test/test_run_lease.py`
- `test/test_runtime.py`
- `test/test_self_model_operational.py`
- `test/test_thought_agent.py`
- `test/test_thought_agent_conversation.py`
- `test/test_thought_agent_live_ollama.py`
- `test/test_thought_urgency_evidence.py`
- `test/test_ui_application.py`
- `test/test_ui_theme.py`
- `test/test_ui_tray_model_roles.py`
- `test/test_ui_workbench.py`
- `test/test_voice_matrix.py`
- `test/test_voice_prosody_matrix.py`

### `src/sofia/avatar/presentation_routine.py`

201 lines.

Definitions:
- `PresentationRoutineResult` (line 29)
- `HeadlessPresentationRoutine` (line 37)
- `__init__` (line 38)
- `evaluate_daypart_fallback` (line 55)
- `evaluate` (line 140)
- `mutate` (line 111)
- `mutate` (line 174)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from .presentation import AttireMode, PresentationAuthority, PresentationState`
- `from .presentation_store import PresentationStore`
- `from .wardrobe_catalog import DAY_DEFAULT_OUTFIT_ID, NIGHT_LOUNGE_OUTFIT_ID`
- `from .wardrobe_planner import Cadence, OutfitPlanner, OutfitProposal, Preference, WardrobeContext, WornEvidence`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/act/__init__.py`
- `src/sofia/act/delivery.py`
- `src/sofia/act/outreach.py`
- `src/sofia/act/system_notice.py`
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_matrix.py`
- `src/sofia/application/conversation_service.py`
- `src/sofia/authority/matrix.py`
- `src/sofia/authorization/evaluator.py`
- `src/sofia/avatar/matrix.py`
- `src/sofia/body/matrix.py`
- `src/sofia/continuity/matrix.py`
- `src/sofia/dev/matrix.py`
- `src/sofia/distributed/inference.py`
- `src/sofia/emotion/matrix.py`
- `src/sofia/environment/matrix.py`
- `src/sofia/external/adapter.py`
- `src/sofia/habits/matrix.py`
- `src/sofia/integrate/matrix.py`
- `src/sofia/interaction/matrix.py`
- `src/sofia/knowledge/matrix.py`
- `src/sofia/machine/matrix.py`
- `src/sofia/memory/matrix.py`
- `src/sofia/ops/failure_matrix.py`
- `src/sofia/ops/matrix.py`
- `src/sofia/rel/matrix.py`
- `src/sofia/social/matrix.py`
- `src/sofia/verify/compatibility_matrix.py`
- `src/sofia/voice/matrix.py`
- `src/sofia/voice/runtime_matrix.py`
- `src/sofia/cognition/matrix/coordinator.py`
- `src/sofia/cognition/matrix/defaults.py`
- `test/test_act_outreach.py`
- `test/test_authority.py`
- `test/test_authorization_evaluator.py`
- `test/test_avatar_presentation_routine.py`
- `test/test_capability_composition_scope.py`
- `test/test_cognition_matrix.py`
- `test/test_conversation_service.py`
- `test/test_filesystem_orchestrator.py`
- `test/test_idle_reflection_application.py`
- `test/test_internal_workspace_awareness.py`
- `test/test_ops_failure_recovery_matrix.py`
- `test/test_rel_habit_matrix.py`
- `test/test_release_compatibility_matrix.py`
- `test/test_semantic_domain_matrix.py`
- `test/test_voice_matrix.py`
- `test/test_voice_runtime_matrix.py`

### `src/sofia/avatar/presentation_runtime.py`

271 lines.

Definitions:
- `PresentationRuntimeBundle` (line 21)
- `_appearance_from_embodiment` (line 39)
- `_authority_from_obsolete_snapshot` (line 51)
- `_migrate_obsolete_wardrobe_snapshot` (line 130)
- `_legacy_presentation_state_path` (line 157)
- `_retired_legacy_path` (line 162)
- `_legacy_snapshot` (line 171)
- `_migrate_legacy_presentation_state` (line 185)
- `load_or_bootstrap_presentation` (line 236)
- `matrix_for` (line 26)
- `current_matrix` (line 34)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `import json`
- `from pathlib import Path`
- `from sofia.embodiment.model import Embodiment`
- `from .presentation import AppearanceState, PresentationAuthority`
- `from .presentation_store import PresentationStore, PresentationStoreError`
- `from .wardrobe_catalog import DAY_DEFAULT_OUTFIT_ID, WardrobePrebuild, build_starter_wardrobe`
- `from .wardrobe_matrix import WardrobeSlotMatrix, build_wardrobe_matrix`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `src/sofia/avatar/clothing_action.py`
- `test/test_application.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_presentation_runtime.py`
- `test/test_idle_reflection_application.py`
- `test/test_internal_workspace_awareness.py`
- `test/test_ui_application.py`

### `src/sofia/avatar/presentation_store.py`

212 lines.

Definitions:
- `PresentationStoreError` (line 19)
- `PresentationStore` (line 23)
- `__init__` (line 35)
- `database_path` (line 49)
- `save` (line 52)
- `persist_mutation` (line 89)
- `load` (line 144)
- `_read_snapshot_json` (line 194)
- `exists` (line 211)

Imports:
- `from __future__ import annotations`
- `from collections.abc import Callable`
- `from contextlib import closing`
- `from datetime import datetime, timezone`
- `import json`
- `from pathlib import Path`
- `import sqlite3`
- `from .presentation import PresentationAuthority, PresentationDenied, PresentationError`
- `from .wardrobe import Wardrobe`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_service.py`
- `src/sofia/avatar/authoring.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/presentation_routine.py`
- `src/sofia/avatar/presentation_runtime.py`
- `src/sofia/cognition/activity.py`
- `src/sofia/conversation/store.py`
- `src/sofia/discord/binding.py`
- `src/sofia/discord/delivery.py`
- `src/sofia/discord/store.py`
- `src/sofia/distributed/identity_durable.py`
- `src/sofia/memory/chatgpt_export_store.py`
- `src/sofia/memory/chatgpt_import_store.py`
- `src/sofia/memory/provenance_store.py`
- `src/sofia/operational/store.py`
- `src/sofia/social/store.py`
- `src/sofia/state/sqlite_plane.py`
- `src/sofia/ui/drafts.py`
- `src/sofia/cognition/matrix/trace.py`
- `test/test_avatar_authoring.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_presentation_routine.py`
- `test/test_avatar_presentation_runtime.py`
- `test/test_avatar_presentation_store.py`
- `test/test_conversation.py`
- `test/test_memory_runtime_wiring.py`
- `test/test_operational_continuity.py`
- `test/test_ui_desktop_controller.py`
- `test/test_ui_drafts.py`

### `src/sofia/avatar/private_grant.py`

92 lines.

Definitions:
- `PrivatePresentationGrantResolver` (line 13)
- `__init__` (line 16)
- `last_error` (line 39)
- `resolve` (line 43)

Imports:
- `from __future__ import annotations`
- `from pathlib import Path`
- `from sofia.safe.operator_stop import OperatorStopStore`
- `from sofia.social.model import AudienceKind, PrincipalContext`
- `from sofia.social.principals import SPARKS_PRINCIPAL_ID`
- `from .presentation import PrivatePresentationGrant`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/background.py`
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_matrix.py`
- `src/sofia/application/emotional_conversation.py`
- `src/sofia/application/idle_reflection.py`
- `src/sofia/authorization/evaluator.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/self_fact_query.py`
- `src/sofia/capability/gateway.py`
- `src/sofia/capability/system.py`
- `src/sofia/clean/__main__.py`
- `src/sofia/clean/recovery.py`
- `src/sofia/codebase/codebase.py`
- `src/sofia/codebase/inspector.py`
- `src/sofia/cognition/model_lifecycle.py`
- `src/sofia/cognition/tools.py`
- `src/sofia/composition/authorization.py`
- `src/sofia/config/authority.py`
- `src/sofia/config/defaults.py`
- `src/sofia/config/state_store.py`
- `src/sofia/dev/git_workspace.py`
- `src/sofia/dev/opencode.py`
- `src/sofia/dev/supply_chain.py`
- `src/sofia/dev/workflow.py`
- `src/sofia/dev/workspace.py`
- `src/sofia/discord/delivery.py`
- `src/sofia/discord/discordpy.py`
- `src/sofia/discord/process_lock.py`
- `src/sofia/discord/store.py`
- `src/sofia/distributed/agent_main.py`
- `src/sofia/distributed/endpoint_policy_durable.py`
- `src/sofia/distributed/pki.py`
- `src/sofia/distributed/state_paths.py`
- `src/sofia/distributed/windows_agent_service_admin.py`
- `src/sofia/embodiment/measurement_query.py`
- `src/sofia/environment/query.py`
- `src/sofia/filesystem/change_capability.py`
- `src/sofia/filesystem/change_filter.py`
- `src/sofia/filesystem/inspector.py`
- `src/sofia/filesystem/observation.py`
- `src/sofia/habits/continuity.py`
- `src/sofia/habits/expectations.py`
- `src/sofia/integrate/capability_adapter.py`
- `src/sofia/integrations/sqlite.py`
- `src/sofia/integrations/storage.py`
- `src/sofia/interaction/core.py`
- `src/sofia/interaction/trusted_offer_gate.py`
- `src/sofia/knowledge/service.py`
- `src/sofia/machine/location_cli.py`
- `src/sofia/operational/status_queries.py`
- `src/sofia/ops/persistence.py`
- `src/sofia/ops/windows_bootstrap.py`
- `src/sofia/ops/windows_rekey_bootstrap.py`
- `src/sofia/personality/expression.py`
- `src/sofia/personality/observation_bridge.py`
- `src/sofia/personality/reflection_query.py`
- `src/sofia/run/active_release.py`
- `src/sofia/run/release.py`
- `src/sofia/run/runtime_child.py`
- `src/sofia/run/runtime_service.py`
- `src/sofia/run/service_admin.py`
- `src/sofia/run/supervisor.py`
- `src/sofia/runtime/response.py`
- `src/sofia/runtime/runtime.py`
- `src/sofia/safe/capability_policy.py`
- `src/sofia/state/atomic_file.py`
- `src/sofia/ui/process_lock.py`
- `src/sofia/ui/settings_window.py`
- `src/sofia/ui/tray_agent.py`
- `src/sofia/ui/tray_launcher.py`
- `src/sofia/ui/windows_startup.py`
- `src/sofia/cognition/matrix/evidence.py`
- `src/sofia/verify/interaction/disposable_live_offer_probe.py`
- `src/sofia/verify/interaction/live_behavior_probe.py`
- `test/test_authorization_evaluator.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_presentation_runtime.py`
- `test/test_avatar_private_grant.py`
- `test/test_avatar_self_fact_query.py`
- `test/test_canonical_embodiment.py`
- `test/test_capability_gateway.py`
- `test/test_capability_system.py`
- `test/test_cognition_matrix.py`
- `test/test_dev_wave1_acceptance.py`
- `test/test_distributed_agent_main.py`
- `test/test_distributed_pki.py`
- `test/test_distributed_windows_agent_service.py`
- `test/test_embodiment_measurement_cognition.py`
- `test/test_embodiment_measurement_query.py`
- `test/test_environment_acceptance.py`
- `test/test_environment_behavior_matrix.py`
- `test/test_environment_query.py`
- `test/test_filesystem.py`
- `test/test_filesystem_observation.py`
- `test/test_habit_foundation.py`
- `test/test_idle_reflection_worker.py`
- `test/test_interaction_ab_probe.py`
- `test/test_interaction_avatar_world.py`
- `test/test_interaction_behavior_matrix.py`
- `test/test_interaction_chat_projection.py`
- `test/test_interaction_consent_followup.py`
- `test/test_interaction_contextual_all_regions.py`
- `test/test_interaction_decision_expression.py`
- `test/test_interaction_focused_probe.py`
- `test/test_interaction_i5_i7_batch.py`
- `test/test_interaction_i7_compound_regression.py`
- `test/test_interaction_import_order.py`
- `test/test_interaction_lab.py`
- `test/test_interaction_live_boundaries.py`
- `test/test_interaction_live_claims.py`
- `test/test_interaction_live_discussion.py`
- `test/test_interaction_live_phrase_coverage.py`
- `test/test_interaction_live_stop_repetition.py`
- `test/test_interaction_region_cue_collision.py`
- `test/test_interaction_registry.py`
- `test/test_interaction_shared_engine.py`
- `test/test_interaction_v2_cross_modal.py`
- `test/test_interaction_v2_live_grammar.py`
- `test/test_interaction_world_observation.py`
- `test/test_interaction_world_text.py`
- `test/test_operational_status_queries.py`
- `test/test_ops_windows_rekey_bootstrap.py`
- `test/test_personality_pipeline.py`
- `test/test_proactive_continuity_awareness.py`
- `test/test_production_storage_boundary.py`
- `test/test_reflection_query.py`
- `test/test_run_active_release.py`
- `test/test_run_service_admin.py`
- `test/test_runtime.py`
- `test/test_tools_completion_acceptance.py`
- `test/test_voice_matrix.py`

### `src/sofia/avatar/self_fact_query.py`

652 lines.

Definitions:
- `AvatarSelfFactAnswer` (line 18)
- `_normalize` (line 31)
- `_friendly_outfit` (line 60)
- `AvatarSelfFactResolver` (line 73)
- `__post_init__` (line 22)
- `allows_private_projection` (line 94)
- `_is_presentation_reason_query` (line 215)
- `_is_current_outfit_query` (line 219)
- `_is_current_outfit_state_followup` (line 233)
- `_is_undergarment_query` (line 244)
- `_is_body_description_query` (line 254)
- `_measurement_text` (line 268)
- `_requested_undergarment_categories` (line 276)
- `_matrix_garments` (line 289)
- `resolve` (line 305)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `import re`
- `from sofia.embodiment.model import Embodiment`
- `from .presentation import AttireMode, PresentationProjection`
- `from .wardrobe_matrix import WardrobeSlotMatrix`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_matrix.py`
- `src/sofia/application/emotional_conversation.py`
- `src/sofia/authorization/evaluator.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/private_grant.py`
- `src/sofia/capability/gateway.py`
- `src/sofia/capability/system.py`
- `src/sofia/clean/__main__.py`
- `src/sofia/clean/recovery.py`
- `src/sofia/codebase/codebase.py`
- `src/sofia/codebase/inspector.py`
- `src/sofia/cognition/tools.py`
- `src/sofia/composition/authorization.py`
- `src/sofia/config/authority.py`
- `src/sofia/config/defaults.py`
- `src/sofia/config/state_store.py`
- `src/sofia/dev/git_workspace.py`
- `src/sofia/dev/opencode.py`
- `src/sofia/dev/supply_chain.py`
- `src/sofia/dev/workflow.py`
- `src/sofia/dev/workspace.py`
- `src/sofia/discord/discordpy.py`
- `src/sofia/discord/process_lock.py`
- `src/sofia/distributed/agent_main.py`
- `src/sofia/distributed/endpoint_policy_durable.py`
- `src/sofia/distributed/pki.py`
- `src/sofia/distributed/state_paths.py`
- `src/sofia/distributed/windows_agent_service_admin.py`
- `src/sofia/embodiment/measurement_query.py`
- `src/sofia/environment/query.py`
- `src/sofia/filesystem/change_capability.py`
- `src/sofia/filesystem/change_filter.py`
- `src/sofia/filesystem/inspector.py`
- `src/sofia/filesystem/observation.py`
- `src/sofia/habits/continuity.py`
- `src/sofia/habits/expectations.py`
- `src/sofia/integrate/capability_adapter.py`
- `src/sofia/integrations/sqlite.py`
- `src/sofia/integrations/storage.py`
- `src/sofia/interaction/core.py`
- `src/sofia/interaction/trusted_offer_gate.py`
- `src/sofia/knowledge/service.py`
- `src/sofia/machine/location_cli.py`
- `src/sofia/operational/status_queries.py`
- `src/sofia/ops/windows_bootstrap.py`
- `src/sofia/ops/windows_rekey_bootstrap.py`
- `src/sofia/personality/expression.py`
- `src/sofia/personality/observation_bridge.py`
- `src/sofia/personality/reflection_query.py`
- `src/sofia/run/active_release.py`
- `src/sofia/run/release.py`
- `src/sofia/run/runtime_child.py`
- `src/sofia/run/runtime_service.py`
- `src/sofia/run/service_admin.py`
- `src/sofia/run/supervisor.py`
- `src/sofia/runtime/response.py`
- `src/sofia/runtime/runtime.py`
- `src/sofia/safe/capability_policy.py`
- `src/sofia/ui/process_lock.py`
- `src/sofia/ui/settings_window.py`
- `src/sofia/ui/tray_agent.py`
- `src/sofia/ui/tray_launcher.py`
- `src/sofia/ui/windows_startup.py`
- `src/sofia/cognition/matrix/evidence.py`
- `src/sofia/verify/interaction/disposable_live_offer_probe.py`
- `src/sofia/verify/interaction/live_behavior_probe.py`
- `test/test_authorization_evaluator.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_presentation_runtime.py`
- `test/test_avatar_private_grant.py`
- `test/test_avatar_self_fact_query.py`
- `test/test_canonical_embodiment.py`
- `test/test_capability_gateway.py`
- `test/test_capability_system.py`
- `test/test_cognition_matrix.py`
- `test/test_dev_wave1_acceptance.py`
- `test/test_distributed_agent_main.py`
- `test/test_distributed_pki.py`
- `test/test_distributed_windows_agent_service.py`
- `test/test_embodiment_measurement_cognition.py`
- `test/test_embodiment_measurement_query.py`
- `test/test_environment_acceptance.py`
- `test/test_environment_behavior_matrix.py`
- `test/test_environment_query.py`
- `test/test_filesystem.py`
- `test/test_filesystem_observation.py`
- `test/test_habit_foundation.py`
- `test/test_interaction_ab_probe.py`
- `test/test_interaction_avatar_world.py`
- `test/test_interaction_behavior_matrix.py`
- `test/test_interaction_chat_projection.py`
- `test/test_interaction_consent_followup.py`
- `test/test_interaction_contextual_all_regions.py`
- `test/test_interaction_decision_expression.py`
- `test/test_interaction_focused_probe.py`
- `test/test_interaction_i5_i7_batch.py`
- `test/test_interaction_i7_compound_regression.py`
- `test/test_interaction_import_order.py`
- `test/test_interaction_lab.py`
- `test/test_interaction_live_boundaries.py`
- `test/test_interaction_live_claims.py`
- `test/test_interaction_live_discussion.py`
- `test/test_interaction_live_phrase_coverage.py`
- `test/test_interaction_live_stop_repetition.py`
- `test/test_interaction_region_cue_collision.py`
- `test/test_interaction_registry.py`
- `test/test_interaction_shared_engine.py`
- `test/test_interaction_v2_cross_modal.py`
- `test/test_interaction_v2_live_grammar.py`
- `test/test_interaction_world_observation.py`
- `test/test_interaction_world_text.py`
- `test/test_operational_status_queries.py`
- `test/test_ops_windows_rekey_bootstrap.py`
- `test/test_personality_pipeline.py`
- `test/test_proactive_continuity_awareness.py`
- `test/test_production_storage_boundary.py`
- `test/test_reflection_query.py`
- `test/test_run_active_release.py`
- `test/test_run_service_admin.py`
- `test/test_runtime.py`
- `test/test_tools_completion_acceptance.py`
- `test/test_voice_matrix.py`

### `src/sofia/avatar/wardrobe.py`

224 lines.

Definitions:
- `normalize_slots` (line 54)
- `WardrobeError` (line 71)
- `WardrobeConflict` (line 75)
- `VisibilityDenied` (line 79)
- `Layer` (line 83)
- `_identifier` (line 91)
- `Garment` (line 98)
- `Outfit` (line 133)
- `Wardrobe` (line 142)
- `__post_init__` (line 111)
- `__init__` (line 145)
- `selection` (line 153)
- `garments` (line 195)
- `require_public_ready` (line 200)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from enum import IntEnum`
- `import re`

Top-level constants:
- `_ID`
- `SINGLETON_SLOTS`
- `LEAF_SLOTS`
- `SLOTS`
- `COVERED_DEFAULT`

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/avatar/authoring.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/presentation.py`
- `src/sofia/avatar/presentation_runtime.py`
- `src/sofia/avatar/presentation_store.py`
- `src/sofia/avatar/self_fact_query.py`
- `src/sofia/avatar/wardrobe_catalog.py`
- `src/sofia/avatar/wardrobe_design.py`
- `src/sofia/avatar/wardrobe_matrix.py`
- `src/sofia/avatar/wardrobe_planner.py`
- `src/sofia/cognition/model_lifecycle.py`
- `src/sofia/cognition/routing.py`
- `src/sofia/composition/engines.py`
- `src/sofia/interaction/goal_journal.py`
- `src/sofia/operational/status_queries.py`
- `src/sofia/personality/expression.py`
- `src/sofia/runtime/response.py`
- `src/sofia/ui/remote_client.py`
- `src/sofia/ui/theme.py`
- `src/sofia/ui/tray_agent.py`
- `src/sofia/verify/dual_cognition.py`
- `test/test_avatar_behavior_matrix.py`
- `test/test_avatar_runtime_projection.py`
- `test/test_avatar_wardrobe_catalog.py`
- `test/test_avatar_wardrobe_creator.py`
- `test/test_avatar_wardrobe_environment_context.py`
- `test/test_avatar_wardrobe_environment_profiles.py`
- `test/test_avatar_wardrobe_graphics.py`
- `test/test_avatar_wardrobe_metadata.py`
- `test/test_avatar_wardrobe_profile_validation.py`
- `test/test_avatar_wardrobe_routine.py`
- `test/test_memory_retrieval_projection.py`
- `test/test_model_configuration_independence.py`
- `test/test_model_lifecycle.py`
- `test/test_operational_status_queries.py`
- `test/test_production_dual_cognition.py`
- `test/test_ui_tray_models.py`

### `src/sofia/avatar/wardrobe_autonomy.py`

205 lines.

Definitions:
- `WardrobeAutonomyDecision` (line 19)
- `WardrobeAutonomyContext` (line 43)
- `WardrobeAutonomyPolicy` (line 71)
- `__post_init__` (line 24)
- `__post_init__` (line 50)
- `decide` (line 80)
- `decide_contextual` (line 98)
- `_counter` (line 195)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from sofia.cognition.matrix import ContextualInfluencePlan, InfluenceMode, InfluenceSignal, InfluenceSurface`
- `from sofia.personality.influence import ContinuityInfluence`
- `from .clothing_intent import ClothingActionIntent`
- `from .wardrobe_planner import OutfitPlan, WardrobeContext`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `src/sofia/avatar/clothing_action.py`
- `test/test_avatar_clothing_action.py`

### `src/sofia/avatar/wardrobe_catalog.py`

1372 lines.

Definitions:
- `RequestStatus` (line 59)
- `StyleInput` (line 66)
- `GarmentBlueprint` (line 87)
- `WardrobePrebuild` (line 222)
- `_starter_profiles` (line 434)
- `_blueprint` (line 1110)
- `_no_graphic` (line 1148)
- `build_starter_wardrobe` (line 1152)
- `__post_init__` (line 74)
- `__post_init__` (line 94)
- `primary_hex` (line 121)
- `accent_hexes` (line 125)
- `material` (line 133)
- `construction` (line 137)
- `fit_anchors` (line 159)
- `category` (line 163)
- `style_tags` (line 174)
- `private_only` (line 178)
- `description` (line 182)
- `design_signature` (line 186)
- `__post_init__` (line 228)
- `reviewed_preferences` (line 283)
- `preset` (line 317)
- `pieces` (line 323)
- `closet_summary` (line 347)
- `manifest` (line 362)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass, replace`
- `from enum import Enum`
- `from hashlib import sha256`
- `import json`
- `import re`
- `from .fit import DEFAULT_FIT_ANCHORS`
- `from .wardrobe import Garment, Wardrobe, WardrobeError`
- `from .wardrobe_design import ComfortProfile, ContextProfile, EnvironmentProfile, FabricWeight, GarmentDesign, GraphicDesign, HumidityProfile, MaterialProperties, MoistureProfile, MovementProfile, PrecipitationProfile, RatedContext, Suitability, SunlightProfile, TemperatureProfile, TraitLevel, WindProfile, garment_type, resolve_color, validate_design`
- `from .wardrobe_planner import Activity, OutfitPlan, Preference, PreferenceActor, PreferenceTarget, Season, Sentiment`

Top-level constants:
- `_ID`
- `DRAFT_STATUS`
- `ALL_SEASONS`
- `DAY_DEFAULT_OUTFIT_ID`
- `NIGHT_LOUNGE_OUTFIT_ID`
- `FALLBACK_OUTFIT_ID`

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/act/delivery.py`
- `src/sofia/act/outreach.py`
- `src/sofia/act/system_notice.py`
- `src/sofia/action/model.py`
- `src/sofia/application/act_service.py`
- `src/sofia/application/bootstrap.py`
- `src/sofia/application/conversation_matrix.py`
- `src/sofia/application/conversation_service.py`
- `src/sofia/application/emotional_conversation.py`
- `src/sofia/authority/model.py`
- `src/sofia/avatar/authoring.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/presentation.py`
- `src/sofia/avatar/presentation_routine.py`
- `src/sofia/avatar/presentation_runtime.py`
- `src/sofia/avatar/self_fact_query.py`
- `src/sofia/avatar/wardrobe.py`
- `src/sofia/avatar/wardrobe_autonomy.py`
- `src/sofia/avatar/wardrobe_design.py`
- `src/sofia/avatar/wardrobe_matrix.py`
- `src/sofia/avatar/wardrobe_planner.py`
- `src/sofia/capability/catalog.py`
- `src/sofia/capability/model.py`
- `src/sofia/clean/__main__.py`
- `src/sofia/clean/recovery.py`
- `src/sofia/codebase/codebase.py`
- `src/sofia/cognition/assembler.py`
- `src/sofia/cognition/model.py`
- `src/sofia/cognition/self_state.py`
- `src/sofia/cognition/tools.py`
- `src/sofia/config/layout.py`
- `src/sofia/dev/capability.py`
- `src/sofia/dev/change_review.py`
- `src/sofia/dev/release.py`
- `src/sofia/dev/release_cli.py`
- `src/sofia/dev/release_signing.py`
- `src/sofia/dev/release_store.py`
- `src/sofia/dev/supply_chain.py`
- `src/sofia/distributed/capability.py`
- `src/sofia/distributed/inference.py`
- `src/sofia/distributed/pki.py`
- `src/sofia/distributed/windows_agent_service_admin.py`
- `src/sofia/embodiment/model.py`
- `src/sofia/embodiment/store.py`
- `src/sofia/emotion/journal.py`
- `src/sofia/emotion/model.py`
- `src/sofia/evolve/executor.py`
- `src/sofia/evolve/revision.py`
- `src/sofia/evolve/state_plane_adapter.py`
- `src/sofia/external/authentication.py`
- `src/sofia/external/capability.py`
- `src/sofia/external/knowledge.py`
- `src/sofia/external/model.py`
- `src/sofia/filesystem/capability.py`
- `src/sofia/filesystem/change_capability.py`
- `src/sofia/habits/continuity.py`
- `src/sofia/habits/engine.py`
- `src/sofia/habits/pattern_store.py`
- `src/sofia/habits/patterns.py`
- `src/sofia/integrate/capability_adapter.py`
- `src/sofia/integrate/governed.py`
- `src/sofia/integrate/policy.py`
- `src/sofia/integrate/registry.py`
- `src/sofia/integrations/capabilities.py`
- `src/sofia/integrations/sqlite.py`
- `src/sofia/interaction/chat.py`
- `src/sofia/interaction/core.py`
- `src/sofia/interaction/expanded_service.py`
- `src/sofia/interaction/grammar.py`
- `src/sofia/interaction/registry.py`
- `src/sofia/interaction/source_link.py`
- `src/sofia/knowledge/capability.py`
- `src/sofia/machine/capability.py`
- `src/sofia/machine/location_cli.py`
- `src/sofia/memory/chatgpt_export.py`
- `src/sofia/operational/model.py`
- `src/sofia/ops/backup.py`
- `src/sofia/ops/backup_cli.py`
- `src/sofia/ops/capability.py`
- `src/sofia/ops/discovery_canary.py`
- `src/sofia/ops/windows_bootstrap.py`
- `src/sofia/ops/windows_rekey_bootstrap.py`
- `src/sofia/personality/expression.py`
- `src/sofia/personality/observation_bridge.py`
- `src/sofia/personality/reflection.py`
- `src/sofia/personality/thought_agent.py`
- `src/sofia/run/active_release.py`
- `src/sofia/run/release.py`
- `src/sofia/run/runtime_service.py`
- `src/sofia/run/service_admin.py`
- `src/sofia/run/watchdog_service.py`
- `src/sofia/run/windows_service_spec.py`
- `src/sofia/safe/release.py`
- `src/sofia/safe/release_ed25519.py`
- `src/sofia/system/capability.py`
- `src/sofia/system/linux.py`
- `src/sofia/system/model.py`
- `src/sofia/system/windows.py`
- `src/sofia/ui/settings_window.py`
- `src/sofia/ui/theme.py`
- `src/sofia/verify/compatibility_matrix.py`
- `src/sofia/verify/semantic_integrity.py`
- `src/sofia/voice/sapi.py`
- `src/sofia/cognition/providers/ollama_provider.py`
- `src/sofia/verify/interaction/ab_probe.py`
- `src/sofia/verify/interaction/architecture_compare.py`
- `src/sofia/verify/interaction/avatar_world_probe.py`
- `src/sofia/verify/interaction/boundary_counterfactual_probe.py`
- `src/sofia/verify/interaction/decision_expression_probe.py`
- `src/sofia/verify/interaction/disposable_live_offer_probe.py`
- `src/sofia/verify/interaction/focused_probe.py`
- `src/sofia/verify/interaction/live_behavior_probe.py`
- `src/sofia/verify/interaction/route_boundary_probe.py`
- `test/test_act_delivery.py`
- `test/test_act_outreach.py`
- `test/test_act_system_notice.py`
- `test/test_action.py`
- `test/test_action_authority_boundary.py`
- `test/test_avatar_authoring.py`
- `test/test_avatar_behavior_matrix.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_fit.py`
- `test/test_avatar_piece_catalog.py`
- `test/test_avatar_presentation.py`
- `test/test_avatar_presentation_routine.py`
- `test/test_avatar_presentation_runtime.py`
- `test/test_avatar_presentation_store.py`
- `test/test_avatar_self_fact_query.py`
- `test/test_avatar_starter_user_preferences.py`
- `test/test_avatar_wardrobe_catalog.py`
- `test/test_avatar_wardrobe_creator.py`
- `test/test_avatar_wardrobe_environment_profiles.py`
- `test/test_avatar_wardrobe_graphics.py`
- `test/test_avatar_wardrobe_matrix.py`
- `test/test_avatar_wardrobe_metadata.py`
- `test/test_avatar_wardrobe_routine.py`
- `test/test_canonical_embodiment.py`
- `test/test_capability_authority_boundary.py`
- `test/test_capability_gateway.py`
- `test/test_capability_model.py`
- `test/test_capability_system.py`
- `test/test_cognitive_action_integration.py`
- `test/test_cognitive_assembler.py`
- `test/test_cognitive_benchmark_contract.py`
- `test/test_cognitive_routing.py`
- `test/test_cognitive_self_state.py`
- `test/test_cognitive_self_state_assembler_contract.py`
- `test/test_cognitive_tools.py`
- `test/test_conversation_provider_live_regressions.py`
- `test/test_conversational_context_projection.py`
- `test/test_current_emotional_state.py`
- `test/test_default_runtime_provider_boundary.py`
- `test/test_dev_know_integrate_ops_cross_package.py`
- `test/test_dev_supply_chain.py`
- `test/test_distributed_inference.py`
- `test/test_distributed_inference_service.py`
- `test/test_embodiment_semantic_contract.py`
- `test/test_emotional_behavior_matrix.py`
- `test/test_emotional_clarifications.py`
- `test/test_emotional_conversation_integration.py`
- `test/test_emotional_journal.py`
- `test/test_environment_behavior_matrix.py`
- `test/test_external_action.py`
- `test/test_external_knowledge.py`
- `test/test_external_model.py`
- `test/test_habit_contextual_matrix.py`
- `test/test_habit_foundation.py`
- `test/test_idle_reflection_worker.py`
- `test/test_interaction_ab_probe.py`
- `test/test_interaction_chat_projection.py`
- `test/test_interaction_conversation_offer_context.py`
- `test/test_interaction_extended_emotions.py`
- `test/test_interaction_route_boundary_probe.py`
- `test/test_know_integrate_wave1_acceptance.py`
- `test/test_know_integrate_waves3_5_acceptance.py`
- `test/test_observation_bridge.py`
- `test/test_observation_bridge_self_noise.py`
- `test/test_ollama_provider.py`
- `test/test_ollama_repetition_guard.py`
- `test/test_ops_backup_restore.py`
- `test/test_personality_embodiment_contract.py`
- `test/test_personality_journal_thread_safety.py`
- `test/test_reflection_conversation_integration.py`
- `test/test_reflection_journal.py`
- `test/test_rel_habit_matrix.py`
- `test/test_release_compatibility_matrix.py`
- `test/test_run_active_release.py`
- `test/test_run_windows_service_spec.py`
- `test/test_system_capability_contract.py`
- `test/test_system_linux_backend.py`
- `test/test_system_windows_backend.py`
- `test/test_thought_agent.py`
- `test/test_thought_agent_conversation.py`
- `test/test_thought_agent_live_ollama.py`
- `test/test_thought_urgency_evidence.py`
- `test/test_ui_theme.py`
- `test/test_waves3_5_cross_package_acceptance.py`

### `src/sofia/avatar/wardrobe_design.py`

942 lines.

Definitions:
- `resolve_color` (line 29)
- `GarmentFamily` (line 42)
- `GarmentTypeDefinition` (line 54)
- `GraphicDesign` (line 93)
- `Suitability` (line 117)
- `TraitLevel` (line 137)
- `FabricWeight` (line 145)
- `MaterialProperties` (line 154)
- `TemperatureProfile` (line 188)
- `PrecipitationProfile` (line 257)
- `MoistureProfile` (line 292)
- `HumidityProfile` (line 318)
- `WindProfile` (line 349)
- `SunlightProfile` (line 367)
- `EnvironmentProfile` (line 385)
- `RatedContext` (line 425)
- `MovementProfile` (line 476)
- `ContextProfile` (line 501)
- `ComfortProfile` (line 539)
- `GarmentDesign` (line 574)
- `_type` (line 663)
- `garment_type` (line 902)
- `all_garment_types` (line 911)
- `validate_design` (line 915)
- `__post_init__` (line 67)
- `__post_init__` (line 98)
- `score` (line 126)
- `__post_init__` (line 161)
- `as_dict` (line 177)
- `__post_init__` (line 195)
- `suitability_for` (line 227)
- `as_dict` (line 240)
- `__post_init__` (line 265)
- `rating` (line 275)
- `as_dict` (line 282)
- `__post_init__` (line 298)
- `as_dict` (line 308)
- `__post_init__` (line 323)
- `rating` (line 330)
- `as_dict` (line 340)
- `__post_init__` (line 353)
- `as_dict` (line 359)
- `__post_init__` (line 371)
- `as_dict` (line 377)
- `__post_init__` (line 395)
- `as_dict` (line 411)
- `__post_init__` (line 432)
- `rating` (line 451)
- `as_dict` (line 465)
- `__post_init__` (line 481)
- `as_dict` (line 492)
- `__post_init__` (line 510)
- `as_dict` (line 526)
- `__post_init__` (line 547)
- `as_dict` (line 562)
- `__post_init__` (line 602)
- `fahrenheit` (line 241)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass, field`
- `from enum import Enum`
- `import re`
- `from .wardrobe import Layer, WardrobeError`

Top-level constants:
- `_TOKEN`
- `_STYLE`
- `_HEX`
- `_TYPE_BY_ID`

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/avatar/authoring.py`
- `src/sofia/avatar/wardrobe_catalog.py`
- `src/sofia/avatar/wardrobe_matrix.py`
- `src/sofia/avatar/wardrobe_planner.py`
- `src/sofia/environment/home_assistant.py`
- `src/sofia/environment/query_forms.py`
- `test/test_avatar_piece_catalog.py`
- `test/test_avatar_wardrobe_creator.py`
- `test/test_avatar_wardrobe_environment_profiles.py`
- `test/test_avatar_wardrobe_graphics.py`
- `test/test_avatar_wardrobe_matrix.py`
- `test/test_avatar_wardrobe_profile_validation.py`
- `test/test_environment_query.py`
- `test/test_ui_application.py`

### `src/sofia/avatar/wardrobe_matrix.py`

136 lines.

Definitions:
- `WardrobeMatrixCell` (line 20)
- `WardrobeSlotMatrix` (line 35)
- `build_wardrobe_matrix` (line 90)
- `cell` (line 42)
- `as_dict` (line 61)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from typing import TYPE_CHECKING`
- `from .wardrobe import LEAF_SLOTS, Layer, WardrobeError, normalize_slots`
- `from .wardrobe_catalog import WardrobePrebuild`
- `from .wardrobe_catalog import WardrobePrebuild`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/avatar/presentation_runtime.py`
- `src/sofia/avatar/self_fact_query.py`
- `src/sofia/avatar/wardrobe_catalog.py`
- `src/sofia/avatar/wardrobe_design.py`
- `test/test_avatar_self_fact_query.py`
- `test/test_avatar_wardrobe_matrix.py`
- `test/test_ui_application.py`

### `src/sofia/avatar/wardrobe_planner.py`

829 lines.

Definitions:
- `Activity` (line 25)
- `Weather` (line 40)
- `EnvironmentMode` (line 47)
- `WearSetting` (line 52)
- `Formality` (line 63)
- `MovementDemand` (line 71)
- `SunExposure` (line 79)
- `Cadence` (line 85)
- `PreferenceActor` (line 91)
- `PreferenceTarget` (line 96)
- `Sentiment` (line 102)
- `_id` (line 110)
- `_aware` (line 118)
- `WeatherObservation` (line 125)
- `EmotionStyleInfluence` (line 138)
- `WardrobeContext` (line 175)
- `OutfitPlan` (line 433)
- `Preference` (line 479)
- `WornEvidence` (line 507)
- `OutfitProposal` (line 520)
- `period_key` (line 529)
- `OutfitPlanner` (line 541)
- `wardrobe_emotion_influences` (line 797)
- `__post_init__` (line 130)
- `__post_init__` (line 151)
- `__post_init__` (line 196)
- `from_environment_snapshot` (line 242)
- `effective_weather` (line 359)
- `effective_temperature_c` (line 366)
- `effective_humidity_percent` (line 379)
- `precipitation_kind` (line 390)
- `daypart` (line 413)
- `lounge_window` (line 426)
- `__post_init__` (line 445)
- `__post_init__` (line 488)
- `__post_init__` (line 513)
- `__init__` (line 544)
- `_movement_rating` (line 588)
- `_design_score` (line 602)
- `_outfit_profile_score` (line 674)
- `suggest` (line 692)
- `score` (line 725)

Imports:
- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime, timedelta, timezone`
- `from enum import Enum, IntEnum`
- `from sofia.environment.model import DaylightState, EnvironmentFreshness, EnvironmentSnapshot, Season`
- `from sofia.personality.influence import ContinuityInfluence`
- `from .wardrobe import Wardrobe, WardrobeError, Outfit`
- `from .wardrobe_design import GarmentDesign, Suitability`

Top-level constants:

Candidate reference files (lexical evidence, not production reachability):
- `src/sofia/application/bootstrap.py`
- `src/sofia/avatar/authoring.py`
- `src/sofia/avatar/clothing_action.py`
- `src/sofia/avatar/presentation_routine.py`
- `src/sofia/avatar/wardrobe_autonomy.py`
- `src/sofia/avatar/wardrobe_catalog.py`
- `src/sofia/environment/__init__.py`
- `src/sofia/environment/home_assistant.py`
- `src/sofia/environment/model.py`
- `src/sofia/environment/nws.py`
- `src/sofia/environment/prompt.py`
- `src/sofia/environment/provider.py`
- `src/sofia/environment/query_sources.py`
- `src/sofia/habits/continuity.py`
- `src/sofia/integrations/nws.py`
- `src/sofia/interaction/conversation_offer_context.py`
- `src/sofia/interaction/temporal.py`
- `src/sofia/memory/promoted_retrieval.py`
- `src/sofia/personality/influence.py`
- `src/sofia/personality/reflection.py`
- `src/sofia/personality/thought_agent.py`
- `src/sofia/runtime/response.py`
- `src/sofia/ui/settings_window.py`
- `src/sofia/voice/prosody_matrix.py`
- `src/sofia/cognition/matrix/expression_plan.py`
- `src/sofia/cognition/matrix/influence.py`
- `test/test_avatar_authoring.py`
- `test/test_avatar_behavior_matrix.py`
- `test/test_avatar_clothing_action.py`
- `test/test_avatar_presentation_routine.py`
- `test/test_avatar_runtime_projection.py`
- `test/test_avatar_wardrobe_context_projection.py`
- `test/test_avatar_wardrobe_creator.py`
- `test/test_avatar_wardrobe_environment_context.py`
- `test/test_avatar_wardrobe_routine.py`
- `test/test_contextual_influence_matrix.py`
- `test/test_conversation.py`
- `test/test_conversation_service.py`
- `test/test_embodied_expression_plan.py`
- `test/test_emotional_behavior_matrix.py`
- `test/test_emotional_conversation_integration.py`
- `test/test_environment_acceptance.py`
- `test/test_environment_behavior_matrix.py`
- `test/test_environment_model.py`
- `test/test_environment_prompt.py`
- `test/test_environment_query.py`
- `test/test_environment_service.py`
- `test/test_habit_contextual_matrix.py`
- `test/test_habit_foundation.py`
- `test/test_idle_reflection_application.py`
- `test/test_interaction_decision_expression.py`
- `test/test_internal_workspace_awareness.py`
- `test/test_memory_promoted_retrieval.py`
- `test/test_memory_runtime_wiring.py`
- `test/test_ollama_repetition_guard.py`
- `test/test_reflection_query.py`
- `test/test_rel_habit_matrix.py`
- `test/test_thought_agent.py`
- `test/test_ui_theme.py`
- `test/test_voice_prosody_matrix.py`
