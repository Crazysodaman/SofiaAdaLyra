# net cleanup report

Phase 9; base `074ab66a56ac6ad281005e50246327a5817358d6`.

Retired the unused offline Discord route-classification prototype.

| Original file | Decision | Responsibility and usage evidence |
| --- | --- | --- |
| `discord_routes.py` | DELETE | No production import or call path; only test_net_discord_routes exercised the classifier. Live Discord transport and distributed TLS own actual connections. |

The sole module defined Route, RouteDenial, RouteDecision, DiscordRoutePolicy and classify_discord_route. Nothing in composition, Discord startup, integrations or remote transport consumed them. Removing the module and its exclusive tests avoids presenting URL classification as a runtime network boundary. No production imports, exports, bootstrap hooks or persistent state needed repair; net had no package marker. Actual Discord startup/authentication/provisioning and mTLS admission remain intact.

## Validation and remaining scope

Dependency search confirmed no remaining net imports or retired classifier names in source/test/tools. Live Discord/remote mTLS/tool completion gate: 137 passed. Compile of the remaining production packages passed. The Phase 9 full-suite gate follows completion of filesystem; deleted exclusive tests are not replaced with skips.

Discord SDK/live runtime owns Discord connections; integrations owns configured service adapters; distributed owns authenticated remote operations. The retired classifier had no production state owner.

Checkpoint: `git log -1 --format=%H -- docs/development/net-cleanup-report.md`.

## Definition, import and reference inventory

Reference candidates below are lexical evidence, not a resolved Python call graph. Each method is listed; receiver identity, callbacks, package exports and module-local calls require inspection. Production paths and intentional offline APIs are identified above. Existing state rows/files belonging to retired prototypes are not deleted by source cleanup.

### `src/sofia/net/discord_routes.py`

61 lines before cleanup.

Imports: `from __future__ import annotations`; `from dataclasses import dataclass`; `from enum import Enum`; `from urllib.parse import urlsplit`

Incoming imports: `test/test_net_discord_routes.py`

Top-level constants: None.

- `Route` (line 11): source candidates `src/sofia/cognition/routing.py`, `src/sofia/interaction/chat.py`, `src/sofia/interaction/trusted_offer_gate.py`, `src/sofia/ui/service_control.py`; test candidates `test/test_net_discord_routes.py`.
- `RouteDenial` (line 16): source candidates none outside file; test candidates `test/test_net_discord_routes.py`.
- `RouteDecision` (line 23): source candidates none outside file; test candidates none.
- `DiscordRoutePolicy` (line 29): source candidates none outside file; test candidates `test/test_net_discord_routes.py`.
- `classify_discord_route` (line 37): source candidates none outside file; test candidates `test/test_net_discord_routes.py`.
- `__post_init__` (line 32): source candidates `src/sofia/act/delivery.py`, `src/sofia/act/outreach.py`, `src/sofia/action/model.py`, `src/sofia/authority/model.py`, `src/sofia/authorization/model.py`, `src/sofia/avatar/clothing_intent.py`, `src/sofia/avatar/fit.py`, `src/sofia/avatar/presentation.py`, `src/sofia/avatar/self_fact_query.py`, `src/sofia/avatar/wardrobe.py`, `src/sofia/avatar/wardrobe_autonomy.py`, `src/sofia/avatar/wardrobe_design.py`, `src/sofia/avatar/wardrobe_planner.py`, `src/sofia/avatar/wardrobe_types.py`, `src/sofia/avatar/wardrobe_prebuild.py`, `src/sofia/capability/model.py`, `src/sofia/codebase/model.py`, `src/sofia/cognition/activity.py`, `src/sofia/cognition/context.py`, `src/sofia/cognition/fleet_engine.py`, `src/sofia/cognition/grounding.py`, `src/sofia/cognition/model.py`, `src/sofia/cognition/operation.py`, `src/sofia/cognition/self_state.py`, `src/sofia/cognition/tools.py`, `src/sofia/config/authority.py`, `src/sofia/config/model.py`, `src/sofia/config/model_catalog.py`, `src/sofia/config/user_settings.py`, `src/sofia/continuity/model.py`, `src/sofia/conversation/model.py`, `src/sofia/dev/approval.py`, `src/sofia/dev/change_review.py`, `src/sofia/dev/opencode.py`, `src/sofia/dev/release.py`, `src/sofia/dev/supply_chain.py`, `src/sofia/discord/access.py`, `src/sofia/discord/provisioning.py`, `src/sofia/distributed/agent.py`, `src/sofia/distributed/authorization.py`, `src/sofia/distributed/capabilities.py`, `src/sofia/distributed/endpoint_policy.py`, `src/sofia/distributed/identity.py`, `src/sofia/distributed/inference.py`, `src/sofia/distributed/inference_service.py`, `src/sofia/distributed/model.py`, `src/sofia/distributed/operations.py`, `src/sofia/distributed/systemd_agent_service.py`, `src/sofia/distributed/version.py`, `src/sofia/embodiment/measurement_query.py`, `src/sofia/embodiment/model.py`, `src/sofia/environment/config.py`, `src/sofia/environment/model.py`, `src/sofia/environment/provider.py`, `src/sofia/environment/query.py`, `src/sofia/evolve/amendment.py`, `src/sofia/evolve/approval.py`, `src/sofia/evolve/executor.py`, `src/sofia/evolve/revision.py`, `src/sofia/external/authentication.py`, `src/sofia/external/capability.py`, `src/sofia/external/knowledge.py`, `src/sofia/external/model.py`, `src/sofia/filesystem/changes.py`, `src/sofia/filesystem/model.py`, `src/sofia/filesystem/observation.py`, `src/sofia/habits/expectations.py`, `src/sofia/habits/model.py`, `src/sofia/habits/patterns.py`, `src/sofia/identity/model.py`, `src/sofia/integrate/model.py`, `src/sofia/integrate/policy.py`, `src/sofia/interaction/world.py`, `src/sofia/knowledge/access.py`, `src/sofia/knowledge/model.py`, `src/sofia/machine/discovery.py`, `src/sofia/machine/hardware.py`, `src/sofia/machine/location.py`, `src/sofia/machine/model.py`, `src/sofia/machine/observation.py`, `src/sofia/memory/chatgpt_import.py`, `src/sofia/memory/historical.py`, `src/sofia/memory/originals.py`, `src/sofia/memory/provenance.py`, `src/sofia/operational/model.py`, `src/sofia/ops/activity.py`, `src/sofia/ops/agent_discovery.py`, `src/sofia/ops/backup.py`, `src/sofia/ops/bootstrap.py`, `src/sofia/ops/discovery.py`, `src/sofia/ops/enrollment.py`, `src/sofia/ops/fleet.py`, `src/sofia/ops/maintenance.py`, `src/sofia/ops/model.py`, `src/sofia/ops/reconcile.py`, `src/sofia/ops/reconciliation_journal.py`, `src/sofia/ops/recovery.py`, `src/sofia/ops/repair_plan.py`, `src/sofia/ops/workload.py`, `src/sofia/personality/reflection_query.py`, `src/sofia/rel/model.py`, `src/sofia/run/heartbeat.py`, `src/sofia/run/host.py`, `src/sofia/run/periodic.py`, `src/sofia/run/supervisor.py`, `src/sofia/run/windows_service_spec.py`, `src/sofia/safe/execution_approval.py`, `src/sofia/safe/operator_stop.py`, `src/sofia/self_model/model.py`, `src/sofia/self_model/operational.py`, `src/sofia/social/model.py`, `src/sofia/state/component_schema.py`, `src/sofia/state/model.py`, `src/sofia/state/namespaces.py`, `src/sofia/system/model.py`, `src/sofia/ui/control_center.py`, `src/sofia/ui/drafts.py`, `src/sofia/ui/quick_tools.py`, `src/sofia/ui/theme.py`, `src/sofia/voice/prosody_matrix.py`, `src/sofia/voice/tts.py`, `src/sofia/cognition/matrix/coordinator.py`, `src/sofia/cognition/matrix/expression_plan.py`, `src/sofia/cognition/matrix/influence.py`, `src/sofia/cognition/matrix/model.py`; test candidates `test/interaction_lab_support.py`.

Final Phase 9 full suite at the filesystem checkpoint: 3201 passed, 6 known failures, 2 skipped. Five failures require unavailable local Ollama; the Windows ProgramData fixture is addressed in Phase 10 config.
