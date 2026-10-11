# Workstream 1: Consolidated Unassessed-Task Audit Queue (2026-10-11)

**Frozen GitHub source SHA used for this triage:** `220f3daf4bed0b8247e41189a1e586d35711c967`  
**Scope:** V18 phases 00, 01, 02, exactly 161 task IDs. **Previously unassessed:** 109.  
**Method:** Joined master-roadmap verbatim task IDs and descriptions to the canonical ledger, inventoried actual repository file paths at the same SHA, suggested candidate source locations based on topic roots and text/path matches. **This is a consolidated triage, NOT a line-by-line code audit or verification.** A path match does not establish that a task is implemented. All `unassessed` ledger statuses remain unchanged.  
**Testing and deployment:** none run. No direct host/VM/database state changes.

## Quick triage by task wording, not by completion

| Likely next action | Number of previously unassessed tasks |
|---|---:|
| Design/research deliverable | 53 |
| Verification/acceptance evidence | 33 |
| Source inspection + potential implementation | 12 |
| Implementation candidate (code not yet verified) | 11 |

Interpretation: these **are not counts of missing code**. The classification reflects task phrasing; assess source call path and evidence before assigning any production state. Some tasks include both coding and final test acceptance.

## File ownership / fast audit sequence

1. **Architecture/authority first**: phase 00 source-of-truth, canonical runtime/DB, operator SAFE and host boundaries.
2. **CI/Project Forge**: phase 01 release, artifact provenance, LIFE run closure and quality validation.
3. **Human authority and inspectability**: phase 02 trusted input, authenticated device owner and stop/consent pathways.
4. **Single updater policy**: one writer for shared `ROADMAP.md` and `docs/development/v18-task-evidence.json`; workers use distinct source files and attach commit evidence for reconciliation.
5. Do not run tests, GitHub Actions or live Venus/Artemis cutovers until owner requests the final test campaign.

## Topic 0: Baseline, audit, and architectural contracts (1 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-002 | Verification/acceptance evidence | `src/sofia/memory/model.py`, `src/sofia/application/memory_review.py`, `src/sofia/cognition/matrix/model.py`, `src/sofia/cognition/model_admission.py` |

## Topic 12: Detailed integration and evaluation contracts (5 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-1204 | Source inspection + potential implementation | `src/sofia/cognition/matrix/model.py`, `src/sofia/cognition/model_admission.py`, `src/sofia/cognition/model_inventory.py`, `src/sofia/cognition/model_lifecycle.py` |
| CA-1205 | Verification/acceptance evidence | `src/sofia/application/memory_review.py`, `src/sofia/life/draft_agent.py`, `src/sofia/life/idea_agent.py`, `src/sofia/life/outreach_agent.py` |
| CA-1206 | Verification/acceptance evidence | `src/sofia/cognition/matrix/model.py`, `src/sofia/application/conversation_matrix.py`, `src/sofia/cognition/model_admission.py`, `src/sofia/cognition/model_inventory.py` |
| CA-1207 | Source inspection + potential implementation | `src/sofia/application/background_runtime.py`, `src/sofia/application/background.py`, `src/sofia/application/conversation_learning.py`, `src/sofia/application/conversation_matrix.py` |
| CA-1208 | Verification/acceptance evidence | `src/sofia/cognition/context_evidence.py`, `src/sofia/application/optional_budget.py`, `src/sofia/cognition/context.py`, `src/sofia/cognition/matrix/context_plan.py` |

## Topic 31: Architecture flaws and pre-build decisions (3 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-3107 | Design/research deliverable | `src/sofia/ops/agent_discovery.py`, `src/sofia/ops/workshop_network_stage.py`, `src/sofia/ops/workshop_network.py`, `src/sofia/safe/operator_stop_cli.py` |
| CA-3108 | Design/research deliverable | `src/sofia/ops/workshop_guest_bootstrap.py`, `src/sofia/ops/bootstrap.py`, `src/sofia/ops/fleet.py`, `src/sofia/ops/linux_bootstrap.py` |
| CA-3112 | Design/research deliverable | `src/sofia/runtime/evidence.py`, `src/sofia/interaction/avatar_world.py`, `src/sofia/verify/interaction/avatar_world_probe.py`, `docs/development/pkg-avatar-embodiment-wardrobe-objects.md` |

## Topic 33: Research protocol, human factors and design verification (11 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-3301 | Design/research deliverable | `docs/development/phase5-platform-world-acceptance.md`, `src/sofia/verify/interaction/live_behavior_probe.py`, `docs/development/authority-cleanup-report.md`, `docs/development/ca-5603-bounded-exact-original-retrieval.md` |
| CA-3303 | Design/research deliverable | `docs/development/verify-cleanup-report.md`, `test/test_verify_installed_wheel_release.py`, `src/sofia/verify/interaction/decision_expression_probe.py`, `docs/development/act-cleanup-report.md` |
| CA-3304 | Design/research deliverable | `src/sofia/verify/neuro_ablation.py`, `test/test_neuro_owner_competition_toggle.py`, `test/test_neuro_subsystem_bridge.py`, `test/test_verify_neuro_ablation_matrix.py` |
| CA-3305 | Design/research deliverable | `test/test_interaction_boundary_counterfactual_probe.py`, `test/test_ops_recovery_objectives.py`, `src/sofia/verify/interaction/boundary_counterfactual_probe.py`, `docs/development/action-cleanup-report.md` |
| CA-3306 | Design/research deliverable | `test/test_memory_reviewed_corrections.py`, `docs/development/memory-cleanup-report.md`, `docs/development/memory-deletion-retention-policy.md`, `docs/development/phase05-mobile-session-audience-binding-2026-10-10.md` |
| CA-3307 | Design/research deliverable | `docs/development/ca-1904-execution-boundary-identity.md`, `test/test_autonomous_work.py`, `test/test_cognition_v2_evidence.py`, `test/test_life_autonomous_followthrough.py` |
| CA-3308 | Design/research deliverable | `test/test_neuro_connectome_research.py`, `test/test_neuro_association_production.py`, `test/test_neuro_circuit_production_wiring.py`, `test/test_neuro_owner_competition_toggle.py` |
| CA-3309 | Design/research deliverable | `docs/development/operational-cleanup-report.md`, `docs/development/phase03-mobile-never-create-state-2026-10-10.md`, `docs/development/state-cleanup-report.md`, `test/test_operational_state.py` |
| CA-3310 | Design/research deliverable | `docs/development/companion-autonomy-contract.md`, `docs/development/companion-v0.1.md`, `test/test_act_outreach.py`, `test/test_companion_expression_runtime.py` |
| CA-3311 | Design/research deliverable | `test/test_capability_model.py`, `test/test_dev_supply_chain.py`, `src/sofia/verify/package_selection.py`, `docs/development/ca-2304-package-unique-selection.md` |
| CA-3312 | Design/research deliverable | `docs/development/ca-6804-safe-approval-no-state-resurrection.md`, `docs/development/pkg-interact-same-model-architecture-comparison.md`, `test/test_machine_inventory_lifecycle.py`, `test/test_machine_model.py` |

## Topic 40: Comparable projects, architecture reuse, and buy-versus-build (6 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-4001 | Design/research deliverable | `docs/development/pkg-interact-same-model-architecture-comparison.md`, `docs/development/ca-6608-model-promotion-transaction.md`, `docs/development/memory-cleanup-report.md`, `docs/development/memory-deletion-retention-policy.md` |
| CA-4002 | Design/research deliverable | `docs/development/ca-1904-execution-boundary-identity.md`, `docs/development/ca-5502-reviewed-history-migration.md`, `docs/development/identity-cleanup-report.md`, `docs/development/phase01-installed-wheel-test-identity-2026-10-10.md` |
| CA-4003 | Design/research deliverable | `docs/development/ca-1904-execution-boundary-identity.md`, `docs/development/ca-4105-audience-immutable-display.md`, `docs/development/ca-5307-mobile-continue-audience.md`, `docs/development/ca-5502-reviewed-history-migration.md` |
| CA-4004 | Design/research deliverable | `test/test_memory_bounded_promoted_scan.py`, `docs/development/ca-5502-reviewed-history-migration.md`, `docs/development/ca-5603-bounded-exact-original-retrieval.md`, `docs/development/memory-cleanup-report.md` |
| CA-4005 | Design/research deliverable | `docs/development/ca-1904-execution-boundary-identity.md`, `docs/development/voice-cleanup-report.md`, `src/sofia/composition/__init__.py`, `src/sofia/composition/authorization.py` |
| CA-4006 | Design/research deliverable | `docs/development/capability-cleanup-report.md`, `docs/development/fleet-tray-remote-controls-acceptance-2026-09-26.md`, `src/sofia/composition/__init__.py`, `src/sofia/composition/authorization.py` |

## Topic 45: Sofía as an OS versus an agent platform/service (4 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-4501 | Design/research deliverable | `src/sofia/ops/agent_discovery.py`, `src/sofia/run/systemd_runtime.py`, `src/sofia/ui/desktop_application.py`, `src/sofia/ui/desktop_controller.py` |
| CA-4503 | Design/research deliverable | `src/sofia/ops/fleet.py`, `src/sofia/run/runtime_service.py`, `src/sofia/run/service_admin.py`, `src/sofia/run/watchdog_service.py` |
| CA-4505 | Design/research deliverable | `src/sofia/ops/linux_bootstrap.py`, `src/sofia/ops/maintenance.py`, `src/sofia/ops/windows_bootstrap.py`, `src/sofia/ops/windows_rekey_bootstrap.py` |
| CA-4506 | Design/research deliverable | `src/sofia/ops/fleet.py`, `src/sofia/ops/platform_install.py`, `src/sofia/ui/avatar_renderer.py`, `test/test_avatar_generated_decision.py` |

## Topic 47: High-value extensions, decision gates and what not to build (6 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-4701 | Design/research deliverable | `test/test_memory_correction_semantic_integrity.py`, `test/test_memory_explicit_conversation_correction.py`, `test/test_memory_reviewed_corrections.py`, `test/test_ws2_memory_original_timestamp_prefilter.py` |
| CA-4702 | Design/research deliverable | `docs/development/ca-6807-local-destination-preflight.md`, `test/test_imported_history_local_audience_privacy.py`, `test/test_mobile_project_thread_history.py`, `src/sofia/life/__init__.py` |
| CA-4703 | Design/research deliverable | `src/sofia/life/__init__.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/draft_agent.py`, `src/sofia/life/idea_agent.py` |
| CA-4704 | Design/research deliverable | `src/sofia/life/model.py`, `test/test_machine_discovery.py`, `test/test_machine_model.py`, `test/test_state_relocation_local_preflight.py` |
| CA-4705 | Design/research deliverable | `docs/development/state-cleanup-report.md`, `docs/ops/HOMELAB_DIGITAL_TWIN.md`, `src/sofia/life/__init__.py`, `src/sofia/life/coordinator.py` |
| CA-4706 | Design/research deliverable | `src/sofia/life/model.py`, `src/sofia/verify/source_provenance.py`, `src/sofia/dev/supply_chain.py`, `test/test_dev_supply_chain.py` |

## Topic 54: OS strategy locked to Option A, Option B later (6 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-5401 | Design/research deliverable | `src/sofia/distributed/capability.py`, `src/sofia/distributed/fleet_probe.py`, `src/sofia/distributed/identity_durable.py`, `src/sofia/distributed/windows_agent_service_admin.py` |
| CA-5402 | Design/research deliverable | `src/sofia/distributed/agent_tools.py`, `src/sofia/distributed/inference_service.py`, `src/sofia/distributed/systemd_agent_service.py`, `src/sofia/distributed/windows_agent_service_admin.py` |
| CA-5404 | Design/research deliverable | `src/sofia/distributed/fleet_probe.py`, `src/sofia/distributed/remote_control.py`, `docs/development/fleet-tray-remote-controls-acceptance-2026-09-26.md`, `docs/recovery/portable-conversation-export-v1.md` |
| CA-5405 | Design/research deliverable | `src/sofia/run/active_release.py`, `src/sofia/state/sqlite_access.py`, `docs/development/v18-venus-artemis-topology-decision.md`, `docs/development/venus-artemis-runtime-topology-2026-10-11.md` |
| CA-5407 | Design/research deliverable | `src/sofia/distributed/endpoint_bound_gateway.py`, `test/test_action_authority_boundary.py`, `test/test_capability_authority_boundary.py`, `src/sofia/distributed/__init__.py` |
| CA-5408 | Design/research deliverable | `src/sofia/distributed/capability.py`, `src/sofia/distributed/systemd_agent_service.py`, `src/sofia/distributed/windows_agent_service_admin.py`, `src/sofia/distributed/windows_agent_service.py` |

## Topic 9: End-to-end test and acceptance matrix (13 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-901 | Verification/acceptance evidence | `test/test_avatar_behavior_matrix.py`, `test/test_avatar_general_preference_bridge.py`, `test/test_avatar_starter_user_preferences.py`, `test/test_avatar_wardrobe_matrix.py` |
| CA-902 | Verification/acceptance evidence | `test/test_avatar_runtime_projection.py`, `test/test_avatar_wardrobe_context_projection.py`, `test/test_conversation_workspace_projection.py`, `test/test_conversational_context_projection.py` |
| CA-903 | Verification/acceptance evidence | `src/sofia/verify/package_selection.py`, `test/test_cognition_v2_evidence.py`, `test/test_interaction_consent_followup.py`, `test/test_life_autonomous_followthrough.py` |
| CA-904 | Verification/acceptance evidence | `test/test_act_outreach.py`, `test/test_cognition_v2_evidence.py`, `test/test_cognitive_tools.py`, `test/test_distributed_agent_tools_telemetry.py` |
| CA-905 | Source inspection + potential implementation | `test/test_cognition_model_promotion_transaction.py`, `test/test_cognition_v2_fleet_machine.py`, `test/test_discord_delivery.py`, `src/sofia/verify/cognition_v2_baseline.py` |
| CA-906 | Verification/acceptance evidence | `test/test_interaction_clarify_quality_regression.py`, `test/test_response_quality_hardening.py`, `test/test_application_memory_review.py`, `test/test_capability_model.py` |
| CA-907 | Verification/acceptance evidence | `test/test_life_canonical_state_loss.py`, `test/test_memory_canonical_state_fencing.py`, `test/test_safe_operator_stop_state_loss.py`, `test/test_safe_permission_state_loss.py` |
| CA-908 | Verification/acceptance evidence | `src/sofia/verify/v18_roadmap.py`, `.github/workflows/release-candidate.yml`, `.github/workflows/release-promotion.yml`, `src/sofia/run/release_process.py` |
| CA-909 | Verification/acceptance evidence | `test/test_act_outreach.py`, `test/test_cognition_v2_evidence.py`, `test/test_distributed_windows_agent_service.py`, `test/test_embodiment_prompt_regression.py` |
| CA-910 | Verification/acceptance evidence | `test/test_ws2_memory_private_admission.py`, `test/test_ws2_memory_review_audience_mutations.py`, `test/action_support.py`, `test/interaction_lab_support.py` |
| CA-911 | Verification/acceptance evidence | `test/test_emotional_conversation_integration.py`, `test/test_neuro_conversation_integration.py`, `test/test_reflection_conversation_integration.py`, `test/test_avatar_generation_conversation.py` |
| CA-912 | Verification/acceptance evidence | `test/test_application_fleet_runtime.py`, `test/test_capability_model.py`, `test/test_cognition_model_promotion_transaction.py`, `test/test_cognition_v2_fleet_machine.py` |
| CA-913 | Verification/acceptance evidence | `test/test_autonomous_work.py`, `test/test_cognition_v2_evidence.py`, `test/test_cognitive_performance_trace.py`, `test/test_conversation_performance_trace.py` |

## Topic 22: Code-derived integration repairs and hardening (NEW v4) (13 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-2203 | Implementation candidate (code not yet verified) | `src/sofia/application/optional_budget.py`, `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py`, `src/sofia/application/autonomous_work.py` |
| CA-2206 | Implementation candidate (code not yet verified) | `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py`, `src/sofia/application/autonomous_work.py`, `src/sofia/application/background_runtime.py` |
| CA-2207 | Implementation candidate (code not yet verified) | `src/sofia/creative/world_bridge.py`, `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py`, `src/sofia/application/autonomous_work.py` |
| CA-2208 | Implementation candidate (code not yet verified) | `src/sofia/creative/world_bridge.py`, `src/sofia/neuro/workspace.py`, `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py` |
| CA-2209 | Implementation candidate (code not yet verified) | `src/sofia/application/conversation_learning.py`, `src/sofia/application/conversation_matrix.py`, `src/sofia/application/conversation_service.py`, `src/sofia/application/emotional_conversation.py` |
| CA-2210 | Verification/acceptance evidence | `src/sofia/application/optional_budget.py`, `test/test_cognitive_operation_system.py`, `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py` |
| CA-2211 | Implementation candidate (code not yet verified) | `src/sofia/application/optional_budget.py`, `src/sofia/creative/world_bridge.py`, `src/sofia/ui/avatar_renderer.py`, `docs/development/pkg-avatar-interact-bridge-code-milestone.md` |
| CA-2212 | Verification/acceptance evidence | `src/sofia/application/memory_review.py`, `src/sofia/neuro/connectome/__init__.py`, `src/sofia/neuro/connectome/ablation.py`, `src/sofia/neuro/connectome/association_store.py` |
| CA-2213 | Implementation candidate (code not yet verified) | `src/sofia/creative/capability.py`, `src/sofia/creative/world_bridge.py`, `src/sofia/know/procedural_skills.py`, `src/sofia/creative/__init__.py` |
| CA-2214 | Verification/acceptance evidence | `src/sofia/application/autonomous_work.py`, `test/test_interaction_chat_projection.py`, `test/test_life_no_placeholder_autonomous_authoring.py`, `src/sofia/application/__init__.py` |
| CA-2215 | Verification/acceptance evidence | `src/sofia/application/background_runtime.py`, `src/sofia/application/background.py`, `src/sofia/application/optional_budget.py`, `src/sofia/creative/model.py` |
| CA-2217 | Verification/acceptance evidence | `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py`, `src/sofia/application/autonomous_work.py`, `src/sofia/application/background_runtime.py` |
| CA-2218 | Verification/acceptance evidence | `src/sofia/application/conversation_learning.py`, `src/sofia/application/conversation_matrix.py`, `src/sofia/application/conversation_service.py`, `src/sofia/application/emotional_conversation.py` |

## Topic 23: CI proof, executable vertical slices and host acceptance (NEW v4) (8 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-2301 | Verification/acceptance evidence | `.github/workflows/package-tests.yml`, `src/sofia/verify/package_selection.py`, `test/test_clean_package.py`, `test/test_cognitive_action_integration.py` |
| CA-2303 | Verification/acceptance evidence | `.github/workflows/compatibility.yml`, `.github/workflows/manual-verify.yml`, `.github/workflows/matrix-tests.yml`, `test/matrix_v2_support.py` |
| CA-2305 | Source inspection + potential implementation | `test/test_avatar_generated_proposal.py`, `test/test_avatar_private_grant.py`, `test/test_avatar_starter_user_preferences.py`, `test/test_avatar_wardrobe_profile_validation.py` |
| CA-2306 | Verification/acceptance evidence | `test/test_application_acceptance.py`, `test/test_application_fleet_runtime.py`, `test/test_cognition_v2_fleet_machine.py`, `test/test_cognitive_performance_trace.py` |
| CA-2307 | Source inspection + potential implementation | `test/test_remote_mtls_transport_acceptance.py`, `.github/workflows/matrix-tests.yml`, `test/matrix_v2_support.py`, `test/test_avatar_behavior_matrix.py` |
| CA-2308 | Verification/acceptance evidence | `src/sofia/verify/cognition_v2_baseline.py`, `test/test_application_acceptance.py`, `test/test_cognition_baseline_installed_assets.py`, `test/test_cognition_v2_baseline.py` |
| CA-2309 | Verification/acceptance evidence | `test/test_memory_deletion_restore.py`, `test/test_memory_import_promotion_canonical_fencing.py`, `test/test_memory_reviewed_corrections.py`, `test/test_ws2_atomic_reviewed_memory_promotion.py` |
| CA-2310 | Verification/acceptance evidence | `src/sofia/verify/interaction/focused_probe.py`, `test/test_application_fleet_runtime.py`, `test/test_cognition_v2_fleet_machine.py`, `test/test_distributed_fleet_probe.py` |

## Topic 30: OpenCode push verification and actual missing release/Fleet wiring (6 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-3002 | Verification/acceptance evidence | `src/sofia/ops/sofia_guest_readiness.py`, `src/sofia/ops/windows_bootstrap.py`, `src/sofia/ops/windows_rekey_bootstrap.py`, `src/sofia/ops/workshop_guest_bootstrap.py` |
| CA-3007 | Verification/acceptance evidence | `.github/workflows/manual-verify.yml`, `.github/workflows/matrix-tests.yml`, `.github/workflows/package-tests.yml`, `.github/workflows/release-candidate.yml` |
| CA-3008 | Source inspection + potential implementation | `docs/development/phase03-canonical-state-no-resurrection-2026-10-11.md`, `src/sofia/ops/local_telemetry.py`, `src/sofia/ops/repair_plan.py`, `src/sofia/ops/state_mobility.py` |
| CA-3009 | Design/research deliverable | `Setup-SofiaFleetArtemis.ps1`, `src/sofia/ops/discovery_canary.py`, `src/sofia/ops/fleet.py`, `src/sofia/ops/migration_grants.py` |
| CA-3013 | Verification/acceptance evidence | `src/sofia/creative/service.py`, `src/sofia/ops/agent_discovery.py`, `src/sofia/ops/discovery_canary.py`, `src/sofia/ops/discovery.py` |
| CA-3016 | Source inspection + potential implementation | `src/sofia/ops/discovery_canary.py`, `src/sofia/ops/windows_bootstrap.py`, `src/sofia/ops/windows_rekey_bootstrap.py`, `src/sofia/verify/interaction/decision_expression_probe.py` |

## Topic 46: Acceptance architecture for all six companion autonomy pillars (8 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-4601 | Design/research deliverable | `test/test_memory_provenance_store.py`, `test/test_memory_provenance.py`, `test/test_memory_reviewed_corrections.py`, `src/sofia/verify/cognition_v2_baseline.py` |
| CA-4602 | Design/research deliverable | `test/test_model_evaluation_harness.py`, `test/test_capability_model.py`, `test/test_cognition_model_promotion_transaction.py`, `test/test_cognition_v2_evidence.py` |
| CA-4603 | Design/research deliverable | `test/test_cognition_model_promotion_transaction.py`, `src/sofia/verify/source_provenance.py`, `test/test_application_fleet_runtime.py`, `test/test_capability_model.py` |
| CA-4604 | Design/research deliverable | `test/action_support.py`, `test/interaction_lab_support.py`, `test/test_action_authority_boundary.py`, `test/test_action.py` |
| CA-4605 | Design/research deliverable | `src/sofia/verify/interaction/avatar_world_probe.py`, `test/test_avatar_authoring.py`, `test/test_avatar_behavior_matrix.py`, `test/test_avatar_clothing_action.py` |
| CA-4606 | Design/research deliverable | `src/sofia/verify/neuro_ablation.py`, `test/test_capability_model.py`, `test/test_cognition_model_promotion_transaction.py`, `test/test_environment_model.py` |
| CA-4607 | Design/research deliverable | `test/test_avatar_generated_proposal.py`, `test/test_capability_proposal.py`, `test/test_cognition_v2_evidence.py`, `test/test_conversation_fts_authorized_source.py` |
| CA-4608 | Design/research deliverable | `test/test_capability_composition_scope.py`, `test/test_avatar_private_grant.py`, `test/test_avatar_wardrobe_environment_context.py`, `test/test_avatar_wardrobe_environment_profiles.py` |

## Topic 11: Inspectability, user controls and feedback (3 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-1103 | Implementation candidate (code not yet verified) | `src/sofia/neuro/__init__.py`, `src/sofia/neuro/adapters.py`, `src/sofia/neuro/connectome/__init__.py`, `src/sofia/neuro/connectome/ablation.py` |
| CA-1104 | Implementation candidate (code not yet verified) | `src/sofia/neuro/connectome/association_store.py`, `src/sofia/neuro/connectome/__init__.py`, `src/sofia/neuro/connectome/ablation.py`, `src/sofia/neuro/connectome/associative.py` |
| CA-1106 | Implementation candidate (code not yet verified) | `src/sofia/neuro/__init__.py`, `src/sofia/neuro/adapters.py`, `src/sofia/neuro/connectome/__init__.py`, `src/sofia/neuro/connectome/ablation.py` |

## Topic 19: Autonomy-specific security and resilience (NEW) (4 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-1901 | Verification/acceptance evidence | `src/sofia/application/idle_reflection.py`, `src/sofia/ops/model.py`, `src/sofia/interaction/world_model.py`, `test/test_virtual_world_editor.py` |
| CA-1902 | Implementation candidate (code not yet verified) | `src/sofia/ops/workshop_policy.py`, `src/sofia/safe/capability_policy_cli.py`, `src/sofia/safe/capability_policy.py`, `src/sofia/application/__init__.py` |
| CA-1903 | Source inspection + potential implementation | `src/sofia/safe/permissions_cli.py`, `src/sofia/safe/permissions.py`, `src/sofia/application/__init__.py`, `src/sofia/application/act_service.py` |
| CA-1906 | Source inspection + potential implementation | `src/sofia/application/memory_review.py`, `src/sofia/ops/model.py`, `src/sofia/safe/secret_store.py`, `src/sofia/application/__init__.py` |

## Topic 27: Scientific exploration, adversarial acceptance and stopping rules (6 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-2701 | Design/research deliverable | `src/sofia/verify/interaction/architecture_compare.py`, `src/sofia/verify/neuro_ablation.py`, `test/test_distributed_inference_control.py`, `test/test_distributed_remote_control.py` |
| CA-2702 | Verification/acceptance evidence | `src/sofia/verify/neuro_ablation.py`, `test/test_neuro_association_production.py`, `test/test_neuro_owner_competition_toggle.py`, `test/test_verify_neuro_ablation_matrix.py` |
| CA-2703 | Design/research deliverable | `src/sofia/neuro/consciousness_research.py`, `test/test_discord_operator.py`, `test/test_life_operator_diagnostics.py`, `test/test_neuro_consciousness_registry_production.py` |
| CA-2704 | Source inspection + potential implementation | `src/sofia/neuro/sensory.py`, `test/test_discord_binding.py`, `test/test_discord_bridge.py`, `test/test_discord_delivery.py` |
| CA-2705 | Source inspection + potential implementation | `test/test_memory_cognition_projection.py`, `test/test_memory_final_projection_scope.py`, `test/test_memory_import_evidence_canonical_fencing.py`, `test/test_memory_retrieval_projection.py` |
| CA-2706 | Source inspection + potential implementation | `test/test_tools_completion_acceptance.py`, `test/test_application_acceptance.py`, `test/test_application_fleet_runtime.py`, `test/test_avatar_runtime_projection.py` |

## Topic 65: Autonomy charter and owner-legible operation (6 previously unassessed)

| ID | Source action hypothesis | Code locations to inspect (candidate paths, not proof) |
|---|---|---|
| CA-6501 | Design/research deliverable | `src/sofia/safe/permission_capability.py`, `src/sofia/safe/permissions_cli.py`, `src/sofia/safe/permissions.py`, `src/sofia/composition/__init__.py` |
| CA-6503 | Design/research deliverable | `src/sofia/safe/permission_capability.py`, `src/sofia/safe/permissions_cli.py`, `src/sofia/safe/permissions.py`, `src/sofia/interaction/decision_reason_audit.py` |
| CA-6504 | Design/research deliverable | `src/sofia/ops/maintenance.py`, `src/sofia/ops/model.py`, `src/sofia/filesystem/changes.py`, `test/test_discord_single_user_gate.py` |
| CA-6505 | Design/research deliverable | `src/sofia/ops/capability.py`, `src/sofia/safe/capability_policy_cli.py`, `src/sofia/safe/capability_policy.py`, `src/sofia/safe/permission_capability.py` |
| CA-6506 | Design/research deliverable | `src/sofia/ops/model.py`, `src/sofia/avatar/generated_decision.py`, `test/test_avatar_generated_decision.py`, `src/sofia/composition/__init__.py` |
| CA-6508 | Design/research deliverable | `src/sofia/ops/maintenance.py`, `docs/development/companion-autonomy-contract.md`, `docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md`, `test/test_operational_awareness_acceptance.py` |

## Graduation rules

- Move `unassessed` to `partial_wiring` only after tracing a concrete source caller and a missing production sink or behavior.
- Move to `code_present_unverified` only with full source paths and independent deterministic contract review, plus a deferred test matrix.
- Never mark `accepted` until actual focused, full CI, and required Windows/Fleet live proof are recorded.
- Architectural or science tasks may legitimately produce a decision packet or benchmark protocol, not a Python implementation.
