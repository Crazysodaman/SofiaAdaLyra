# authority cleanup report

Phase 8; base `b755190e6c2d1706bd2962a6d23dfd88746e47ef`.

Three files own immutable operation authority and its matrix adapter. Runtime builds operation Authority; cognition tool filtering invokes can_use_capability; default matrix registry registers AuthorityMatrixEvaluator. Action/capability execution still checks its own authority boundaries.

| Original file | Decision | Responsibility and usage evidence |
| --- | --- | --- |
| `__init__.py` | KEEP | Exports the canonical model/evaluator without another state owner. |
| `matrix.py` | KEEP | Default matrix registry invokes the Authority evaluator before routing. |
| `model.py` | KEEP | Authority used by runtime/operation/tool filtering; can_use_capability is a live exposure check, not execution permission. |

No merge or deletion warranted. One model and one adapter separate values from matrix integration; there is no duplicate mutable authority ledger. Validators and hook methods remain used by construction/routing. Retention is grounded in runtime and tool-filtering callers, not own tests.

## Validation and remaining scope

Authority/cognition matrix/action and capability authority/tool gate 154 passed in 0.49s. Latest full source snapshot 3,375 passed, 7 diagnosed failures, 2 skipped. Documentation-only checkpoint; source unchanged.

Authority is scoped immutable evidence on an operation; standing policy and durable approvals remain in SAFE/config rather than being copied here.

Checkpoint: `git log -1 --format=%H -- docs/development/authority-cleanup-report.md`.

## Definition, import and reference inventory

Reference candidates below are lexical evidence, not a resolved Python call graph. Each method is listed; receiver identity, callbacks, package exports and module-local calls require inspection. Production paths and intentional offline APIs are identified above. Existing state rows/files belonging to retired prototypes are not deleted by source cleanup.

### `src/sofia/authority/__init__.py`

5 lines before cleanup.

Imports: `from sofia.authority.model import Authority`

Incoming imports: None.

Top-level constants: `__all__`


### `src/sofia/authority/matrix.py`

20 lines before cleanup.

Imports: `from sofia.cognition.matrix.model import DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance`

Incoming imports: `src/sofia/cognition/matrix/defaults.py`; `test/test_authority.py`

Top-level constants: None.

- `AuthorityMatrixEvaluator` (line 10): source candidates `src/sofia/cognition/matrix/defaults.py`; test candidates `test/test_authority.py`.
- `evaluate` (line 13): source candidates `src/sofia/act/__init__.py`, `src/sofia/act/delivery.py`, `src/sofia/act/outreach.py`, `src/sofia/act/system_notice.py`, `src/sofia/application/bootstrap.py`, `src/sofia/application/conversation_matrix.py`, `src/sofia/application/conversation_service.py`, `src/sofia/authorization/evaluator.py`, `src/sofia/avatar/matrix.py`, `src/sofia/avatar/presentation_routine.py`, `src/sofia/body/matrix.py`, `src/sofia/continuity/matrix.py`, `src/sofia/dev/matrix.py`, `src/sofia/distributed/inference.py`, `src/sofia/emotion/matrix.py`, `src/sofia/environment/matrix.py`, `src/sofia/external/adapter.py`, `src/sofia/habits/matrix.py`, `src/sofia/integrate/matrix.py`, `src/sofia/interaction/matrix.py`, `src/sofia/knowledge/matrix.py`, `src/sofia/machine/matrix.py`, `src/sofia/memory/matrix.py`, `src/sofia/ops/failure_matrix.py`, `src/sofia/ops/matrix.py`, `src/sofia/rel/matrix.py`, `src/sofia/social/matrix.py`, `src/sofia/verify/compatibility_matrix.py`, `src/sofia/voice/matrix.py`, `src/sofia/cognition/matrix/coordinator.py`, `src/sofia/cognition/matrix/defaults.py`; test candidates `test/test_act_outreach.py`, `test/test_authority.py`, `test/test_authorization_evaluator.py`, `test/test_avatar_presentation_routine.py`, `test/test_capability_composition_scope.py`, `test/test_cognition_matrix.py`, `test/test_conversation_service.py`, `test/test_filesystem_orchestrator.py`, `test/test_ops_failure_recovery_matrix.py`, `test/test_rel_habit_matrix.py`, `test/test_release_compatibility_matrix.py`, `test/test_semantic_domain_matrix.py`, `test/test_voice_matrix.py`.

### `src/sofia/authority/model.py`

115 lines before cleanup.

Imports: `from dataclasses import dataclass`

Incoming imports: `src/sofia/authority/__init__.py`; `src/sofia/cognition/operation.py`; `src/sofia/cognition/tools.py`; `src/sofia/operational/status_queries.py`; `src/sofia/runtime/runtime.py`; `src/sofia/cognition/matrix/authority.py`; `test/test_action.py`; `test/test_action_authority_boundary.py`; `test/test_authority.py`; `test/test_cognition.py`; `test/test_cognition_matrix.py`; `test/test_cognitive_action_integration.py`; `test/test_cognitive_operation.py`; `test/test_cognitive_operation_system.py`; `test/test_cognitive_tools.py`; `test/test_conversation_service.py`; `test/test_voice_matrix.py`

Top-level constants: None.

- `Authority` (line 5): source candidates `src/sofia/authority/__init__.py`, `src/sofia/cognition/operation.py`, `src/sofia/cognition/tools.py`, `src/sofia/operational/status_queries.py`, `src/sofia/runtime/runtime.py`, `src/sofia/ui/control_center.py`, `src/sofia/ui/settings_window.py`, `src/sofia/cognition/matrix/authority.py`; test candidates `test/test_action.py`, `test/test_action_authority_boundary.py`, `test/test_authority.py`, `test/test_cognition.py`, `test/test_cognition_matrix.py`, `test/test_cognitive_action_integration.py`, `test/test_cognitive_operation.py`, `test/test_cognitive_operation_system.py`, `test/test_cognitive_tools.py`, `test/test_conversation_service.py`, `test/test_ui_control_center.py`, `test/test_voice_matrix.py`.
- `__post_init__` (line 24): source candidates `src/sofia/act/delivery.py`, `src/sofia/act/outreach.py`, `src/sofia/action/model.py`, `src/sofia/authorization/model.py`, `src/sofia/avatar/clothing_intent.py`, `src/sofia/avatar/fit.py`, `src/sofia/avatar/presentation.py`, `src/sofia/avatar/self_fact_query.py`, `src/sofia/avatar/wardrobe.py`, `src/sofia/avatar/wardrobe_autonomy.py`, `src/sofia/avatar/wardrobe_design.py`, `src/sofia/avatar/wardrobe_planner.py`, `src/sofia/avatar/wardrobe_types.py`, `src/sofia/avatar/wardrobe_prebuild.py`, `src/sofia/capability/model.py`, `src/sofia/capability/proposal.py`, `src/sofia/codebase/model.py`, `src/sofia/cognition/activity.py`, `src/sofia/cognition/context.py`, `src/sofia/cognition/fleet_engine.py`, `src/sofia/cognition/grounding.py`, `src/sofia/cognition/model.py`, `src/sofia/cognition/operation.py`, `src/sofia/cognition/self_state.py`, `src/sofia/cognition/tools.py`, `src/sofia/config/authority.py`, `src/sofia/config/model.py`, `src/sofia/config/model_catalog.py`, `src/sofia/config/user_settings.py`, `src/sofia/continuity/model.py`, `src/sofia/conversation/model.py`, `src/sofia/dev/approval.py`, `src/sofia/dev/change_review.py`, `src/sofia/dev/opencode.py`, `src/sofia/dev/release.py`, `src/sofia/dev/supply_chain.py`, `src/sofia/discord/access.py`, `src/sofia/discord/provisioning.py`, `src/sofia/distributed/agent.py`, `src/sofia/distributed/authorization.py`, `src/sofia/distributed/capabilities.py`, `src/sofia/distributed/endpoint_policy.py`, `src/sofia/distributed/identity.py`, `src/sofia/distributed/inference.py`, `src/sofia/distributed/inference_service.py`, `src/sofia/distributed/model.py`, `src/sofia/distributed/operations.py`, `src/sofia/distributed/systemd_agent_service.py`, `src/sofia/distributed/version.py`, `src/sofia/embodiment/measurement_query.py`, `src/sofia/embodiment/model.py`, `src/sofia/environment/config.py`, `src/sofia/environment/model.py`, `src/sofia/environment/provider.py`, `src/sofia/environment/query.py`, `src/sofia/evolve/amendment.py`, `src/sofia/evolve/approval.py`, `src/sofia/evolve/executor.py`, `src/sofia/evolve/revision.py`, `src/sofia/external/authentication.py`, `src/sofia/external/capability.py`, `src/sofia/external/knowledge.py`, `src/sofia/external/model.py`, `src/sofia/filesystem/changes.py`, `src/sofia/filesystem/model.py`, `src/sofia/filesystem/observation.py`, `src/sofia/habits/expectations.py`, `src/sofia/habits/model.py`, `src/sofia/habits/patterns.py`, `src/sofia/identity/model.py`, `src/sofia/integrate/model.py`, `src/sofia/integrate/policy.py`, `src/sofia/interaction/world.py`, `src/sofia/knowledge/access.py`, `src/sofia/knowledge/model.py`, `src/sofia/machine/discovery.py`, `src/sofia/machine/hardware.py`, `src/sofia/machine/location.py`, `src/sofia/machine/model.py`, `src/sofia/machine/observation.py`, `src/sofia/memory/chatgpt_import.py`, `src/sofia/memory/historical.py`, `src/sofia/memory/originals.py`, `src/sofia/memory/provenance.py`, `src/sofia/net/discord_routes.py`, `src/sofia/operational/model.py`, `src/sofia/ops/activity.py`, `src/sofia/ops/agent_discovery.py`, `src/sofia/ops/approval.py`, `src/sofia/ops/backup.py`, `src/sofia/ops/bootstrap.py`, `src/sofia/ops/discovery.py`, `src/sofia/ops/enrollment.py`, `src/sofia/ops/failover.py`, `src/sofia/ops/failure_matrix.py`, `src/sofia/ops/lease.py`, `src/sofia/ops/maintenance.py`, `src/sofia/ops/migration.py`, `src/sofia/ops/model.py`, `src/sofia/ops/reconcile.py`, `src/sofia/ops/reconciliation_journal.py`, `src/sofia/ops/recovery.py`, `src/sofia/ops/repair_plan.py`, `src/sofia/ops/workload.py`, `src/sofia/personality/reflection_query.py`, `src/sofia/rel/model.py`, `src/sofia/run/heartbeat.py`, `src/sofia/run/host.py`, `src/sofia/run/periodic.py`, `src/sofia/run/supervisor.py`, `src/sofia/run/windows_service_spec.py`, `src/sofia/safe/execution_approval.py`, `src/sofia/safe/operator_stop.py`, `src/sofia/self_model/model.py`, `src/sofia/self_model/operational.py`, `src/sofia/social/model.py`, `src/sofia/state/component_schema.py`, `src/sofia/state/model.py`, `src/sofia/state/namespaces.py`, `src/sofia/system/model.py`, `src/sofia/ui/control_center.py`, `src/sofia/ui/drafts.py`, `src/sofia/ui/quick_tools.py`, `src/sofia/ui/theme.py`, `src/sofia/verify/compatibility_matrix.py`, `src/sofia/verify/release.py`, `src/sofia/voice/prosody_matrix.py`, `src/sofia/voice/tts.py`, `src/sofia/cognition/matrix/coordinator.py`, `src/sofia/cognition/matrix/expression_plan.py`, `src/sofia/cognition/matrix/influence.py`, `src/sofia/cognition/matrix/model.py`; test candidates `test/interaction_lab_support.py`.
- `can_use_capability` (line 75): source candidates `src/sofia/cognition/tools.py`; test candidates `test/test_authority.py`.
