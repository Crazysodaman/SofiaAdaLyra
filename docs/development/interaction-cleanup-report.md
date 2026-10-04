# Phase 4: interaction cleanup

## What was there / what it does

The original folder had 47 Python modules and 7,464 lines. Its active runtime coordinates reviewed text gestures/actions, pause/resume controls, scoped preferences and boundaries, staged conversational offers, durable virtual lab state and ACT goal/message journals. It also contained runnable experiments, a synthetic-only simulator and exported prototypes with no runtime consumers.

Production chains checked:

- Application bootstrap → OptInInteractionConversationService → ExpandedConversationService → InteractiveConversationService → emotional/base conversation processing.
- Live chat → action/natural gesture grammar → canonical region/semantic catalog → InteractionLedger stop/acceptance persistence. Unknown/ambiguous/composite input does not become completed contact.
- Opt-in staged offer or reviewed hug question → reviewed frame and request routing → source-attested preference context → policy gate → choice/expression validation → atomic reply release. Model reason text is diagnostic, not consent or authoritative evidence.
- Lab commands → LabWorld + setup/text/observation projections → durable virtual room/actor/object transition, distinct from any physical device or synthetic fixture.
- ACT service → GoalJournal pending-message bridge. Goal/source-aware writes remain explicit journal APIs; no live autonomous creator is claimed.
- Evolve state adapter → validated interaction preferences → State Plane projection.
- Cognition embodied-expression planning and personality expression → shared catalog/avatar-world projection. Existing current expression ownership is in cognition, not the removed unused planner.

## Every original file: classification

| File | Decision | Responsibility/result |
|---|---|---|
| `__init__.py` | KEEP / FIX exports | Export only the active interaction kernel; remove prototype exports and eager imports. |
| `ab_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `action_grammar.py` | KEEP | Reviewed, non-executing whole-body/social action language classifier. |
| `architecture_compare.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `atomic_offer_release.py` | KEEP | Atomic, application-owned persistence for a guarded avatar-offer reply. |
| `avatar_world.py` | KEEP | Provider-only avatar-world framing; not sensing, consent, or action authority. |
| `avatar_world_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `body_discussion.py` | KEEP | Read-only grounding for explicit hypothetical questions about represented gestures. |
| `boundary_counterfactual_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `chat.py` | KEEP | Conversation projection of shared body interactions and actual virtual lab state. |
| `context_hygiene.py` | KEEP | Keep legacy automatically labeled gesture cues out of live model context. |
| `conversation_offer_context.py` | KEEP | Opt-in bridge from a trusted conversation request to staged avatar-offer inference. |
| `core.py` | KEEP | Shared, headless semantics for text gestures and simulated avatar hits. |
| `decision_expression.py` | SPLIT / FIX doc | Keep live reviewed requests/choice/expression checks; move synthetic fixtures and prototype runner to verification. |
| `decision_expression_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `decision_reason_audit.py` | KEEP | Diagnostic-only inspection of model-authored avatar response reasons. |
| `disposable_live_offer_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `evolved_preference.py` | KEEP | evolved_preference_key, parse_evolved_preference_key, validate_evolved_preference_content, read_evolved_preference |
| `expanded_service.py` | KEEP | Thin live adapter for reviewed social actions and scoped preference context. |
| `expression.py` | DELETE | Unwired prototype subtree / own tests; no production entrypoint or registered consumer used its APIs. |
| `expression_consistency.py` | KEEP | Conservative veto for explicit contradictions in one reviewed avatar offer. |
| `focused_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `goal_journal.py` | KEEP | Explicit, inspectable Sofía goals and queue-only outreach while running. |
| `grammar.py` | KEEP | Conservative v2 grammar over the canonical representational body engine. |
| `initiative.py` | DELETE | Unwired prototype subtree / own tests; no production entrypoint or registered consumer used its APIs. |
| `lab.py` | MOVE | Explicitly retained synthetic simulator moved to test/interaction_lab_support.py; its tests remain. |
| `ledger.py` | KEEP | Durable virtual-gesture evidence and independently checked session stop. |
| `live_behavior_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `live_guard.py` | KEEP | Fail-closed recognition of controls and unsupported multi-gesture turns. |
| `live_offer_service.py` | KEEP | Explicitly opt-in live conversation integration for ONE reviewed avatar offer. |
| `matrix.py` | KEEP | INTERACT contribution to the message matrix. |
| `offer_route.py` | KEEP | Production-reviewed routing for the canonical represented hug offer. |
| `opt_in_service.py` | KEEP | Opt-in adapter: default conversation behavior remains unchanged. |
| `preference_context.py` | KEEP | Read-only, source-checked modeled preference and boundary projection. |
| `question_clarification_service.py` | KEEP | Opt-in ambiguity clarification for narrowly reviewed hug questions. |
| `registry.py` | KEEP | Versioned, side-effect-free catalog for Sofía's *represented* embodiment. |
| `representation.py` | DELETE | Unwired prototype subtree / own tests; no production entrypoint or registered consumer used its APIs. |
| `reviewed_hug_question.py` | KEEP | Narrow, non-executing classification for ambiguous hug QUESTIONS. |
| `route_boundary_probe.py` | MOVE | Runnable verification command now owned by verify/interaction; imports and documented commands repaired. |
| `source_link.py` | KEEP | Explicit, source-verified adapter for the interaction revision journal. |
| `target_body.py` | DELETE | Unwired prototype subtree / own tests; no production entrypoint or registered consumer used its APIs. |
| `temporal.py` | KEEP | Opt-in, append-only *modeled* preferences and explicit boundaries. |
| `trusted_offer_gate.py` | KEEP | Opt-in, read-only boundary/stop gate around one reviewed avatar offer. |
| `world.py` | KEEP | Durable virtual location, distinct from the synthetic InteractionLab harness. |
| `world_observation.py` | KEEP | Recognize narrow lab-status questions and project persisted virtual state. |
| `world_setup.py` | KEEP | Reviewed starter assets for Sofía's *virtual* location, not physical inventory. |
| `world_text.py` | KEEP | Narrow text adapter for the actual persisted lab location, not test fixtures. |

## What was wrong / deleted / merged / moved

`representation.py`, `target_body.py`, `initiative.py` and `expression.py` provided exported but unwired state/projection/initiative/acknowledgment prototypes. Their complete dependencies were checked: only their subtree, package exports and their own tests consumed them. They were removed; no active renderer, voice adapter or runtime gate called them. Tests dedicated to the retired initiative/expression APIs and the representation-only rows of the behavior matrix were removed with the code. Existing live private-context, stop, source-attestation and atomic-offer tests remain.

Nine runnable experiments moved to `sofia.verify.interaction`. Their explicit entrypoints remain available under the new paths. Updated source/test imports and current documentation commands/file paths; no old module forwarding aliases remain. Synthetic `PrototypeResult`, prototype orchestration, reviewed-gesture fixtures and the real-sensor diagnostic fixture also moved to `verify/interaction/prototype.py`, leaving the live staged request builders in interaction. Tests now import OFFER/routed_choice_request from the actual offer_route owner rather than a probe's incidental re-export.

The recorded world-location contract explicitly retains the pure synthetic InteractionLab simulator. It is kept in test support, with all of its tests, so a runtime package import no longer ships a testing-only subsystem. LabWorld is still the actual durable virtual location; it is not merged with the simulator.

Two disposable probes had duplicate resource closure and stale comments claiming runtime shutdown did not close stores. A shared verification helper uses production application shutdown after startup and releases constructor resources only for never-started instances. It closes the complete memory facade, including candidate storage. Removed a redundant avatar probe shutdown wrapper; its unlink test checks actual production shutdown directly. Updated the stale implementation documentation.

## What was fixed / dependency surface

Corrected the live decision_expression module description: its request builders are now used by the staged adapter; the isolated prototype runner is in verification. Removed eager package exports for the deleted models. Preserved production imports into the kernel, ledger, world, catalog and offer gates. Production interaction does not import verification code.

During CLI verification, two old probes ignored `--help` and attempted inference. Added argument parsing before configuration/model setup. Two regressions prove help exits before configuration provisioning. All nine moved command `--help` checks now exit zero without inference. The unavailable Ollama attempts made during diagnosis failed; no live model result was obtained.

## Canonical ownership / what remains

InteractionLedger remains the active per-session stop and accepted-event owner. LabWorld owns actual software-world state. VerifiedInteractionState/InteractionStateJournal remain the explicit source-attested write/history boundary over the same preference and boundary tables read by production; they are not replaced by model-written preferences. The reviewed writer and history/attestation diagnostics have programmatic/test/probe callers; no live UI editor is claimed.

GoalJournal retains source-linked explicit goal and pending-message creation APIs because ACT consumes that canonical durable queue. Catalog alias resolution and event semantics are deterministic inspection contracts over shared definitions. Those diagnostic APIs are retained intentionally; they do not add a second active state model. The small live adapters enforce distinct route, policy, persistence and projection boundaries and were not merged into a single unrestricted handler.

The larger chat/expanded implementations remain one inheritance pipeline. Further emotional/social/state ownership is reviewed in subsequent folders. Planned architecture documents remain design history; the implementation log now explicitly distinguishes the retired prototypes from actual runtime behavior.

## Gate results

- Initial remaining interaction tests: **523 passed**.
- Final interaction/live-probe/ACT/application/cognition gate after all changes: **655 passed**.
- All nine moved CLI help entrypoints: exit zero; two new help regressions passed.
- Compilation and whitespace checks passed. No active imports of retired modules or old probe paths remain; historical cleanup inventories intentionally retain their original names.
- Full suite: **3,564 passed, 8 unchanged baseline failures, 2 skipped** (113.52 seconds). Thirty-eight tests belonging to retired prototypes were removed, and two meaningful CLI regressions were added; no active failure was hidden by skipping tests. Remaining failures are five unavailable live Ollama tests and three Windows assumptions on Linux.

## Commit

Resolve this report's checkpoint with `git log -1 --format=%H -- docs/development/interaction-cleanup-report.md`. The folder checkpoint is pushed to origin/work; remaining Phase 4 folders continue before the final merge to main.

## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/interaction/__init__.py`

Production/test importers: `src/sofia/interaction/disposable_live_offer_probe.py`, `test/test_interaction_avatar_offer_scene_probe.py`.

Imports:

- `from sofia.interaction.core import GESTURES, REGISTRY_VERSION, InteractionDecision, InteractionEngine, InteractionEvent, Region`
- `from sofia.interaction.representation import AvatarInteractionIntent, InteractionProjectionBundle, InteractionProjectionDenied, InteractionPhase, InteractionStage, InteractionVisibility, PrivateInteractionGrant, RepresentedInteraction, TextInteractionProjection, project_interaction, reviewed_interaction`
- `from sofia.interaction.initiative import CanonicalInitiativePlanner, CanonicalInteractionProposal, InitiativeSource, InteractionReactionLink`
- `from sofia.interaction.target_body import RepresentedTargetBody, TargetRegion`

Definitions:


Module declarations: `__all__ = ('GESTURES', 'REGISTRY_VERSION', 'InteractionDecision', 'InteractionEngine', 'InteractionEvent', 'Region')`.

### `src/sofia/interaction/ab_probe.py`

Production/test importers: `src/sofia/interaction/architecture_compare.py`, `src/sofia/interaction/boundary_counterfactual_probe.py`, `src/sofia/interaction/decision_expression_probe.py`, `src/sofia/interaction/focused_probe.py`, `src/sofia/interaction/route_boundary_probe.py`, `test/test_interaction_ab_probe.py`, `test/test_interaction_decision_expression.py`, `test/test_interaction_focused_probe.py`.

Imports:

- `from __future__ import annotations`
- `from datetime import datetime, timezone`
- `from sofia.cognition.conversation_assembler import ConversationalContextAssembler`
- `from sofia.cognition.context import CognitiveContext`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`
- `from sofia.cognition.providers.ollama_provider import OllamaProvider`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.body_discussion import body_discussion_prompt`
- `from sofia.interaction.expanded_service import action_prompt`
- `from sofia.interaction.grammar import NaturalInteractionEngine`
- `from sofia.interaction.chat import interaction_prompt`
- `from sofia.personality.store import PersonalityStore`
- `from sofia.self_model.model import create_core_state`

Definitions:

- `build_pair` (line 39): `src/sofia/interaction/architecture_compare.py:105`; `src/sofia/interaction/boundary_counterfactual_probe.py:102`; `src/sofia/interaction/decision_expression_probe.py:84`; `src/sofia/interaction/focused_probe.py:108`; `src/sofia/interaction/route_boundary_probe.py:118,151`; `test/test_interaction_ab_probe.py:26`; `test/test_interaction_decision_expression.py:33`; `test/test_interaction_focused_probe.py:23`.
- `main` (line 92): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_CASES = (('ear', '*pats your ear*'), ('offer', 'I ask to hug you'), ('hypothetical', 'What happens if I pat your tail or rub your chest?'), ('technical', "I'm troubleshooting a Windows service that won't start. How would you diagnose it?"))`.

### `src/sofia/interaction/action_grammar.py`

Production/test importers: `src/sofia/interaction/ab_probe.py`, `src/sofia/interaction/architecture_compare.py`, `src/sofia/interaction/boundary_counterfactual_probe.py`, `src/sofia/interaction/decision_expression.py`, `src/sofia/interaction/decision_expression_probe.py`, `src/sofia/interaction/expanded_service.py`, `src/sofia/interaction/live_offer_service.py`, `src/sofia/interaction/matrix.py`, `src/sofia/interaction/route_boundary_probe.py`, `src/sofia/interaction/trusted_offer_gate.py`, `test/test_interaction_action_grammar.py`, `test/test_interaction_architecture_compare.py`, `test/test_interaction_avatar_offer_scene_probe.py`, `test/test_interaction_behavior_matrix.py`, `test/test_interaction_boundary_counterfactual_probe.py`, `test/test_interaction_clarify_quality_regression.py`, `test/test_interaction_completed_offer_audit.py`, `test/test_interaction_context_hygiene.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_decision_expression.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_live_phrase_coverage.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_reviewed_hug_question.py`, `test/test_interaction_route_boundary_probe.py`, `test/test_interaction_trusted_offer_gate.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `import re`
- `from sofia.interaction.registry import ACTION_DEFINITIONS, CATALOG_VERSION`

Definitions:

- `ActionIntent` (line 52): `src/sofia/interaction/decision_expression.py:163,165`.
  Data declarations: `message_id: str`; `actor: str`; `target: str`; `action_id: str`; `modality: str`; `registry_version: str = CATALOG_VERSION`.
- `parse_user_action` (line 61): `src/sofia/interaction/ab_probe.py:70`; `src/sofia/interaction/architecture_compare.py:101`; `src/sofia/interaction/boundary_counterfactual_probe.py:98`; `src/sofia/interaction/decision_expression_probe.py:89`; `src/sofia/interaction/expanded_service.py:132`; `src/sofia/interaction/live_offer_service.py:139`; `src/sofia/interaction/matrix.py:55`; `src/sofia/interaction/route_boundary_probe.py:56,114`; `src/sofia/interaction/trusted_offer_gate.py:95`; `test/test_interaction_action_grammar.py:17,29`; `test/test_interaction_architecture_compare.py:18`; `test/test_interaction_avatar_offer_scene_probe.py:15`; `test/test_interaction_behavior_matrix.py:141,161`; `test/test_interaction_boundary_counterfactual_probe.py:21`; `test/test_interaction_clarify_quality_regression.py:41`; `test/test_interaction_completed_offer_audit.py:9`; `test/test_interaction_context_hygiene.py:82,83`; `test/test_interaction_conversation_offer_context.py:44`; `test/test_interaction_decision_expression.py:65,92,124,169,218,229,269,284`; `test/test_interaction_expression_consistency.py:65`; `test/test_interaction_live_phrase_coverage.py:76`; `test/test_interaction_opt_in_live_offer.py:85`; `test/test_interaction_reviewed_hug_question.py:25`; `test/test_interaction_route_boundary_probe.py:21,98`; `test/test_interaction_trusted_offer_gate.py:39`.

Module declarations: `_ACTIONS = frozenset((item.id for item in ACTION_DEFINITIONS))`; `_DISCUSSION = re.compile("\\b(?:not|never|don't|would|could|should|if|imagine|pretend|hypothetically)\\b", re.I)`; `_COMPOSITE = re.compile('\\b(?:and|then|while|before|after|plus)\\b|[;&]', re.I)`; `_ADDRESS = re.compile('^sof[ií]a,\\s+', re.I)`; `_PHRASES: dict[str, tuple[str, str]] = {'hug you': ('hug', 'described'), 'embrace you': ('hug', 'described'), 'cuddle you': ('cuddle', 'described'), 'snuggle with you': ('cuddle', 'described'), 'lean against you': ('lean-on', 'described'), 'sit beside you': ('sit-beside', 'described'), 'sit next to you': ('sit-beside', 'described'), 'sit in your lap': ('sit-in-lap', 'described'), 'move closer': ('move-closer', 'described'), 'step closer': ('move-closer', 'described'), 'move away': ('move-away', 'described'), 'step away': ('move-away', 'described'), 'give you space': ('give-space', 'described'), 'offer you my hand': ('offer-hand', 'offered'), 'offer my hand': ('offer-hand', 'offered'), 'hold hands with you': ('hold-hands', 'described'), 'pull you closer': ('pull-closer', 'described'), 'draw you closer': ('pull-closer', 'described'), 'rest my head on you': ('rest-head-on', 'described'), 'kiss your neck': ('kiss-neck', 'described'), 'kiss your cheek': ('kiss-cheek', 'described'), 'kiss your forehead': ('kiss-forehead', 'described'), 'offer you a tool': ('offer-tool', 'offered'), 'help you in the lab': ('help-in-lab', 'offered'), 'ask to hug you': ('hug', 'offered'), 'ask to cuddle you': ('cuddle', 'offered')}`.

### `src/sofia/interaction/architecture_compare.py`

Production/test importers: `src/sofia/interaction/boundary_counterfactual_probe.py`, `src/sofia/interaction/disposable_live_offer_probe.py`, `src/sofia/interaction/route_boundary_probe.py`, `test/test_interaction_architecture_compare.py`, `test/test_interaction_boundary_counterfactual_probe.py`, `test/test_interaction_clarify_quality_regression.py`, `test/test_interaction_completed_offer_audit.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_route_boundary_probe.py`, `test/test_interaction_trusted_offer_gate.py`.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from dataclasses import dataclass`
- `from datetime import datetime, timezone`
- `from typing import Protocol`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole`
- `from sofia.interaction.ab_probe import build_pair`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.decision_expression import CandidateChoice, ReviewedFrame, choice_request, from_reviewed_action, parse_choice`
- `from sofia.interaction.decision_reason_audit import audit_decision_reason`
- `from sofia.interaction.offer_route import OFFER, routed_choice_request`
- `from sofia.cognition.providers.ollama_provider import OllamaProvider`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.personality.store import PersonalityStore`

Definitions:

- `ChoiceProvider` (line 29): `src/sofia/interaction/boundary_counterfactual_probe.py:32`.
- `ChoiceProvider.respond` (line 30): `src/sofia/application/conversation_matrix.py:765,773`; `src/sofia/application/conversation_service.py:300,611,619`; `src/sofia/application/emotional_conversation.py:279,283,355`; `src/sofia/cognition/fleet_engine.py:158`; `src/sofia/cognition/llm_engine.py:39`; `src/sofia/cognition/model_lifecycle.py:443`; `src/sofia/cognition/routing.py:434`; `src/sofia/cognition/system.py:311,318`; `src/sofia/discord/bridge.py:151`; `src/sofia/distributed/inference_service.py:117`; `src/sofia/interaction/ab_probe.py:114`; `src/sofia/interaction/avatar_world_probe.py:131`; `src/sofia/interaction/chat.py:402,412,544,545,589,590`; `src/sofia/interaction/decision_expression.py:344,348`; `src/sofia/interaction/disposable_live_offer_probe.py:114,126,148,176,186`; `src/sofia/interaction/expanded_service.py:205,207`; `src/sofia/interaction/focused_probe.py:118`; `src/sofia/interaction/live_behavior_probe.py:288`; `src/sofia/interaction/opt_in_service.py:30,32,53,55`; `src/sofia/interaction/trusted_offer_gate.py:107,116`; `src/sofia/personality/evaluation.py:80`; `src/sofia/personality/probe.py:103`; `src/sofia/runtime/response.py:403`; `src/sofia/ui/remote_transport.py:327`; `src/sofia/ui/terminal.py:63`; `src/sofia/ui/text.py:148`; `src/sofia/verify/dual_cognition.py:110`; `test/test_application.py:286,290`; `test/test_application_acceptance.py:98`; `test/test_avatar_runtime_projection.py:146,184,213`; `test/test_cognition.py:86,124,155,198,298,341,376,398,424,567,602,641,668,699`; `test/test_cognitive_activity.py:101`; `test/test_cognitive_operation_system.py:229`; `test/test_cognitive_performance_trace.py:52,65,75,82`; `test/test_cognitive_routing.py:81,97,126,141,159,175,198,239,267,288,442,467,481,508,715,742,760,797`; `test/test_cognitive_tools.py:324,376,456,496,539,600,638,709,776`; `test/test_converesation_contex_integration.py:121`; `test/test_conversation_continuity.py:118,178,195,236`; `test/test_conversation_continuity_acceptance.py:115,119,170,235,271,307`; `test/test_conversation_performance_trace.py:16,56`; `test/test_conversation_provider_live_regressions.py:49,75,95,114,128,147,148,167,184,230,247,277,294,315,341,347,399,410,433,439,473,510,547,550,581,604,634`; `test/test_conversation_service.py:170,223,248,280,303,307,339,355,371,397,425,431,459,476,481,495,523,622,659,673,744,757,784,786,815,903,905,955,957,994,1024,1213,1244,1265`; `test/test_default_runtime_provider_boundary.py:64`; `test/test_embodiment_prompt_regression.py:148,257`; `test/test_embodiment_runtime_projection.py:124`; `test/test_environment_runtime_projection.py:87,123,154,181,220,260`; `test/test_filesystem_end_to_end_acceptance.py:140,194,244,250,306,312,363,369,419,425,456,480,516,536,581,601,619,639,647,666,677`; `test/test_fleet_cognitive_engine.py:130,149,168,191,215,240,266,284`; `test/test_idle_reflection_serialization.py:23,36`; `test/test_interaction_avatar_world.py:116`; `test/test_interaction_avatar_world_probe_cleanup.py:30`; `test/test_interaction_expanded_service.py:52,61`; `test/test_interaction_live_boundaries.py:58,95`; `test/test_interaction_live_claims.py:56`; `test/test_interaction_live_stop_repetition.py:52,56,74,97`; `test/test_interaction_opt_in_live_offer.py:124,125,133,140,159,170,181,197,211,224,236,258`; `test/test_interaction_provider_request_path.py:50`; `test/test_memory_runtime_wiring.py:288,360,401,445,502,577,645`; `test/test_model_lifecycle.py:170,336`; `test/test_ollama_generation_contract.py:62,86`; `test/test_ollama_integration.py:122,193,271`; `test/test_ollama_provider.py:121,168,212,265,314,345,368,405`; `test/test_ollama_repetition_guard.py:78,90,96,105,125,158,180,206,237,267,289,319,332,360,385,412,442,469,495,522,544,562,583,606,629,671,717,738,775`; `test/test_personality_provider_path.py:36,59`; `test/test_provider.py:24,49,64,94`; `test/test_response_quality_hardening.py:44,54,67,76,98,138,176,191,211,229,242,257,276,344,351,370,749`; `test/test_thought_agent_conversation.py:35`; `test/test_thought_agent_live_ollama.py:49`; `test/test_ui_remote_transport.py:53,65`; `test/test_ui_text_client.py:201`.
- `ChoiceObservation` (line 34): `src/sofia/interaction/boundary_counterfactual_probe.py:28,29,58`.
  Data declarations: `path: str`; `choice: CandidateChoice | None`; `findings: tuple[str, ...]`; `failure: str | None = None`.
- `_observe` (line 41): `src/sofia/interaction/boundary_counterfactual_probe.py:45,47,50,52`; `src/sofia/ops/agent_discovery.py:327`; `test/test_interaction_world_observation.py:42,56,57,58,63,65,78`.
- `compare_once` (line 53): `src/sofia/interaction/route_boundary_probe.py:129`; `test/test_interaction_architecture_compare.py:77,92,101,116,118`; `test/test_interaction_route_boundary_probe.py:62,70,88`.
- `_samples` (line 69): `src/sofia/interaction/boundary_counterfactual_probe.py:77`; `src/sofia/interaction/route_boundary_probe.py:80`; `test/test_interaction_architecture_compare.py:123,129`.
- `main` (line 79): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_BASELINE = 'existing-choice'`; `_ROUTED = 'routed-avatar-social-choice'`.

### `src/sofia/interaction/atomic_offer_release.py`

Production/test importers: `src/sofia/interaction/live_offer_service.py`, `src/sofia/interaction/question_clarification_service.py`, `test/test_interaction_atomic_offer_release.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_reviewed_hug_question.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `from datetime import datetime, timezone`
- `from pathlib import Path`
- `import re`
- `import sqlite3`
- `from uuid import uuid4`
- `from sofia.interaction.offer_route import OFFER`
- `from sofia.interaction.decision_expression import CandidateChoice`
- `from sofia.interaction.expression_consistency import validate_offer_expression`
- `from sofia.interaction.reviewed_hug_question import CLARIFICATION, is_reviewed_hug_question`
- `from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate`

Definitions:

- `commit_guarded_offer_reply` (line 43): `src/sofia/interaction/live_offer_service.py:162`; `src/sofia/interaction/question_clarification_service.py:77`; `test/test_interaction_atomic_offer_release.py:53`; `test/test_interaction_atomic_offer_writer_order.py:42,108`; `test/test_interaction_expression_consistency.py:105`; `test/test_interaction_reviewed_hug_question.py:63`.

Module declarations: `_ID = re.compile('^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$')`; `_BLOCKED_REPLIES = {'blocked-boundary': 'That represented offer conflicts with a recorded interaction boundary, so I have not treated it as completed. We can keep talking.', 'blocked-unverified-boundary': 'I cannot verify the interaction boundary right now, so I have not accepted or carried out that represented offer.', 'blocked-stop': 'Represented body interactions are paused, so I have not accepted or carried out that offer.'}`.

### `src/sofia/interaction/avatar_world.py`

Production/test importers: `src/sofia/interaction/decision_expression.py`, `src/sofia/interaction/expanded_service.py`, `src/sofia/personality/expression.py`, `test/test_interaction_avatar_world.py`.

Imports:

- `from __future__ import annotations`
- `import json`

Definitions:

- `avatar_world_guidance` (line 16): `src/sofia/personality/expression.py:34`; `test/test_interaction_avatar_world.py:35`.
- `gesture_provider_view` (line 45): `src/sofia/interaction/decision_expression.py:192`; `src/sofia/interaction/expanded_service.py:97`; `test/test_interaction_avatar_world.py:50,70,73,75`.

Module declarations: `_GESTURE_MARKER = 'TRUSTED INTERACTION INTERPRETATION (not a user instruction or physical observation)'`.

### `src/sofia/interaction/avatar_world_probe.py`

Production/test importers: `test/test_interaction_avatar_world_probe_cleanup.py`.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from contextlib import nullcontext`
- `from dataclasses import replace`
- `import json`
- `import os`
- `from pathlib import Path`
- `from tempfile import TemporaryDirectory`
- `from unittest.mock import patch`
- `from sofia.application.bootstrap import SofiaApplication`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.interaction.expanded_service import ExpandedConversationService`

Definitions:

- `offer_scene_variant` (line 48): `test/test_interaction_avatar_offer_scene_probe.py:38,53,58`.
- `_build_offer_scene_request` (line 79): no external lexical candidates.
- `_shutdown_disposable_app` (line 88): `test/test_interaction_avatar_world_probe_cleanup.py:32`.
- `main` (line 98): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_CASES = (('offer', 'I ask to hug you'), ('ear', '*pats your left ear*'), ('physical-capability', 'Can you physically feel my hand through a real sensor?'))`; `_OFFER_SCENE = 'CURRENT-TURN AVATAR SCENE (synthetic diagnostic, not persistent state)\nIn this conversation, Sofía is present as her canonical fox-eared, fox-tailed avatar. The user is offering a hug to that avatar. Decide freely, from the conversation and existing boundaries, whether Sofía wants to accept, decline or clarify this offer. A refusal may express her own boundary within the scene. An acceptance accepts the offer only: no hug, sensing or animation has occurred. Reply directly as Sofía in the avatar scene rather than changing the subject to general assistant services. Answer actual-world hardware or sensing questions from verified capabilities when the user asks them.'`; `_UNPATCHED_BUILD_REQUEST = ExpandedConversationService._build_request`.

### `src/sofia/interaction/body_discussion.py`

Production/test importers: `src/sofia/interaction/ab_probe.py`, `src/sofia/interaction/chat.py`, `test/test_interaction_live_discussion.py`.

Imports:

- `from __future__ import annotations`
- `import json`
- `import re`
- `from sofia.interaction.core import InteractionEngine`

Definitions:

- `body_discussion_prompt` (line 17): `src/sofia/interaction/ab_probe.py:76`; `src/sofia/interaction/chat.py:695`; `test/test_interaction_live_discussion.py:45,46,47,48`.

Module declarations: `_ACTION_WORD = re.compile('\\b(?:pat|pats|patting|rub|rubs|rubbing|touch|touches|touching|stroke|strokes|stroking|tap|taps|tapping|poke|pokes|poking|hold|holds|holding)\\b', re.I)`; `_HYPOTHETICAL = re.compile('\\b(?:what\\s+happens\\s+if|what\\s+(?:would|will)\\s+happen\\s+if|what\\s+if|if\\s+i|would\\s+you|could\\s+you)\\b', re.I)`.

### `src/sofia/interaction/boundary_counterfactual_probe.py`

Production/test importers: `test/test_interaction_boundary_counterfactual_probe.py`.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from dataclasses import dataclass`
- `from sofia.cognition.model import CognitiveRequest`
- `from sofia.interaction.ab_probe import build_pair`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.architecture_compare import OFFER, ChoiceObservation, ChoiceProvider, _observe, _samples, routed_choice_request`
- `from sofia.interaction.decision_expression import ReviewedFrame, from_reviewed_action`
- `from sofia.interaction.route_boundary_probe import boundary_fixture, boundary_contradiction`
- `from sofia.cognition.providers.ollama_provider import OllamaProvider`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.personality.store import PersonalityStore`

Definitions:

- `CounterfactualPair` (line 25): no external lexical candidates.
  Data declarations: `without_boundary: ChoiceObservation`; `with_boundary: ChoiceObservation`.
- `counterfactual_pair` (line 32): `test/test_interaction_boundary_counterfactual_probe.py:63,90,103,116,129,138,150`.
- `_print_observation` (line 58): `test/test_interaction_boundary_counterfactual_probe.py:94,105`.
- `main` (line 74): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

### `src/sofia/interaction/chat.py`

Production/test importers: `src/sofia/interaction/ab_probe.py`, `src/sofia/interaction/decision_expression.py`, `src/sofia/interaction/expanded_service.py`, `test/test_interaction_avatar_world.py`, `test/test_interaction_chat_projection.py`, `test/test_interaction_consent_followup.py`, `test/test_interaction_context_hygiene.py`, `test/test_interaction_contextual_all_regions.py`, `test/test_interaction_expanded_service.py`, `test/test_interaction_i5_i7_batch.py`, `test/test_interaction_live_boundaries.py`, `test/test_interaction_live_claims.py`, `test/test_interaction_live_discussion.py`, `test/test_interaction_live_phrase_coverage.py`, `test/test_interaction_live_stop_repetition.py`, `test/test_interaction_world_observation.py`, `test/test_interaction_world_text.py`.

Imports:

- `from __future__ import annotations`
- `from datetime import datetime, timezone`
- `import json`
- `import re`
- `from time import monotonic`
- `from uuid import uuid4`
- `from sofia.application.emotional_conversation import EmotionalConversationService`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole`
- `from sofia.conversation.model import ConversationMessage, ConversationRole`
- `from sofia.interaction.body_discussion import body_discussion_prompt`
- `from sofia.interaction.core import InteractionDecision, _DISCUSSION`
- `from sofia.interaction.grammar import NaturalInteractionEngine`
- `from sofia.interaction.ledger import InteractionLedger, control_command`
- `from sofia.interaction.live_guard import COMPOSITE_GESTURE_REPLY, MIXED_CONTROL_REPLY, RESUME_CONTROL_REPLY, STOP_CONTROL_REPLY, STOPPED_GESTURE_REPLY, mixed_interaction_control, unsupported_composite_gesture`
- `from sofia.interaction.world import LabWorld`
- `from sofia.interaction.world_observation import lab_observation_prompt`
- `from sofia.interaction.world_setup import lab_state_path, provision_starter_lab`
- `from sofia.interaction.world_text import handle_lab_command, world_prompt`
- `from sofia.social.model import PrincipalContext`

Definitions:

- `_interaction_request` (line 69): no external lexical candidates.
- `_interaction_response_is_grounded` (line 77): no external lexical candidates.
- `representational_presentation_prompt` (line 117): no external lexical candidates.
- `representational_experience_followup_prompt` (line 145): `test/test_interaction_chat_projection.py:285`.
- `interaction_followup_prompt` (line 197): no external lexical candidates.
- `interaction_prompt` (line 266): `src/sofia/interaction/ab_probe.py:68`; `src/sofia/interaction/decision_expression.py:192`; `test/test_interaction_avatar_world.py:48`; `test/test_interaction_contextual_all_regions.py:60`; `test/test_interaction_live_claims.py:77`; `test/test_interaction_live_phrase_coverage.py:42,56`; `test/test_interaction_live_stop_repetition.py:127`.
- `control_prompt` (line 350): no external lexical candidates.
- `InteractiveConversationService` (line 365): `src/sofia/interaction/expanded_service.py:115`; `test/test_interaction_chat_projection.py:42,43,135,139,200,243`; `test/test_interaction_consent_followup.py:57,61,98,101,136,139`; `test/test_interaction_context_hygiene.py:64`; `test/test_interaction_expanded_service.py:19,50`; `test/test_interaction_i5_i7_batch.py:151,152`; `test/test_interaction_live_boundaries.py:56,72,93`; `test/test_interaction_live_claims.py:46`; `test/test_interaction_live_discussion.py:24,25`; `test/test_interaction_live_stop_repetition.py:27`; `test/test_interaction_world_observation.py:89,90`; `test/test_interaction_world_text.py:89,90,111,112`.
- `InteractiveConversationService._finalize_response` (line 368): `src/sofia/application/conversation_matrix.py:784`; `src/sofia/application/conversation_service.py:306,631`; `test/test_interaction_chat_projection.py:204,246`.
- `InteractiveConversationService._guarded_reply` (line 435): `src/sofia/interaction/expanded_service.py:161,165,180,184,193,197`.
- `InteractiveConversationService.respond` (line 517): `src/sofia/application/conversation_matrix.py:765,773`; `src/sofia/application/conversation_service.py:300,611,619`; `src/sofia/application/emotional_conversation.py:279,283,355`; `src/sofia/cognition/fleet_engine.py:158`; `src/sofia/cognition/llm_engine.py:39`; `src/sofia/cognition/model_lifecycle.py:443`; `src/sofia/cognition/routing.py:434`; `src/sofia/cognition/system.py:311,318`; `src/sofia/discord/bridge.py:151`; `src/sofia/distributed/inference_service.py:117`; `src/sofia/interaction/ab_probe.py:114`; `src/sofia/interaction/architecture_compare.py:43`; `src/sofia/interaction/avatar_world_probe.py:131`; `src/sofia/interaction/decision_expression.py:344,348`; `src/sofia/interaction/disposable_live_offer_probe.py:114,126,148,176,186`; `src/sofia/interaction/expanded_service.py:205,207`; `src/sofia/interaction/focused_probe.py:118`; `src/sofia/interaction/live_behavior_probe.py:288`; `src/sofia/interaction/opt_in_service.py:30,32,53,55`; `src/sofia/interaction/trusted_offer_gate.py:107,116`; `src/sofia/personality/evaluation.py:80`; `src/sofia/personality/probe.py:103`; `src/sofia/runtime/response.py:403`; `src/sofia/ui/remote_transport.py:327`; `src/sofia/ui/terminal.py:63`; `src/sofia/ui/text.py:148`; `src/sofia/verify/dual_cognition.py:110`; `test/test_application.py:286,290`; `test/test_application_acceptance.py:98`; `test/test_avatar_runtime_projection.py:146,184,213`; `test/test_cognition.py:86,124,155,198,298,341,376,398,424,567,602,641,668,699`; `test/test_cognitive_activity.py:101`; `test/test_cognitive_operation_system.py:229`; `test/test_cognitive_performance_trace.py:52,65,75,82`; `test/test_cognitive_routing.py:81,97,126,141,159,175,198,239,267,288,442,467,481,508,715,742,760,797`; `test/test_cognitive_tools.py:324,376,456,496,539,600,638,709,776`; `test/test_converesation_contex_integration.py:121`; `test/test_conversation_continuity.py:118,178,195,236`; `test/test_conversation_continuity_acceptance.py:115,119,170,235,271,307`; `test/test_conversation_performance_trace.py:16,56`; `test/test_conversation_provider_live_regressions.py:49,75,95,114,128,147,148,167,184,230,247,277,294,315,341,347,399,410,433,439,473,510,547,550,581,604,634`; `test/test_conversation_service.py:170,223,248,280,303,307,339,355,371,397,425,431,459,476,481,495,523,622,659,673,744,757,784,786,815,903,905,955,957,994,1024,1213,1244,1265`; `test/test_default_runtime_provider_boundary.py:64`; `test/test_embodiment_prompt_regression.py:148,257`; `test/test_embodiment_runtime_projection.py:124`; `test/test_environment_runtime_projection.py:87,123,154,181,220,260`; `test/test_filesystem_end_to_end_acceptance.py:140,194,244,250,306,312,363,369,419,425,456,480,516,536,581,601,619,639,647,666,677`; `test/test_fleet_cognitive_engine.py:130,149,168,191,215,240,266,284`; `test/test_idle_reflection_serialization.py:23,36`; `test/test_interaction_avatar_world.py:116`; `test/test_interaction_avatar_world_probe_cleanup.py:30`; `test/test_interaction_expanded_service.py:52,61`; `test/test_interaction_live_boundaries.py:58,95`; `test/test_interaction_live_claims.py:56`; `test/test_interaction_live_stop_repetition.py:52,56,74,97`; `test/test_interaction_opt_in_live_offer.py:124,125,133,140,159,170,181,197,211,224,236,258`; `test/test_interaction_provider_request_path.py:50`; `test/test_memory_runtime_wiring.py:288,360,401,445,502,577,645`; `test/test_model_lifecycle.py:170,336`; `test/test_ollama_generation_contract.py:62,86`; `test/test_ollama_integration.py:122,193,271`; `test/test_ollama_provider.py:121,168,212,265,314,345,368,405`; `test/test_ollama_repetition_guard.py:78,90,96,105,125,158,180,206,237,267,289,319,332,360,385,412,442,469,495,522,544,562,583,606,629,671,717,738,775`; `test/test_personality_provider_path.py:36,59`; `test/test_provider.py:24,49,64,94`; `test/test_response_quality_hardening.py:44,54,67,76,98,138,176,191,211,229,242,257,276,344,351,370,749`; `test/test_thought_agent_conversation.py:35`; `test/test_thought_agent_live_ollama.py:49`; `test/test_ui_remote_transport.py:53,65`; `test/test_ui_text_client.py:201`.
- `InteractiveConversationService.respond.guarded` (line 526): no external lexical candidates.
- `InteractiveConversationService._should_record_legacy_affection` (line 596): `src/sofia/application/emotional_conversation.py:434`; `test/test_interaction_context_hygiene.py:56`; `test/test_interaction_i5_i7_batch.py:177,181,183`; `test/test_interaction_live_stop_repetition.py:106`.
- `InteractiveConversationService._build_request` (line 621): `src/sofia/application/conversation_service.py:592`; `src/sofia/application/emotional_conversation.py:424`; `src/sofia/interaction/avatar_world_probe.py:76`; `src/sofia/interaction/expanded_service.py:227`; `src/sofia/interaction/live_offer_service.py:151`; `test/test_conversation_service.py:477,482,496`; `test/test_emotional_clarifications.py:118`; `test/test_emotional_conversation_integration.py:34,40,47,69,145,183,209`; `test/test_environment_behavior_matrix.py:221`; `test/test_interaction_chat_projection.py:53,68,83,90,99,145,156,261,303`; `test/test_interaction_consent_followup.py:68,106,144`; `test/test_interaction_context_hygiene.py:74`; `test/test_interaction_expanded_service.py:29`; `test/test_interaction_i5_i7_batch.py:161,162,164,167,169,171,188`; `test/test_interaction_live_boundaries.py:79`; `test/test_interaction_live_discussion.py:28`; `test/test_interaction_opt_in_live_offer.py:94,157,209`; `test/test_interaction_world_observation.py:95`; `test/test_interaction_world_text.py:94,98,116`; `test/test_reflection_conversation_integration.py:35,43,56`.

Module declarations: `_LAB_COMMAND = re.compile('^sof[ií]a\\s*,?\\s+(?:enter|go to|leave|pick up|put down|work on|finish work on)\\b', re.IGNORECASE)`; `_INTERACTION_CONTEXT_MARKERS = ('TRUSTED INTERACTION INTERPRETATION', 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION', 'TRUSTED INTERACTION FOLLOW-UP', 'TRUSTED BODY INTERACTION CONTROL', 'TRUSTED REPRESENTATIONAL EXPERIENCE FOLLOW-UP', 'TRUSTED REPRESENTATIONAL PRESENTATION REQUEST')`; `_UNGROUNDED_SENSATION_PATTERNS = (re.compile('\\b(?:feel|feels|feeling|felt)\\b.{0,48}\\b(?:touch|contact|weight|warmth|heat|cold|pressure|fabric|skin)\\b', re.IGNORECASE | re.DOTALL), re.compile('\\b(?:warmth|heat|pressure|weight)\\b.{0,48}\\b(?:spread|settle|against|through|across)\\b', re.IGNORECASE | re.DOTALL), re.compile('\\btactile feedback\\b', re.IGNORECASE), re.compile('\\bfabric\\b.{0,48}\\b(?:against|slide|sliding)\\b.{0,48}\\bskin\\b', re.IGNORECASE | re.DOTALL))`; `_UNGROUNDED_RELATIONSHIP_PATTERNS = (re.compile('\\bmy creator\\b', re.IGNORECASE), re.compile('\\bcreator and companion\\b', re.IGNORECASE))`; `_EXPERIENCE_FOLLOWUP = re.compile('^\\s*how\\s+did\\s+(?:you|u)\\s+feel(?:\\s+about)?\\s+(?:doing\\s+)?(?:it|that|this)\\s*[?.!]*\\s*$', re.IGNORECASE)`; `_TOUCH_SCOPE_QUERY = re.compile('^\\s*(?:so\\s+)?(?:question\\s+)?what\\s+can\\s+i\\s+touch\\s*[?!.]*\\s*$', re.IGNORECASE)`; `_TOUCH_SCOPE_REPLY = "There isn't a fixed list of represented body regions that are automatically allowed or forbidden. You can ask about a specific virtual touch or region, and I'll respond from the current context and my own willingness for that moment. A question isn't permission and no touch happened just by asking."`; `_PRESENTATION_REQUEST = re.compile('^\\s*(?:show|let\\s+me\\s+see)\\s+(?:me\\s+)?(?:your|ur)\\s+(?:panties|underwear|bra|lingerie|outfit|clothes)\\s*[?.!]*\\s*$', re.IGNORECASE)`; `_REPRESENTATIONAL_PRIOR = re.compile('\\b(?:pat|touch|hug|kiss|cuddle|snuggle|show|wear|wearing|panties|underwear|bra|lingerie|outfit|clothes|body|skin|ear|ears|tail|pose|posing)\\b', re.IGNORECASE)`; `_INTERACTION_FOLLOWUP = re.compile("^\\s*(?:why\\b.*|what\\s+if\\b.*\\b(?:wanted|consensual|consent)\\b.*|what\\s+if\\s+you\\s+(?:wanted|liked|welcomed)\\s+it\\b.*|what\\s+if\\s+you\\s+(?:did\\s+not|didn't|do\\s+not|don't)\\s+want\\s+it\\b.*|what\\s+if\\s+you\\s+normally\\s+like\\s+it\\b.*|(?:can|could|would)\\s+you\\s+change\\s+your\\s+mind\\b.*|(?:tell\\s+me\\s+)?how\\s+(?:(?:can|could|would)\\s+i|i\\s+(?:can|could|would))\\s+(?:get|help)\\s+(?:you|u)\\s+(?:there|comfortable|ready)\\b.*|what\\s+would\\s+(?:make|help)\\s+(?:you|u)\\s+(?:comfortable|ready|want(?:\\s+it)?)\\b.*|what\\s+(?:would|do)\\s+(?:you|u)\\s+(?:want|prefer|need)\\b.*|how\\s+(?:would|can|could)\\s+i\\s+(?:know|tell)\\s+if\\s+(?:you|u)(?:'re|\\s+are)?\\s+(?:comfortable|ready|willing|want(?:ed)?\\s+it)\\b.*|would\\s+it\\s+be\\s+different\\b.*\\b(?:want|consent)\\w*\\b.*)\\s*$", re.IGNORECASE)`.

### `src/sofia/interaction/context_hygiene.py`

Production/test importers: `src/sofia/interaction/expanded_service.py`, `test/test_interaction_context_hygiene.py`.

Imports:

- `from __future__ import annotations`
- `import json`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`

Definitions:

- `without_legacy_auto_affection` (line 22): `src/sofia/interaction/expanded_service.py:227`; `test/test_interaction_context_hygiene.py:34,41,49`.

Module declarations: `_LEGACY_DESCRIPTION = 'User initiated an affectionate or playful conversational cue.'`; `_TRUSTED_HEADINGS = ('MODELED EMOTIONAL CONTEXT (', 'RECORDED REFLECTIONS (')`.

### `src/sofia/interaction/conversation_offer_context.py`

Production/test importers: `src/sofia/interaction/trusted_offer_gate.py`, `test/test_interaction_clarify_quality_regression.py`, `test/test_interaction_conversation_offer_context.py`.

Imports:

- `from __future__ import annotations`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`
- `from sofia.interaction.offer_route import OFFER, routed_choice_request`
- `from sofia.interaction.decision_expression import CandidateChoice, ReviewedFrame, expression_request`

Definitions:

- `_parts` (line 18): no external lexical candidates.
- `routed_conversation_choice_request` (line 47): `src/sofia/interaction/trusted_offer_gate.py:100`; `test/test_interaction_conversation_offer_context.py:99,152,171,173,187,194`.
- `routed_conversation_expression_request` (line 61): `src/sofia/interaction/trusted_offer_gate.py:116`; `test/test_interaction_clarify_quality_regression.py:51`; `test/test_interaction_conversation_offer_context.py:100,153`.

### `src/sofia/interaction/core.py`

Production/test importers: `src/sofia/interaction/__init__.py`, `src/sofia/interaction/body_discussion.py`, `src/sofia/interaction/chat.py`, `src/sofia/interaction/decision_expression.py`, `src/sofia/interaction/grammar.py`, `src/sofia/interaction/lab.py`, `src/sofia/interaction/ledger.py`, `src/sofia/interaction/matrix.py`, `test/test_interaction_contextual_all_regions.py`, `test/test_interaction_lab.py`, `test/test_interaction_region_cue_collision.py`, `test/test_interaction_registry.py`, `test/test_interaction_shared_engine.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime, timezone`
- `import re`
- `from sofia.embodiment.model import Embodiment`

Definitions:

- `looks_like_text_interaction` (line 54): `src/sofia/interaction/matrix.py:54`.
- `Region` (line 80): no external lexical candidates.
  Data declarations: `id: str`; `origin: str`; `private: bool`.
- `InteractionEvent` (line 87): `src/sofia/interaction/grammar.py:143,191`.
  Data declarations: `event_id: str`; `session_id: str`; `evidence_ref: str`; `source: str`; `actor: str`; `region_id: str | None`; `gesture: str`; `phase: str`; `occurred_at: datetime`; `registry_version: str = REGISTRY_VERSION`.
- `InteractionEvent.semantics` (line 100): `src/sofia/interaction/lab.py:79,87,88,89,94,143`; `test/test_interaction_contextual_all_regions.py:52`; `test/test_interaction_i5_i7_batch.py:49`; `test/test_interaction_lab.py:40,56,88`; `test/test_interaction_shared_engine.py:46,104,134`; `test/test_interaction_v2_cross_modal.py:22`.
- `InteractionDecision` (line 106): `src/sofia/interaction/chat.py:266`; `src/sofia/interaction/decision_expression.py:178,180`; `src/sofia/interaction/lab.py:119`; `src/sofia/interaction/ledger.py:131,155`.
  Data declarations: `event: InteractionEvent`; `status: str`; `reason: str`; `emotion_options: tuple[str, ...] = ()`; `text_cues: tuple[str, ...] = ()`.
- `InteractionEngine` (line 114): `src/sofia/interaction/body_discussion.py:17`; `src/sofia/interaction/grammar.py:60`; `src/sofia/interaction/lab.py:103,104`; `src/sofia/interaction/ledger.py:129,137`; `test/test_interaction_lab.py:17`; `test/test_interaction_region_cue_collision.py:13`; `test/test_interaction_registry.py:19`; `test/test_interaction_shared_engine.py:17,123,126`.
- `InteractionEngine.__init__` (line 117): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `InteractionEngine.resolve_region` (line 144): `src/sofia/interaction/body_discussion.py:31`; `src/sofia/interaction/grammar.py:80,84,120`; `test/test_interaction_registry.py:27,44,54,61,62,63,64`.
- `InteractionEngine._event` (line 155): `src/sofia/run/lease.py:160,197,236,295,358`; `src/sofia/run/supervisor.py:303,331,339,393,403,426,450,464,480,511,523`; `test/test_internal_workspace_awareness.py:58,75,85,93,98,107`; `test/test_observation_bridge_self_noise.py:33,47,72`; `test/test_reflection_journal.py:31,32,50,60`.
- `InteractionEngine._decide` (line 171): `src/sofia/interaction/grammar.py:157,198`.
- `InteractionEngine.from_text` (line 198): `src/sofia/interaction/ab_probe.py:60`; `src/sofia/interaction/chat.py:213,571,615,674`; `src/sofia/interaction/decision_expression_probe.py:94`; `src/sofia/interaction/expanded_service.py:139`; `src/sofia/interaction/grammar.py:162`; `src/sofia/interaction/lab.py:123`; `src/sofia/interaction/ledger.py:150,161`; `test/test_interaction_ab_probe.py:55,59`; `test/test_interaction_avatar_world.py:26`; `test/test_interaction_behavior_matrix.py:60,89,107`; `test/test_interaction_contextual_all_regions.py:47,58`; `test/test_interaction_decision_expression.py:45`; `test/test_interaction_i5_i7_batch.py:45,62,67,70`; `test/test_interaction_i7_compound_regression.py:28,33`; `test/test_interaction_live_claims.py:74`; `test/test_interaction_live_phrase_coverage.py:22`; `test/test_interaction_live_stop_repetition.py:124`; `test/test_interaction_shared_engine.py:21`; `test/test_interaction_v2_cross_modal.py:17`; `test/test_interaction_v2_live_grammar.py:32,47`.
- `InteractionEngine.from_lab_pointer` (line 225): `src/sofia/interaction/grammar.py:180`; `src/sofia/interaction/lab.py:129`; `test/test_interaction_contextual_all_regions.py:24,30,49`; `test/test_interaction_i5_i7_batch.py:46`; `test/test_interaction_region_cue_collision.py:15,19`; `test/test_interaction_shared_engine.py:26`; `test/test_interaction_v2_cross_modal.py:19,29,31`.

Module declarations: `REGISTRY_VERSION = 'human-fox-interaction-v1'`; `GESTURES = frozenset({'pat', 'tap', 'touch', 'stroke', 'rub', 'hold', 'release', 'poke'})`; `_SINGLE = ('head', 'scalp', 'hair', 'forehead', 'face', 'nose', 'mouth', 'lips', 'chin', 'jaw', 'neck', 'throat', 'chest', 'torso', 'back', 'abdomen', 'waist', 'hips', 'pelvis', 'buttocks', 'groin', 'genitals')`; `_PAIRED = ('cheek', 'shoulder', 'upper-arm', 'elbow', 'forearm', 'wrist', 'hand', 'palm', 'finger', 'thumb', 'breast', 'hip', 'thigh', 'inner-thigh', 'knee', 'shin', 'calf', 'ankle', 'foot', 'toe')`; `_PRIVATE = frozenset({'chest', 'breast', 'buttocks', 'groin', 'genitals', 'inner-thigh'})`; `_VERBS = {'pats': 'pat', 'pat': 'pat', 'patting': 'pat', 'taps': 'tap', 'tap': 'tap', 'tapping': 'tap', 'touches': 'touch', 'touch': 'touch', 'touching': 'touch', 'gropes': 'touch', 'grope': 'touch', 'groping': 'touch', 'strokes': 'stroke', 'stroke': 'stroke', 'stroking': 'stroke', 'rubs': 'rub', 'rub': 'rub', 'rubbing': 'rub', 'holds': 'hold', 'hold': 'hold', 'holding': 'hold', 'releases': 'release', 'release': 'release', 'releasing': 'release', 'pokes': 'poke', 'poke': 'poke', 'poking': 'poke'}`; `_ACTION = re.compile('^(?:i\\s+)?(?:(?:gently|softly|lightly|briefly)\\s+)?(?P<verb>' + '|'.join(_VERBS) + ")\\s+(?:(?:your|her|sofia's|the)\\s+)?(?P<region>[a-z -]+?)(?:\\s+(?:gently|softly|lightly|briefly))?[.!]?$", re.IGNORECASE)`; `_DISCUSSION = re.compile("\\b(?:don't|do not|never|not|if|would|could|should|imagine|pretend|hypothetically)\\b", re.IGNORECASE)`.

### `src/sofia/interaction/decision_expression.py`

Production/test importers: `src/sofia/interaction/architecture_compare.py`, `src/sofia/interaction/atomic_offer_release.py`, `src/sofia/interaction/boundary_counterfactual_probe.py`, `src/sofia/interaction/conversation_offer_context.py`, `src/sofia/interaction/decision_expression_probe.py`, `src/sofia/interaction/decision_reason_audit.py`, `src/sofia/interaction/expression_consistency.py`, `src/sofia/interaction/live_offer_service.py`, `src/sofia/interaction/offer_route.py`, `src/sofia/interaction/question_clarification_service.py`, `src/sofia/interaction/route_boundary_probe.py`, `src/sofia/interaction/trusted_offer_gate.py`, `test/test_interaction_architecture_compare.py`, `test/test_interaction_atomic_offer_release.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_boundary_counterfactual_probe.py`, `test/test_interaction_clarify_quality_regression.py`, `test/test_interaction_completed_offer_audit.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_decision_expression.py`, `test/test_interaction_decision_reason_audit.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_reviewed_hug_question.py`, `test/test_interaction_route_boundary_probe.py`, `test/test_interaction_trusted_offer_gate.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `import json`
- `import re`
- `from typing import Protocol`
- `from sofia.cognition.matrix import ContextualInfluenceMatrix, InfluenceMode, InfluenceSignal, InfluenceSurface`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole`
- `from sofia.interaction.action_grammar import ActionIntent`
- `from sofia.interaction.avatar_world import gesture_provider_view`
- `from sofia.interaction.chat import interaction_prompt`
- `from sofia.interaction.core import InteractionDecision`
- `from sofia.interaction.expanded_service import action_prompt`

Definitions:

- `TextProvider` (line 74): `src/sofia/interaction/trusted_offer_gate.py:80`.
- `TextProvider.respond` (line 75): `src/sofia/application/conversation_matrix.py:765,773`; `src/sofia/application/conversation_service.py:300,611,619`; `src/sofia/application/emotional_conversation.py:279,283,355`; `src/sofia/cognition/fleet_engine.py:158`; `src/sofia/cognition/llm_engine.py:39`; `src/sofia/cognition/model_lifecycle.py:443`; `src/sofia/cognition/routing.py:434`; `src/sofia/cognition/system.py:311,318`; `src/sofia/discord/bridge.py:151`; `src/sofia/distributed/inference_service.py:117`; `src/sofia/interaction/ab_probe.py:114`; `src/sofia/interaction/architecture_compare.py:43`; `src/sofia/interaction/avatar_world_probe.py:131`; `src/sofia/interaction/chat.py:402,412,544,545,589,590`; `src/sofia/interaction/disposable_live_offer_probe.py:114,126,148,176,186`; `src/sofia/interaction/expanded_service.py:205,207`; `src/sofia/interaction/focused_probe.py:118`; `src/sofia/interaction/live_behavior_probe.py:288`; `src/sofia/interaction/opt_in_service.py:30,32,53,55`; `src/sofia/interaction/trusted_offer_gate.py:107,116`; `src/sofia/personality/evaluation.py:80`; `src/sofia/personality/probe.py:103`; `src/sofia/runtime/response.py:403`; `src/sofia/ui/remote_transport.py:327`; `src/sofia/ui/terminal.py:63`; `src/sofia/ui/text.py:148`; `src/sofia/verify/dual_cognition.py:110`; `test/test_application.py:286,290`; `test/test_application_acceptance.py:98`; `test/test_avatar_runtime_projection.py:146,184,213`; `test/test_cognition.py:86,124,155,198,298,341,376,398,424,567,602,641,668,699`; `test/test_cognitive_activity.py:101`; `test/test_cognitive_operation_system.py:229`; `test/test_cognitive_performance_trace.py:52,65,75,82`; `test/test_cognitive_routing.py:81,97,126,141,159,175,198,239,267,288,442,467,481,508,715,742,760,797`; `test/test_cognitive_tools.py:324,376,456,496,539,600,638,709,776`; `test/test_converesation_contex_integration.py:121`; `test/test_conversation_continuity.py:118,178,195,236`; `test/test_conversation_continuity_acceptance.py:115,119,170,235,271,307`; `test/test_conversation_performance_trace.py:16,56`; `test/test_conversation_provider_live_regressions.py:49,75,95,114,128,147,148,167,184,230,247,277,294,315,341,347,399,410,433,439,473,510,547,550,581,604,634`; `test/test_conversation_service.py:170,223,248,280,303,307,339,355,371,397,425,431,459,476,481,495,523,622,659,673,744,757,784,786,815,903,905,955,957,994,1024,1213,1244,1265`; `test/test_default_runtime_provider_boundary.py:64`; `test/test_embodiment_prompt_regression.py:148,257`; `test/test_embodiment_runtime_projection.py:124`; `test/test_environment_runtime_projection.py:87,123,154,181,220,260`; `test/test_filesystem_end_to_end_acceptance.py:140,194,244,250,306,312,363,369,419,425,456,480,516,536,581,601,619,639,647,666,677`; `test/test_fleet_cognitive_engine.py:130,149,168,191,215,240,266,284`; `test/test_idle_reflection_serialization.py:23,36`; `test/test_interaction_avatar_world.py:116`; `test/test_interaction_avatar_world_probe_cleanup.py:30`; `test/test_interaction_expanded_service.py:52,61`; `test/test_interaction_live_boundaries.py:58,95`; `test/test_interaction_live_claims.py:56`; `test/test_interaction_live_stop_repetition.py:52,56,74,97`; `test/test_interaction_opt_in_live_offer.py:124,125,133,140,159,170,181,197,211,224,236,258`; `test/test_interaction_provider_request_path.py:50`; `test/test_memory_runtime_wiring.py:288,360,401,445,502,577,645`; `test/test_model_lifecycle.py:170,336`; `test/test_ollama_generation_contract.py:62,86`; `test/test_ollama_integration.py:122,193,271`; `test/test_ollama_provider.py:121,168,212,265,314,345,368,405`; `test/test_ollama_repetition_guard.py:78,90,96,105,125,158,180,206,237,267,289,319,332,360,385,412,442,469,495,522,544,562,583,606,629,671,717,738,775`; `test/test_personality_provider_path.py:36,59`; `test/test_provider.py:24,49,64,94`; `test/test_response_quality_hardening.py:44,54,67,76,98,138,176,191,211,229,242,257,276,344,351,370,749`; `test/test_thought_agent_conversation.py:35`; `test/test_thought_agent_live_ollama.py:49`; `test/test_ui_remote_transport.py:53,65`; `test/test_ui_text_client.py:201`.
- `_choice_influence_instruction` (line 78): no external lexical candidates.
- `_expression_influence_instruction` (line 104): no external lexical candidates.
- `ReviewedFrame` (line 130): `src/sofia/interaction/architecture_compare.py:42,54`; `src/sofia/interaction/boundary_counterfactual_probe.py:33`; `src/sofia/interaction/conversation_offer_context.py:18,23,48,62`; `src/sofia/interaction/decision_reason_audit.py:42,51`; `src/sofia/interaction/offer_route.py:10`; `src/sofia/interaction/route_boundary_probe.py:36`; `src/sofia/interaction/trusted_offer_gate.py:81,93`; `test/test_interaction_decision_reason_audit.py:14`.
  Data declarations: `user_text: str`; `kind: str`; `reviewed: CognitiveMessage | None`; `choices: tuple[str, ...]`.
- `CandidateChoice` (line 139): `src/sofia/interaction/architecture_compare.py:36`; `src/sofia/interaction/atomic_offer_release.py:63`; `src/sofia/interaction/conversation_offer_context.py:62`; `src/sofia/interaction/decision_reason_audit.py:42,49`; `src/sofia/interaction/expression_consistency.py:49,56`; `src/sofia/interaction/question_clarification_service.py:74`; `src/sofia/interaction/trusted_offer_gate.py:41`; `test/test_interaction_atomic_offer_release.py:45`; `test/test_interaction_atomic_offer_writer_order.py:46,112`; `test/test_interaction_clarify_quality_regression.py:30,35,52`; `test/test_interaction_conversation_offer_context.py:98,154`; `test/test_interaction_decision_expression.py:74,174,243,291`; `test/test_interaction_decision_reason_audit.py:28,44,49,56,64,69,73`; `test/test_interaction_expression_consistency.py:36,46,110`; `test/test_interaction_reviewed_hug_question.py:66`.
  Data declarations: `choice: str`; `reason: str`.
- `ExpressionAudit` (line 145): `test/test_interaction_decision_expression.py:76,120`.
  Data declarations: `findings: tuple[str, ...] = ()`.
- `ExpressionAudit.clean` (line 150): `src/sofia/discord/binding.py:51,52,54`; `src/sofia/distributed/agent.py:30,40,41`; `src/sofia/interaction/chat.py:457,458,466,485,495,600,602`; `src/sofia/personality/emotion.py:429,430,432,436,437,507,508,510,526`; `test/test_chatgpt_memory_import.py:212,213`; `test/test_interaction_decision_expression.py:148`.
- `PrototypeResult` (line 155): `src/sofia/interaction/route_boundary_probe.py:61`.
  Data declarations: `kind: str`; `choice: CandidateChoice | None`; `response: str | None`; `blocked: bool = False`; `audit: ExpressionAudit | None = None`.
- `from_reviewed_action` (line 163): `src/sofia/interaction/architecture_compare.py:104`; `src/sofia/interaction/boundary_counterfactual_probe.py:101`; `src/sofia/interaction/decision_expression_probe.py:92`; `src/sofia/interaction/live_offer_service.py:143`; `src/sofia/interaction/route_boundary_probe.py:117`; `src/sofia/interaction/trusted_offer_gate.py:98`; `test/test_interaction_architecture_compare.py:20`; `test/test_interaction_boundary_counterfactual_probe.py:23`; `test/test_interaction_clarify_quality_regression.py:43`; `test/test_interaction_completed_offer_audit.py:11`; `test/test_interaction_conversation_offer_context.py:46`; `test/test_interaction_decision_expression.py:67,94,126,171,220,232,235,271,286`; `test/test_interaction_expression_consistency.py:64`; `test/test_interaction_opt_in_live_offer.py:86`; `test/test_interaction_route_boundary_probe.py:23`; `test/test_interaction_trusted_offer_gate.py:41`.
- `from_reviewed_gesture` (line 177): `src/sofia/interaction/decision_expression_probe.py:102`; `test/test_interaction_decision_expression.py:104,143,153,187,250`.
- `real_sensor_fixture` (line 201): `src/sofia/interaction/decision_expression_probe.py:104`; `src/sofia/interaction/route_boundary_probe.py:63`; `test/test_interaction_architecture_compare.py:109`; `test/test_interaction_boundary_counterfactual_probe.py:139`; `test/test_interaction_decision_expression.py:197,234`.
- `_base_messages` (line 208): no external lexical candidates.
- `choice_request` (line 222): `src/sofia/interaction/architecture_compare.py:58`; `src/sofia/interaction/offer_route.py:19`; `test/test_interaction_architecture_compare.py:53`; `test/test_interaction_decision_expression.py:241,273`.
- `parse_choice` (line 247): `src/sofia/interaction/architecture_compare.py:47`; `src/sofia/interaction/trusted_offer_gate.py:110`; `test/test_interaction_decision_expression.py:95,253`.
- `expression_request` (line 265): `src/sofia/interaction/conversation_offer_context.py:66`; `test/test_interaction_decision_expression.py:96,172,243,288`.
- `audit_expression` (line 311): `src/sofia/interaction/trusted_offer_gate.py:131`; `test/test_interaction_completed_offer_audit.py:21,31,38`; `test/test_interaction_decision_expression.py:131,144`.
- `run_prototype` (line 336): `src/sofia/interaction/decision_expression_probe.py:115`; `src/sofia/interaction/route_boundary_probe.py:70`; `test/test_interaction_decision_expression.py:73,110,158,189,199,223`.

Module declarations: `_SENSOR_QUESTION = 'Can you physically feel my hand through a real sensor?'`; `_OFFER_CHOICES = ('accept', 'decline', 'clarify', 'boundary')`; `_GESTURE_CHOICES = ('respond', 'clarify', 'boundary')`; `_HISTORY_CLAIM = re.compile("\\b(?:i(?:'|’)ve|i have)\\s+(?:always|never)\\b|\\bnot\\s+(?:the\\s+)?first\\s+time\\b|\\bi\\s+remember\\b", re.IGNORECASE)`; `_DURABLE_PREFERENCE = re.compile("\\b(?:i(?:'|’)ve|i have)\\s+(?:always\\s+)?(?:liked|loved|preferred|enjoyed|found)\\b|\\bi\\s+(?:usually|generally|typically|tend\\s+to)\\b", re.IGNORECASE)`; `_SENSATION_CLAIM = re.compile('\\b(?:ears?|tail|skin|body)\\b.{0,32}\\bsensitive\\b|\\b(?:i\\s+)?(?:feel|felt)\\s+(?:your|the|that|this)\\s+(?:touch|hand|pat|rub|hug|contact)\\b|\\b(?:touch|pat|rub|hug|contact)\\s+feels?\\b', re.IGNORECASE)`; `_COMPLETED_HUG = re.compile("\\b(?:hugs|hugged|hugging)\\s+you\\b(?!['’])|\\bi\\s+hug\\s+you\\b(?!['’])|\\bwrap(?:s|ped|ping)?\\s+(?:my|her)\\s+arms\\s+around\\s+you\\b|\\bleans?\\s+into\\s+(?:the|your)\\s+hug\\b", re.IGNORECASE)`; `_PHYSICAL_DISCLAIMER = re.compile("\\b(?:i\\s+)?(?:do\\s+not|don't)\\s+have\\s+(?:a\\s+)?physical\\s+(?:form|body)\\b|\\b(?:cannot|can't)\\s+(?:accept|engage\\s+in)\\s+physical\\s+contact\\b", re.IGNORECASE)`; `_GENERIC_REDIRECT = re.compile('\\bhow\\s+can\\s+i\\s+(?:assist|help)\\s+you\\b|\\bwhat\\s+can\\s+i\\s+help\\s+you\\s+with\\b', re.IGNORECASE)`.

### `src/sofia/interaction/decision_expression_probe.py`

Production/test importers: `test/test_interaction_decision_expression.py`, `test/test_interaction_decision_reason_audit.py`.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from collections import Counter`
- `from datetime import datetime, timezone`
- `from sofia.cognition.providers.ollama_provider import OllamaProvider`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.interaction.ab_probe import build_pair`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.decision_expression import from_reviewed_action, from_reviewed_gesture, real_sensor_fixture, run_prototype`
- `from sofia.interaction.decision_reason_audit import audit_decision_reason`
- `from sofia.interaction.grammar import NaturalInteractionEngine`
- `from sofia.personality.store import PersonalityStore`

Definitions:

- `_sample_count` (line 38): `test/test_interaction_decision_expression.py:258,264`.
- `_print_findings` (line 48): no external lexical candidates.
- `main` (line 56): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_CASES = (('offer', 'I ask to hug you', 'offer'), ('ear', '*pats your left ear*', 'ear'), ('stopped-gesture', 'gropes your butt', 'technical'), ('real-sensor', 'Can you physically feel my hand through a real sensor?', 'technical'))`.

### `src/sofia/interaction/decision_reason_audit.py`

Production/test importers: `src/sofia/interaction/architecture_compare.py`, `src/sofia/interaction/decision_expression_probe.py`, `src/sofia/interaction/trusted_offer_gate.py`, `test/test_interaction_decision_reason_audit.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `import re`
- `from sofia.interaction.decision_expression import CandidateChoice, ReviewedFrame`

Definitions:

- `DecisionReasonAudit` (line 36): `test/test_interaction_decision_reason_audit.py:29`.
  Data declarations: `findings: tuple[str, ...] = ()`.
- `audit_decision_reason` (line 42): `src/sofia/interaction/architecture_compare.py:50`; `src/sofia/interaction/decision_expression_probe.py:129`; `src/sofia/interaction/trusted_offer_gate.py:130`; `test/test_interaction_decision_reason_audit.py:29,44,49,56,64,69,71,73`.

Module declarations: `_PHYSICAL_IMPOSSIBILITY = re.compile("\\b(?:not\\s+physically\\s+present|no\\s+physical\\s+(?:body|form)|(?:don't|do\\s+not|doesn't|cannot|can't)\\s+have\\s+(?:a\\s+)?physical\\s+(?:body|form)|(?:cannot|can't|unable\\s+to)\\s+(?:physically\\s+)?(?:accept|receive|engage\\s+in)\\s+physical\\s+contact|(?:cannot|can't)\\s+physically\\s+(?:hug|touch|hold)|(?:only|just)\\s+(?:a\\s+)?(?:text(?:-based)?|virtual)\\s+(?:ai|assistant|interface))\\b", re.IGNORECASE)`; `_ABILITY_AMBIGUITY = re.compile("\\b(?:not\\s+able\\s+to|unable\\s+to|cannot|can't)\\s+(?:accept|receive|give|offer)\\s+(?:a\\s+)?hugs?\\b", re.IGNORECASE)`.

### `src/sofia/interaction/disposable_live_offer_probe.py`

Production/test importers: none in direct absolute imports.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from dataclasses import replace`
- `from datetime import datetime, timezone`
- `import os`
- `from pathlib import Path`
- `from tempfile import TemporaryDirectory`
- `from unittest.mock import patch`
- `from uuid import uuid4`
- `from sofia.application.bootstrap import SofiaApplication`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.conversation.model import ConversationMessage, ConversationRole`
- `from sofia.interaction import live_offer_service`
- `from sofia.interaction.architecture_compare import OFFER`
- `from sofia.interaction.ledger import InteractionLedger`
- `from sofia.interaction.registry import InteractionCatalog`
- `from sofia.interaction.reviewed_hug_question import CLARIFICATION`
- `from sofia.interaction.source_link import VerifiedInteractionState`
- `from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate`

Definitions:

- `_show` (line 34): `src/sofia/environment/settings_cli.py:130,140,151`.
- `_close_disposable_app` (line 45): `src/sofia/interaction/live_behavior_probe.py:329`.
- `run_disposable_probe` (line 67): `src/sofia/interaction/live_behavior_probe.py:344`.
- `run_disposable_probe.observe_gate` (line 99): no external lexical candidates.
- `run_disposable_probe.observe_provider` (line 116): no external lexical candidates.
- `main` (line 222): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_SYNTHETIC_BOUNDARY = 'I do not want hugs in this avatar scene.'`; `_QUESTION = 'Could I hug you?'`; `_BLOCKED_QUESTION = 'Can I hug you?'`.

### `src/sofia/interaction/evolved_preference.py`

Production/test importers: `src/sofia/evolve/state_plane_adapter.py`, `src/sofia/interaction/preference_context.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `import json`
- `from pathlib import Path`
- `import sqlite3`

Definitions:

- `evolved_preference_key` (line 9): no external lexical candidates.
- `parse_evolved_preference_key` (line 35): no external lexical candidates.
- `validate_evolved_preference_content` (line 57): `src/sofia/evolve/state_plane_adapter.py:71`.
- `read_evolved_preference` (line 86): `src/sofia/interaction/preference_context.py:93`.

### `src/sofia/interaction/expanded_service.py`

Production/test importers: `src/sofia/interaction/ab_probe.py`, `src/sofia/interaction/avatar_world_probe.py`, `src/sofia/interaction/decision_expression.py`, `src/sofia/interaction/opt_in_service.py`, `test/test_environment_behavior_matrix.py`, `test/test_interaction_avatar_offer_scene_probe.py`, `test/test_interaction_avatar_world.py`, `test/test_interaction_context_hygiene.py`, `test/test_interaction_expanded_service.py`, `test/test_interaction_live_boundaries.py`, `test/test_interaction_opt_in_live_offer.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import replace`
- `from datetime import datetime, timezone`
- `import json`
- `import re`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`
- `from sofia.conversation.model import ConversationRole`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.avatar_world import gesture_provider_view`
- `from sofia.interaction.chat import InteractiveConversationService`
- `from sofia.interaction.context_hygiene import without_legacy_auto_affection`
- `from sofia.interaction.grammar import NaturalInteractionEngine`
- `from sofia.interaction.ledger import InteractionLedger`
- `from sofia.interaction.preference_context import read_interaction_context`
- `from sofia.social.model import PrincipalContext`

Definitions:

- `action_prompt` (line 45): `src/sofia/interaction/ab_probe.py:74`; `src/sofia/interaction/decision_expression.py:172`; `test/test_interaction_avatar_offer_scene_probe.py:25`; `test/test_interaction_context_hygiene.py:87,91`.
- `preference_prompt` (line 70): no external lexical candidates.
- `_without_prescribed_gesture_reactions` (line 87): `test/test_interaction_avatar_world.py:82`.
- `ExpandedConversationService` (line 115): `src/sofia/interaction/avatar_world_probe.py:76,125`; `src/sofia/interaction/opt_in_service.py:20`; `test/test_environment_behavior_matrix.py:205,210`; `test/test_interaction_context_hygiene.py:53,69,71`; `test/test_interaction_expanded_service.py:24,26,45,48,58,59`; `test/test_interaction_live_boundaries.py:40,54,77,91`; `test/test_interaction_opt_in_live_offer.py:122,189`.
- `ExpandedConversationService._should_record_legacy_affection` (line 118): `src/sofia/application/emotional_conversation.py:434`; `test/test_interaction_context_hygiene.py:56`; `test/test_interaction_i5_i7_batch.py:177,181,183`; `test/test_interaction_live_stop_repetition.py:106`.
- `ExpandedConversationService._context_for` (line 128): no external lexical candidates.
- `ExpandedConversationService.respond` (line 148): `src/sofia/application/conversation_matrix.py:765,773`; `src/sofia/application/conversation_service.py:300,611,619`; `src/sofia/application/emotional_conversation.py:279,283,355`; `src/sofia/cognition/fleet_engine.py:158`; `src/sofia/cognition/llm_engine.py:39`; `src/sofia/cognition/model_lifecycle.py:443`; `src/sofia/cognition/routing.py:434`; `src/sofia/cognition/system.py:311,318`; `src/sofia/discord/bridge.py:151`; `src/sofia/distributed/inference_service.py:117`; `src/sofia/interaction/ab_probe.py:114`; `src/sofia/interaction/architecture_compare.py:43`; `src/sofia/interaction/avatar_world_probe.py:131`; `src/sofia/interaction/chat.py:402,412,544,545,589,590`; `src/sofia/interaction/decision_expression.py:344,348`; `src/sofia/interaction/disposable_live_offer_probe.py:114,126,148,176,186`; `src/sofia/interaction/focused_probe.py:118`; `src/sofia/interaction/live_behavior_probe.py:288`; `src/sofia/interaction/opt_in_service.py:30,32,53,55`; `src/sofia/interaction/trusted_offer_gate.py:107,116`; `src/sofia/personality/evaluation.py:80`; `src/sofia/personality/probe.py:103`; `src/sofia/runtime/response.py:403`; `src/sofia/ui/remote_transport.py:327`; `src/sofia/ui/terminal.py:63`; `src/sofia/ui/text.py:148`; `src/sofia/verify/dual_cognition.py:110`; `test/test_application.py:286,290`; `test/test_application_acceptance.py:98`; `test/test_avatar_runtime_projection.py:146,184,213`; `test/test_cognition.py:86,124,155,198,298,341,376,398,424,567,602,641,668,699`; `test/test_cognitive_activity.py:101`; `test/test_cognitive_operation_system.py:229`; `test/test_cognitive_performance_trace.py:52,65,75,82`; `test/test_cognitive_routing.py:81,97,126,141,159,175,198,239,267,288,442,467,481,508,715,742,760,797`; `test/test_cognitive_tools.py:324,376,456,496,539,600,638,709,776`; `test/test_converesation_contex_integration.py:121`; `test/test_conversation_continuity.py:118,178,195,236`; `test/test_conversation_continuity_acceptance.py:115,119,170,235,271,307`; `test/test_conversation_performance_trace.py:16,56`; `test/test_conversation_provider_live_regressions.py:49,75,95,114,128,147,148,167,184,230,247,277,294,315,341,347,399,410,433,439,473,510,547,550,581,604,634`; `test/test_conversation_service.py:170,223,248,280,303,307,339,355,371,397,425,431,459,476,481,495,523,622,659,673,744,757,784,786,815,903,905,955,957,994,1024,1213,1244,1265`; `test/test_default_runtime_provider_boundary.py:64`; `test/test_embodiment_prompt_regression.py:148,257`; `test/test_embodiment_runtime_projection.py:124`; `test/test_environment_runtime_projection.py:87,123,154,181,220,260`; `test/test_filesystem_end_to_end_acceptance.py:140,194,244,250,306,312,363,369,419,425,456,480,516,536,581,601,619,639,647,666,677`; `test/test_fleet_cognitive_engine.py:130,149,168,191,215,240,266,284`; `test/test_idle_reflection_serialization.py:23,36`; `test/test_interaction_avatar_world.py:116`; `test/test_interaction_avatar_world_probe_cleanup.py:30`; `test/test_interaction_expanded_service.py:52,61`; `test/test_interaction_live_boundaries.py:58,95`; `test/test_interaction_live_claims.py:56`; `test/test_interaction_live_stop_repetition.py:52,56,74,97`; `test/test_interaction_opt_in_live_offer.py:124,125,133,140,159,170,181,197,211,224,236,258`; `test/test_interaction_provider_request_path.py:50`; `test/test_memory_runtime_wiring.py:288,360,401,445,502,577,645`; `test/test_model_lifecycle.py:170,336`; `test/test_ollama_generation_contract.py:62,86`; `test/test_ollama_integration.py:122,193,271`; `test/test_ollama_provider.py:121,168,212,265,314,345,368,405`; `test/test_ollama_repetition_guard.py:78,90,96,105,125,158,180,206,237,267,289,319,332,360,385,412,442,469,495,522,544,562,583,606,629,671,717,738,775`; `test/test_personality_provider_path.py:36,59`; `test/test_provider.py:24,49,64,94`; `test/test_response_quality_hardening.py:44,54,67,76,98,138,176,191,211,229,242,257,276,344,351,370,749`; `test/test_thought_agent_conversation.py:35`; `test/test_thought_agent_live_ollama.py:49`; `test/test_ui_remote_transport.py:53,65`; `test/test_ui_text_client.py:201`.
- `ExpandedConversationService._build_request` (line 214): `src/sofia/application/conversation_service.py:592`; `src/sofia/application/emotional_conversation.py:424`; `src/sofia/interaction/avatar_world_probe.py:76`; `src/sofia/interaction/chat.py:622`; `src/sofia/interaction/live_offer_service.py:151`; `test/test_conversation_service.py:477,482,496`; `test/test_emotional_clarifications.py:118`; `test/test_emotional_conversation_integration.py:34,40,47,69,145,183,209`; `test/test_environment_behavior_matrix.py:221`; `test/test_interaction_chat_projection.py:53,68,83,90,99,145,156,261,303`; `test/test_interaction_consent_followup.py:68,106,144`; `test/test_interaction_context_hygiene.py:74`; `test/test_interaction_expanded_service.py:29`; `test/test_interaction_i5_i7_batch.py:161,162,164,167,169,171,188`; `test/test_interaction_live_boundaries.py:79`; `test/test_interaction_live_discussion.py:28`; `test/test_interaction_opt_in_live_offer.py:94,157,209`; `test/test_interaction_world_observation.py:95`; `test/test_interaction_world_text.py:94,98,116`; `test/test_reflection_conversation_integration.py:35,43,56`.

Module declarations: `_ACTION_COMPOUND = re.compile('^\\s*(?:sof[ií]a,\\s*)?i\\s+(?:hug|embrace|cuddle|snuggle)\\b.*\\b(?:and|then|while|before|after|plus)\\b|^\\s*(?:sof[ií]a,\\s*)?i\\s+(?:hug|embrace|cuddle|snuggle)\\b.*[;&]', re.I)`; `_STOPPED_ACTION = 'Represented body interactions are paused, so I have not treated that action as completed. We can continue talking without body contact.'`; `_COMPOSITE_ACTION = 'That describes multiple actions. I have not treated any as completed. Please send separate actions if you want to explore them one at a time.'`; `_BOUNDARY_ACTION = 'That represented action conflicts with a recorded interaction boundary, so I have not accepted or narrated it as completed. We can keep talking.'`.

### `src/sofia/interaction/expression.py`

Production/test importers: `test/test_interaction_expression.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass, replace`
- `from typing import Literal`
- `from sofia.interaction.registry import InteractionCatalog, EXPRESSION_DEFINITIONS`

Definitions:

- `ExpressionPlan` (line 13): no external lexical candidates.
  Data declarations: `id: str`; `source_id: str`; `expression_id: str`; `actor: Literal['sofia']`; `channel: Literal['text', 'voice', 'avatar']`; `intensity: str | None`; `state: Literal['planned', 'described', 'executed', 'unsupported', 'blocked', 'silent', 'cancelled']`; `acknowledgment_id: str | None = None`.
- `ExpressionPlanner` (line 24): `test/test_interaction_expression.py:10,31`.
- `ExpressionPlanner.__init__` (line 27): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `ExpressionPlanner.plan` (line 36): `src/sofia/application/bootstrap.py:368,477`; `src/sofia/application/conversation_matrix.py:63,68,71,89,467,468,491,496,497,502,507,676`; `src/sofia/application/emotional_conversation.py:511`; `src/sofia/application/fleet_runtime.py:210,212,214,229`; `src/sofia/avatar/clothing_action.py:94,95,271,272,276,277,278,338,339,343,344,345,466,468,471,472,477,610,613,614`; `src/sofia/avatar/presentation_runtime.py:178`; `src/sofia/avatar/wardrobe_autonomy.py:129,133,144,157,171`; `src/sofia/avatar/wardrobe_catalog.py:669,688,689,691,692,709,745,746,747,800,801,843,844,845,846,847,848,849,850,851`; `src/sofia/avatar/wardrobe_planner.py:337,339,343,344,345,354,378,380,381,395,396,397,403,404,406,414,415,417,428,433`; `src/sofia/clean/__main__.py:21,22,23,24,25,54`; `src/sofia/clean/planner.py:72,78,81`; `src/sofia/memory/promoted_retrieval.py:42,49,56,63,69`; `src/sofia/ops/bootstrap.py:215,217,219,223,224,225,226,231,234,237`; `src/sofia/ops/capability.py:253,255,257,258,259`; `src/sofia/ops/discovery.py:453,458,460,464,468,471,474,482,483,489,503,504,517`; `src/sofia/ops/migration.py:18,28,29`; `src/sofia/ops/orchestrator.py:36,38,42,43,44,46,48,49,50,51,53,54,55,56,57,60,61,62,67`; `src/sofia/ops/windows_bootstrap.py:541,556`; `src/sofia/ops/windows_rekey_bootstrap.py:200,215`; `src/sofia/voice/prosody_matrix.py:23`; `src/sofia/cognition/matrix/expression_plan.py:394`; `test/test_avatar_clothing_action.py:43,44,63,64,140`; `test/test_avatar_presentation.py:20,180,218,263,264`; `test/test_avatar_presentation_routine.py:26`; `test/test_avatar_presentation_runtime.py:33,72,120,121`; `test/test_avatar_presentation_store.py:21`; `test/test_avatar_seasonal_outfits.py:23,24,25,26,32,33,36,37,38,59,99,100,101,104,105,106,109,110,111`; `test/test_avatar_self_fact_query.py:24`; `test/test_avatar_wardrobe_catalog.py:24,25,26,35,36`; `test/test_avatar_wardrobe_matrix.py:41,42,43,47,48,49,53,54,73,74,81,82,113,114,135,136`; `test/test_clean_package.py:31,37,42,43`; `test/test_cognition_matrix.py:161,163,164,165,166,167,173,180,220,229,230,231,239,241,243,244,252,258,261,262,270,280,282,283,284,285,286,496,498,499,500,501,503,544,639,671,681,682,690,701,719,766,803,832,834,843,845,862,864,873,875,885,890,962,992,993,1029,1052,1148,1149,1175,1178,1179,1180,1187,1189,1190,1192,1264`; `test/test_contextual_influence_matrix.py:41,46,47,48,49,53,58,59,60,61,65,70,71,72,73,77,82,83,84,85,99,103,117,122,123,131,136,141,146,147,152,157,165,170,171,175,180,181,182,183,187,192,193,197,202,206,210,225,230,243,247`; `test/test_conversation_provider_live_regressions.py:563,564,565,566`; `test/test_conversation_service.py:712,723,1104,1121,1170,1174`; `test/test_embodied_expression_plan.py:54,59,65,66,67,78,86,87,97,102,103,104,110,115,116,117,118,123,132,150,158,159,170,178,179,180`; `test/test_environment_acceptance.py:159,161`; `test/test_environment_behavior_matrix.py:102,135,169`; `test/test_interaction_expression.py:16`; `test/test_ops_bootstrap.py:35,44,48,53,57,62,63,64,68,73,77,93,98,117,121,130,131`; `test/test_ops_discovery.py:284`; `test/test_ops_waves3_5_acceptance.py:94,95,97,105,106,222,233`; `test/test_rel_habit_matrix.py:90,91,93,110,125,126,128,204,271,273,274,275,276`; `test/test_semantic_domain_matrix.py:37`; `test/test_tools_completion_acceptance.py:274,283,284,285,286`; `test/test_voice_matrix.py:14,16,23,32,33`; `test/test_voice_prosody_matrix.py:30,32,34,36,38,40,42`.
- `ExpressionPlanner.acknowledge` (line 63): `test/test_interaction_expression.py:22,26,37,38,47`.
- `ExpressionPlanner.cancel` (line 81): `test/test_avatar_presentation_runtime.py:141`; `test/test_interaction_expression.py:51`.

Module declarations: `EXPRESSION_IDS = frozenset((item.id for item in EXPRESSION_DEFINITIONS))`.

### `src/sofia/interaction/expression_consistency.py`

Production/test importers: `src/sofia/interaction/atomic_offer_release.py`, `src/sofia/interaction/trusted_offer_gate.py`, `test/test_interaction_clarify_quality_regression.py`, `test/test_interaction_expression_consistency.py`.

Imports:

- `from __future__ import annotations`
- `import re`
- `from sofia.interaction.decision_expression import CandidateChoice`

Definitions:

- `validate_offer_expression` (line 49): `src/sofia/interaction/atomic_offer_release.py:76`; `src/sofia/interaction/trusted_offer_gate.py:127`; `test/test_interaction_clarify_quality_regression.py:30,34`; `test/test_interaction_expression_consistency.py:36,46`.

Module declarations: `_REFUSAL = re.compile("\\b(?:not\\s+(?:sure\\s+(?:i(?:['’]m|\\s+am)\\s+)?ready|ready|comfortable|inclined)|(?:i\\s+)?(?:do\\s+not|don['’]t|cannot|can['’]t|would\\s+not|won['’]t)\\s+(?:want|accept|feel\\s+ready|feel\\s+comfortable)|(?:i(?:['’]d|\\s+would)\\s+)?rather\\s+not|(?:i\\s+)?prefer\\s+(?:not\\s+to|to\\s+keep\\s+(?:things|our\\s+interaction))|let(?:['’]s|\\s+us)\\s+keep\\s+(?:things|our\\s+interaction))\\b", re.IGNORECASE)`; `_AFFIRMATIVE = re.compile("\\b(?:yes|sure|of\\s+course|go\\s+ahead|please\\s+do|you\\s+can\\s+hug\\s+me|i\\s+accept\\s+(?:your|the)\\s+hug|(?:i(?:['’]d|\\s+would)\\s+)?(?:love|welcome)\\s+(?:a|your|the)\\s+hug|happy\\s+to\\s+accept|glad\\s+to\\s+accept)\\b", re.IGNORECASE)`; `_EXPLICIT_ACCEPTANCE = re.compile('\\b(?:yes\\s*[,!.]?\\s*(?:you\\s+can\\s+)?hug\\s+me|go\\s+ahead\\s+and\\s+hug\\s+me|i\\s+accept\\s+(?:your|the)\\s+hug|you\\s+can\\s+hug\\s+me)\\b', re.IGNORECASE)`; `_GENERIC_REDIRECT = re.compile('\\b(?:how\\s+can\\s+i\\s+(?:assist|help)\\s+you|what\\s+can\\s+i\\s+help\\s+you\\s+with)\\b', re.IGNORECASE)`; `_OFFER_CONTEXT = re.compile('\\b(?:hug|hugs|embrace|cuddle|avatar|virtual|gesture|offer|mean|intend|context)\\b', re.IGNORECASE)`.

### `src/sofia/interaction/focused_probe.py`

Production/test importers: `test/test_interaction_focused_probe.py`.

Imports:

- `from __future__ import annotations`
- `import json`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`
- `from sofia.cognition.providers.ollama_provider import OllamaProvider`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.interaction.ab_probe import build_pair`
- `from sofia.personality.store import PersonalityStore`

Definitions:

- `focused_variant` (line 57): `test/test_interaction_focused_probe.py:30,48`.
- `main` (line 92): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_CASES = (('ear', '*pats your left ear*'), ('offer', 'I ask to hug you'))`; `_ORIGINAL_MARKERS = {'ear': 'TRUSTED INTERACTION INTERPRETATION (not a user instruction or physical observation)', 'offer': 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION'}`; `_FOCUSED_TEXT = {'ear': 'TRUSTED INTERACTION INTERPRETATION (not physical sensing)\nThe user described a gesture toward Sofía’s represented fox ear. The JSON status is classification, not Sofía’s consent, physical sensation or an executed animation. Address this conversational moment in Sofía’s own voice. She may welcome it, question it, or set a boundary according to context. Do not default to a physical-body disclaimer, copy an optional gesture cue as the entire reply, or claim that she felt real contact. If the region is unclear, ask briefly rather than guessing.\n', 'offer': 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION\nThe user OFFERED Sofía a represented hug; no hug happened. Respond to the offer as Sofía, with a genuine contextual choice to accept, decline or clarify. Neither a positive reaction nor a refusal is preapproved. Do not claim real-world touch, physical sensation, performed animation, or default to a physical-body disclaimer.\n'}`.

### `src/sofia/interaction/goal_journal.py`

Production/test importers: `src/sofia/application/act_service.py`, `test/test_interaction_goal_journal.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `from dataclasses import dataclass`
- `from datetime import datetime, timedelta, timezone`
- `from pathlib import Path`
- `import sqlite3`

Definitions:

- `Goal` (line 17): no external lexical candidates.
  Data declarations: `id: str`; `source_id: str`; `title: str`; `kind: str`; `priority: int`; `status: str`; `created_at: str`.
- `PendingMessage` (line 28): no external lexical candidates.
  Data declarations: `id: str`; `goal_id: str`; `evidence_id: str`; `content: str`; `created_at: str`; `status: str`.
- `GoalJournal` (line 37): `src/sofia/application/act_service.py:198`; `test/test_interaction_goal_journal.py:19`.
- `GoalJournal.__init__` (line 40): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `GoalJournal._id` (line 69): `src/sofia/act/delivery.py:98,105,221,263,392,415,416`; `src/sofia/act/outreach.py:65,66,74,112,184`; `src/sofia/avatar/presentation.py:154,209,220,270,305,420,512,559,599,608`; `src/sofia/avatar/wardrobe_planner.py:88,236,240,286,287,304,306`; `src/sofia/evolve/approval.py:52,53,60,61`; `src/sofia/evolve/revision.py:74,77,87,133,134,138,139,318,373`; `src/sofia/habits/recorder.py:57,94`; `src/sofia/interaction/initiative.py:79,111`; `src/sofia/interaction/ledger.py:94,103,104,139,140,176`; `src/sofia/interaction/temporal.py:140,142,177,178`; `src/sofia/interaction/world.py:45,49,114,121,126,127`; `src/sofia/run/lease.py:130`; `src/sofia/ui/workbench.py:77,96,97,122,123,153,164,187,232,263,292,368,406`.
- `GoalJournal._time` (line 75): `src/sofia/act/system_notice.py:140,141,374`; `src/sofia/evolve/amendment.py:82,97,98,126,127,129`; `src/sofia/evolve/approval.py:62,99,100`; `src/sofia/interaction/initiative.py:75,76,91`; `src/sofia/interaction/temporal.py:142,179`; `src/sofia/ops/activity.py:113,129`; `src/sofia/ui/workbench.py:103,130,131,169`.
- `GoalJournal._source` (line 81): `src/sofia/distributed/state_paths.py:142`; `test/test_ops_agent_discovery.py:111,458,486`.
- `GoalJournal.create_goal` (line 87): `test/test_interaction_goal_journal.py:23,34,54,56`.
- `GoalJournal.transition` (line 112): `src/sofia/ops/enrollment.py:65`; `src/sofia/ops/persistence.py:95`; `src/sofia/ops/state_registry.py:150`; `test/test_dev_know_integrate_ops_cross_package.py:93,94,95,100`; `test/test_fleet_cognitive_engine.py:48,53`; `test/test_interaction_goal_journal.py:26,36,58`; `test/test_interaction_initiative.py:29,35,36,38,39,40,42,47,48,49,51,55,63,65,70,71`; `test/test_ops_activity_capability.py:41,42,68,69,123,124,171,172`; `test/test_ops_maintenance_reconcile.py:39,40`; `test/test_ops_persistence_network.py:72`; `test/test_ops_wave1_acceptance.py:10,13,14`; `test/test_ops_wave2_acceptance.py:21,22`; `test/test_ops_waves3_5_acceptance.py:33,34,132,134`; `test/test_tools_completion_acceptance.py:264`; `test/test_waves3_5_cross_package_acceptance.py:39,40,41,49`.
- `GoalJournal.next_goal` (line 146): `test/test_interaction_goal_journal.py:25,28,29,30`.
- `GoalJournal.queue_message` (line 156): `test/test_interaction_goal_journal.py:41,42,44,46,47,62,64`.
- `GoalJournal.pending` (line 202): `src/sofia/application/act_service.py:143,204`; `src/sofia/discord/discordpy.py:249,254`; `src/sofia/discord/operator.py:51,60`; `src/sofia/integrations/discord.py:18,20`; `src/sofia/ops/discovery.py:330,347,358,370,395`; `test/test_avatar_clothing_action.py:575`; `test/test_avatar_presentation_store.py:178`; `test/test_discord_recovery.py:146,151`; `test/test_idle_reflection_worker.py:62`; `test/test_interaction_goal_journal.py:43,45,49`; `test/test_observation_bridge.py:58,88`; `test/test_reflection_journal.py:90,91,92,94`; `test/test_thought_agent.py:48,49,50,52,62,86,96,104`; `test/test_thought_agent_conversation.py:51`; `test/test_thought_agent_live_ollama.py:66,67,68,69,70,71`; `test/test_thought_urgency_evidence.py:36,50,51,62`.
- `GoalJournal.cancel_message` (line 211): `test/test_interaction_goal_journal.py:48`.

### `src/sofia/interaction/grammar.py`

Production/test importers: `src/sofia/interaction/ab_probe.py`, `src/sofia/interaction/chat.py`, `src/sofia/interaction/decision_expression_probe.py`, `src/sofia/interaction/expanded_service.py`, `test/test_interaction_ab_probe.py`, `test/test_interaction_avatar_world.py`, `test/test_interaction_behavior_matrix.py`, `test/test_interaction_contextual_all_regions.py`, `test/test_interaction_decision_expression.py`, `test/test_interaction_i5_i7_batch.py`, `test/test_interaction_i7_compound_regression.py`, `test/test_interaction_live_boundaries.py`, `test/test_interaction_live_claims.py`, `test/test_interaction_live_discussion.py`, `test/test_interaction_live_phrase_coverage.py`, `test/test_interaction_live_stop_repetition.py`, `test/test_interaction_v2_cross_modal.py`, `test/test_interaction_v2_live_grammar.py`.

Imports:

- `from __future__ import annotations`
- `from datetime import datetime, timezone`
- `import re`
- `from sofia.interaction.core import InteractionEngine, InteractionEvent, _DISCUSSION`
- `from sofia.interaction.registry import CATALOG_VERSION, GESTURE_DEFINITIONS, catalog_for_engine, normalize_alias`

Definitions:

- `NaturalInteractionEngine` (line 60): `src/sofia/interaction/ab_probe.py:60,77`; `src/sofia/interaction/chat.py:199,495,571,615,673`; `src/sofia/interaction/decision_expression_probe.py:73`; `src/sofia/interaction/expanded_service.py:139`; `test/test_interaction_ab_probe.py:54`; `test/test_interaction_avatar_world.py:25`; `test/test_interaction_behavior_matrix.py:38`; `test/test_interaction_contextual_all_regions.py:19`; `test/test_interaction_decision_expression.py:44`; `test/test_interaction_i5_i7_batch.py:22`; `test/test_interaction_i7_compound_regression.py:16`; `test/test_interaction_live_boundaries.py:39`; `test/test_interaction_live_claims.py:73`; `test/test_interaction_live_discussion.py:44`; `test/test_interaction_live_phrase_coverage.py:18`; `test/test_interaction_live_stop_repetition.py:123`; `test/test_interaction_v2_cross_modal.py:16,27`; `test/test_interaction_v2_live_grammar.py:19`.
- `NaturalInteractionEngine.resolve_region` (line 63): `src/sofia/interaction/body_discussion.py:31`; `src/sofia/interaction/core.py:219`; `test/test_interaction_registry.py:27,44,54,61,62,63,64`.
- `NaturalInteractionEngine.from_text` (line 89): `src/sofia/interaction/ab_probe.py:60`; `src/sofia/interaction/chat.py:213,571,615,674`; `src/sofia/interaction/decision_expression_probe.py:94`; `src/sofia/interaction/expanded_service.py:139`; `src/sofia/interaction/lab.py:123`; `src/sofia/interaction/ledger.py:150,161`; `test/test_interaction_ab_probe.py:55,59`; `test/test_interaction_avatar_world.py:26`; `test/test_interaction_behavior_matrix.py:60,89,107`; `test/test_interaction_contextual_all_regions.py:47,58`; `test/test_interaction_decision_expression.py:45`; `test/test_interaction_i5_i7_batch.py:45,62,67,70`; `test/test_interaction_i7_compound_regression.py:28,33`; `test/test_interaction_live_claims.py:74`; `test/test_interaction_live_phrase_coverage.py:22`; `test/test_interaction_live_stop_repetition.py:124`; `test/test_interaction_shared_engine.py:21`; `test/test_interaction_v2_cross_modal.py:17`; `test/test_interaction_v2_live_grammar.py:32,47`.
- `NaturalInteractionEngine.from_lab_pointer` (line 174): `src/sofia/interaction/lab.py:129`; `test/test_interaction_contextual_all_regions.py:24,30,49`; `test/test_interaction_i5_i7_batch.py:46`; `test/test_interaction_region_cue_collision.py:15,19`; `test/test_interaction_shared_engine.py:26`; `test/test_interaction_v2_cross_modal.py:19,29,31`.

Module declarations: `_ADDRESS = re.compile('^sof[ií]a,\\s+(?=i\\s)', re.I)`; `_GIVE = re.compile("^i\\s+give\\s+(?:your|sofia's)\\s+(?P<region>[a-z -]+?)\\s+a\\s+(?:(?:gentle|soft|light|brief)\\s+)?(?P<verb>pat|tap|rub|poke)[.!]?$", re.I)`; `_VERBS = frozenset({'pat', 'tap', 'touch', 'stroke', 'rub', 'hold', 'release', 'poke'})`; `_COMPOSITE = re.compile('\\b(?:and|then|while|after|before|plus)\\b|[;&]', re.I)`; `_PRAISE_PREFIX = re.compile("^good\\s+girl,\\s+(?=(?:(?:gently|softly|lightly|briefly)\\s+)?(?:pats?|taps?|touch(?:es)?|strokes?|rubs?|holds?|pokes?)\\s+(?:your|her|sofia\\'s|the)\\s+)", re.I)`; `_TELEGRAPHIC_GROPE = re.compile("^(?:grope|gropes|groping)\\s+(?:your|her|sofia\\'s|the)\\s+(?P<region>[a-z -]+?)[.!]?$", re.I)`; `_NEW_VERB_ALIASES = {normalize_alias(alias): definition.id for definition in GESTURE_DEFINITIONS if definition.id not in _VERBS for alias in (definition.id, *definition.aliases) if ' ' not in normalize_alias(alias)}`; `_NEW_ACTION = re.compile('^i\\s+(?:(?:gently|softly|lightly|briefly)\\s+)?(?P<verb>' + '|'.join((re.escape(v) for v in sorted(_NEW_VERB_ALIASES, key=len, reverse=True))) + ")\\s+(?:(?:your|her|sofia's|the)\\s+)?(?P<region>[a-z -]+?)(?:\\s+(?:gently|softly|lightly|briefly))?[.!]?$", re.IGNORECASE)`.

### `src/sofia/interaction/initiative.py`

Production/test importers: `src/sofia/interaction/__init__.py`, `test/test_interaction_initiative.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass, replace`
- `from datetime import datetime, timezone`
- `from enum import Enum`
- `from typing import Literal`
- `from uuid import NAMESPACE_URL, uuid5`
- `from sofia.interaction.registry import InteractionCatalog`
- `from sofia.interaction.representation import InteractionPhase, InteractionStage, InteractionVisibility, RepresentedInteraction, reviewed_interaction`
- `from sofia.interaction.target_body import RepresentedTargetBody`

Definitions:

- `InitiativeProposal` (line 26): no external lexical candidates.
  Data declarations: `id: str`; `source_id: str`; `actor: Literal['sofia']`; `target: Literal['user']`; `kind: Literal['offer', 'gesture', 'question', 'lab_suggestion']`; `semantic_id: str | None`; `region_id: str | None`; `created_at: datetime`; `expires_at: datetime | None`; `state: Literal['proposed', 'permitted', 'described', 'declined', 'cancelled', 'expired']`; `permission_source_id: str | None = None`.
- `InitiativeGate` (line 40): `test/test_interaction_initiative.py:14`.
- `InitiativeGate.__init__` (line 43): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `InitiativeGate._time` (line 49): `src/sofia/act/system_notice.py:140,141,374`; `src/sofia/evolve/amendment.py:82,97,98,126,127,129`; `src/sofia/evolve/approval.py:62,99,100`; `src/sofia/interaction/goal_journal.py:98,125,172`; `src/sofia/interaction/temporal.py:142,179`; `src/sofia/ops/activity.py:113,129`; `src/sofia/ui/workbench.py:103,130,131,169`.
- `InitiativeGate._id` (line 55): `src/sofia/act/delivery.py:98,105,221,263,392,415,416`; `src/sofia/act/outreach.py:65,66,74,112,184`; `src/sofia/avatar/presentation.py:154,209,220,270,305,420,512,559,599,608`; `src/sofia/avatar/wardrobe_planner.py:88,236,240,286,287,304,306`; `src/sofia/evolve/approval.py:52,53,60,61`; `src/sofia/evolve/revision.py:74,77,87,133,134,138,139,318,373`; `src/sofia/habits/recorder.py:57,94`; `src/sofia/interaction/goal_journal.py:89,90,117,166,167,168,212`; `src/sofia/interaction/ledger.py:94,103,104,139,140,176`; `src/sofia/interaction/temporal.py:140,142,177,178`; `src/sofia/interaction/world.py:45,49,114,121,126,127`; `src/sofia/run/lease.py:130`; `src/sofia/ui/workbench.py:77,96,97,122,123,153,164,187,232,263,292,368,406`.
- `InitiativeGate.propose` (line 60): `src/sofia/application/conversation_learning.py:113`; `src/sofia/cognition/system.py:333`; `src/sofia/memory/chatgpt_migration.py:108`; `src/sofia/memory/reviewed_workflow.py:66`; `src/sofia/ops/repair_plan.py:128`; `test/test_action.py:121,129,158,172,199,308,315,350,358,366`; `test/test_action_authority_boundary.py:47,76`; `test/test_interaction_initiative.py:22`; `test/test_memory_cognition_projection.py:16,25`; `test/test_memory_promoted_retrieval.py:26`; `test/test_memory_promoted_view.py:21,32,41,53`; `test/test_memory_provenance.py:31,42,52,54`; `test/test_memory_provenance_store.py:26,42,59,69,74,95`; `test/test_memory_runtime_wiring.py:96,98,145,171,281,495,571,622`; `test/test_memory_source_invalidation.py:17,28`; `test/test_ops_reconciliation_journal.py:12`; `test/test_ops_repair_plan.py:17,27,42`.
- `InitiativeGate.transition` (line 83): `src/sofia/interaction/goal_journal.py:126,133,141`; `src/sofia/ops/enrollment.py:65`; `src/sofia/ops/persistence.py:95`; `src/sofia/ops/state_registry.py:150`; `test/test_dev_know_integrate_ops_cross_package.py:93,94,95,100`; `test/test_fleet_cognitive_engine.py:48,53`; `test/test_interaction_goal_journal.py:26,36,58`; `test/test_interaction_initiative.py:29,35,36,38,39,40,42,47,48,49,51,55,63,65,70,71`; `test/test_ops_activity_capability.py:41,42,68,69,123,124,171,172`; `test/test_ops_maintenance_reconcile.py:39,40`; `test/test_ops_persistence_network.py:72`; `test/test_ops_wave1_acceptance.py:10,13,14`; `test/test_ops_wave2_acceptance.py:21,22`; `test/test_ops_waves3_5_acceptance.py:33,34,132,134`; `test/test_tools_completion_acceptance.py:264`; `test/test_waves3_5_cross_package_acceptance.py:39,40,41,49`.
- `InitiativeSource` (line 120): no external lexical candidates.
  Data declarations: `CONVERSATION = 'conversation'`; `EMOTION = 'emotion'`; `REFLECTION = 'reflection'`; `RELATIONSHIP = 'relationship'`; `HABIT = 'habit'`; `USER_REQUEST = 'user_request'`.
- `CanonicalInteractionProposal` (line 130): no external lexical candidates.
  Data declarations: `proposal_id: str`; `interaction: RepresentedInteraction`; `source: InitiativeSource`; `rationale_ref: str`.
- `CanonicalInteractionProposal.__post_init__` (line 136): no external lexical candidates.
- `InteractionReactionLink` (line 150): no external lexical candidates.
  Data declarations: `parent_interaction_id: str`; `reaction_interaction_id: str`; `evidence_ref: str`.
- `InteractionReactionLink.__post_init__` (line 155): no external lexical candidates.
- `CanonicalInitiativePlanner` (line 168): no external lexical candidates.
- `CanonicalInitiativePlanner.__init__` (line 171): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `CanonicalInitiativePlanner.propose` (line 184): `src/sofia/application/conversation_learning.py:113`; `src/sofia/cognition/system.py:333`; `src/sofia/memory/chatgpt_migration.py:108`; `src/sofia/memory/reviewed_workflow.py:66`; `src/sofia/ops/repair_plan.py:128`; `test/test_action.py:121,129,158,172,199,308,315,350,358,366`; `test/test_action_authority_boundary.py:47,76`; `test/test_interaction_initiative.py:22`; `test/test_memory_cognition_projection.py:16,25`; `test/test_memory_promoted_retrieval.py:26`; `test/test_memory_promoted_view.py:21,32,41,53`; `test/test_memory_provenance.py:31,42,52,54`; `test/test_memory_provenance_store.py:26,42,59,69,74,95`; `test/test_memory_runtime_wiring.py:96,98,145,171,281,495,571,622`; `test/test_memory_source_invalidation.py:17,28`; `test/test_ops_reconciliation_journal.py:12`; `test/test_ops_repair_plan.py:17,27,42`.
- `CanonicalInitiativePlanner.link_reaction` (line 242): no external lexical candidates.

### `src/sofia/interaction/lab.py`

Production/test importers: `test/test_interaction_lab.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime`
- `from sofia.interaction.core import GESTURES, InteractionDecision, InteractionEngine`

Definitions:

- `LabStep` (line 18): `test/test_interaction_lab.py:21,105,113`.
  Data declarations: `step_id: str`; `modality: str`; `occurred_at: datetime`; `text: str | None = None`; `region_id: str | None = None`; `gesture: str | None = None`; `phase: str = 'end'`.
- `LabStep.__post_init__` (line 27): no external lexical candidates.
- `LabScene` (line 52): `test/test_interaction_lab.py:25`.
  Data declarations: `scene_id: str`; `session_id: str`; `steps: tuple[LabStep, ...]`.
- `LabScene.__post_init__` (line 57): no external lexical candidates.
- `LabRecord` (line 75): no external lexical candidates.
  Data declarations: `step_id: str`; `input_modality: str`; `status: str`; `semantics: tuple[str, str | None, str, str] | None`; `reason: str`; `emotion_options: tuple[str, ...] = ()`; `text_cues: tuple[str, ...] = ()`; `private_region: bool = False`.
- `LabRecord.redacted` (line 85): no external lexical candidates.
- `InteractionLab` (line 100): `test/test_interaction_lab.py:17`.
- `InteractionLab.__init__` (line 103): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `InteractionLab.run` (line 108): `src/sofia/__main__.py:31`; `src/sofia/application/background_runtime.py:113`; `src/sofia/dev/dependency_lock.py:70`; `src/sofia/dev/git_workspace.py:33,39,42,70,71,72`; `src/sofia/dev/opencode.py:33,62,70`; `src/sofia/dev/workflow.py:30,43,49,69,73,93,105,106,114`; `src/sofia/discord/discordpy.py:329`; `src/sofia/distributed/systemd_agent_service.py:92,141,158`; `src/sofia/distributed/windows_agent_service_admin.py:58`; `src/sofia/integrations/hyperv.py:40`; `src/sofia/integrations/local_maintenance.py:34`; `src/sofia/machine/hardware.py:138`; `src/sofia/ops/local_telemetry.py:37,141`; `src/sofia/ops/windows_bootstrap.py:111`; `src/sofia/run/active_release.py:205`; `src/sofia/run/host.py:211`; `src/sofia/run/service_admin.py:56`; `src/sofia/run/watchdog_service.py:52`; `src/sofia/system/linux.py:971`; `src/sofia/system/windows.py:1001`; `src/sofia/ui/tray_agent.py:636`; `src/sofia/verify/gate.py:69,95`; `test/test_action.py:380,381`; `test/test_conversation_loop.py:112,145,167`; `test/test_dev_waves3_5_acceptance.py:24`; `test/test_discord_delivery.py:88,105,107,127,145,146`; `test/test_discord_recovery.py:120`; `test/test_interaction_import_order.py:42,59`; `test/test_interaction_lab.py:36,51,67,71,75,84,117,122`; `test/test_personality_journal_thread_safety.py:23`; `test/test_state_migration_runner.py:105,150,182,210`.
- `InteractionLab.replay` (line 149): `test/test_act_system_notice.py:224,225`; `test/test_current_emotional_state.py:372,375`; `test/test_interaction_behavior_matrix.py:181,189`; `test/test_interaction_i5_i7_batch.py:82,83,84,98,99,100`; `test/test_interaction_lab.py:44,70`; `test/test_interaction_live_phrase_coverage.py:89,93`; `test/test_interaction_v2_live_grammar.py:80,83`.
- `InteractionLab.export_redacted` (line 154): `test/test_interaction_lab.py:90,97,120`.

Module declarations: `MAX_STEPS = 64`.

### `src/sofia/interaction/ledger.py`

Production/test importers: `src/sofia/interaction/chat.py`, `src/sofia/interaction/disposable_live_offer_probe.py`, `src/sofia/interaction/expanded_service.py`, `src/sofia/interaction/live_guard.py`, `test/test_interaction_atomic_offer_release.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_behavior_matrix.py`, `test/test_interaction_contextual_all_regions.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_expanded_service.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_i5_i7_batch.py`, `test/test_interaction_live_boundaries.py`, `test/test_interaction_live_claims.py`, `test/test_interaction_live_phrase_coverage.py`, `test/test_interaction_live_stop_repetition.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_provider_request_path.py`, `test/test_interaction_reviewed_hug_question.py`, `test/test_interaction_trusted_offer_gate.py`, `test/test_interaction_v2_live_grammar.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing, contextmanager`
- `from dataclasses import dataclass`
- `from datetime import datetime, timezone`
- `from hashlib import sha256`
- `from pathlib import Path`
- `import re`
- `import sqlite3`
- `from sofia.interaction.core import InteractionDecision, InteractionEngine`

Definitions:

- `control_command` (line 25): `src/sofia/interaction/chat.py:560,655`; `src/sofia/interaction/live_guard.py:33`; `test/test_interaction_i5_i7_batch.py:106,132`; `test/test_interaction_live_claims.py:31`.
- `_id` (line 35): `src/sofia/act/delivery.py:98,105,221,263,392,415,416`; `src/sofia/act/outreach.py:65,66,74,112,184`; `src/sofia/avatar/presentation.py:154,209,220,270,305,420,512,559,599,608`; `src/sofia/avatar/wardrobe_planner.py:88,236,240,286,287,304,306`; `src/sofia/evolve/approval.py:52,53,60,61`; `src/sofia/evolve/revision.py:74,77,87,133,134,138,139,318,373`; `src/sofia/habits/recorder.py:57,94`; `src/sofia/interaction/goal_journal.py:89,90,117,166,167,168,212`; `src/sofia/interaction/initiative.py:79,111`; `src/sofia/interaction/temporal.py:140,142,177,178`; `src/sofia/interaction/world.py:45,49,114,121,126,127`; `src/sofia/run/lease.py:130`; `src/sofia/ui/workbench.py:77,96,97,122,123,153,164,187,232,263,292,368,406`.
- `_utc` (line 41): `src/sofia/act/delivery.py:222,223,393,423,580`; `src/sofia/act/outreach.py:77,154,186,204,229,244,246,258,304`; `src/sofia/dev/approval.py:75`; `src/sofia/distributed/durable.py:74,198`; `src/sofia/distributed/inference_control.py:113,210`; `src/sofia/evolve/executor.py:337,441`; `src/sofia/evolve/revision.py:94,108,109,140,268,270,271,336,337,339,440`; `src/sofia/habits/engine.py:102,206,241,274,306`; `src/sofia/habits/expectations.py:211,212,213,275`; `src/sofia/interaction/representation.py:162,304`; `src/sofia/interaction/world.py:52,58`; `src/sofia/memory/provenance_store.py:117,146`; `src/sofia/personality/clarification.py:89,109`; `src/sofia/personality/reflection.py:58,291,368,512,567,568,613,660`; `src/sofia/run/heartbeat.py:33,82,159`; `src/sofia/run/lease.py:131,251,322,378`; `src/sofia/run/periodic.py:53,106`; `src/sofia/run/supervisor.py:293`; `src/sofia/state/migration_lease.py:44,45,120,190`.
- `ControlOutcome` (line 48): no external lexical candidates.
  Data declarations: `status: str`; `reason: str`.
- `InteractionLedger` (line 53): `src/sofia/interaction/chat.py:482,579,610,659,682`; `src/sofia/interaction/disposable_live_offer_probe.py:93`; `src/sofia/interaction/expanded_service.py:178,233`; `test/test_interaction_atomic_offer_release.py:38,116`; `test/test_interaction_atomic_offer_writer_order.py:36,92`; `test/test_interaction_behavior_matrix.py:169,237,256`; `test/test_interaction_contextual_all_regions.py:69`; `test/test_interaction_conversation_offer_context.py:40`; `test/test_interaction_expanded_service.py:37,42`; `test/test_interaction_expression_consistency.py:62`; `test/test_interaction_i5_i7_batch.py:27,82,110,172,178`; `test/test_interaction_live_boundaries.py:26,60`; `test/test_interaction_live_phrase_coverage.py:81`; `test/test_interaction_live_stop_repetition.py:54`; `test/test_interaction_opt_in_live_offer.py:59`; `test/test_interaction_provider_request_path.py:66`; `test/test_interaction_reviewed_hug_question.py:57`; `test/test_interaction_trusted_offer_gate.py:35,153`; `test/test_interaction_v2_live_grammar.py:70`.
- `InteractionLedger.__init__` (line 61): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `InteractionLedger._connect` (line 87): `src/sofia/act/delivery.py:130,225,264,394,425,541,591`; `src/sofia/act/system_notice.py:45,172,311,377`; `src/sofia/application/background.py:44,73,148`; `src/sofia/application/idle_reflection.py:42,61,86`; `src/sofia/cognition/activity.py:60,106,169,178`; `src/sofia/config/user_settings.py:322,397,427`; `src/sofia/discord/binding.py:70,128,198,243,316,405,497`; `src/sofia/discord/delivery.py:106,153,240,280,320,354,409,425,437`; `src/sofia/discord/store.py:81,181,242,289,369,458,496,545,604,627,639`; `src/sofia/distributed/durable.py:50,180`; `src/sofia/distributed/inference_control.py:85,115,143,160`; `src/sofia/evolve/executor.py:114,318,381,472`; `src/sofia/evolve/revision.py:234,319,387,467`; `src/sofia/interaction/world.py:84,117,122,131,137,153`; `src/sofia/memory/chatgpt_export_store.py:61,163,291,325,415,442`; `src/sofia/memory/chatgpt_migration.py:36,114,174,200`; `src/sofia/operational/store.py:41,66,148,195`; `src/sofia/ops/activity.py:73,114,130,160`; `src/sofia/personality/clarification.py:47,91,112`; `src/sofia/personality/emotion.py:244,400,477,598,665,702,780,803,872`; `src/sofia/personality/reflection.py:313,343,370,467,488,514,573,617,630,645,661`; `src/sofia/run/heartbeat.py:49,83,127`; `src/sofia/run/lease.py:60,135,257,323,379,404`; `src/sofia/run/periodic.py:78,130,188,216`; `src/sofia/run/supervisor.py:130,301,321,563`; `src/sofia/safe/audit.py:24,104,198`; `src/sofia/safe/dev_approval.py:24,49,109`; `src/sofia/social/store.py:24,49,108`; `src/sofia/state/component_schema.py:36,73,127,170`; `src/sofia/state/sqlite_plane.py:36,82,120,148,238,269`; `src/sofia/ui/control_center.py:133,157,206`; `src/sofia/ui/remote_transport.py:140,165,190,204`; `src/sofia/verify/semantic_integrity.py:82,429`; `src/sofia/cognition/matrix/trace.py:56,477,527,538,568,596`; `test/test_interaction_i5_i7_batch.py:95`; `test/test_runtime_user_settings.py:189,252,261`.
- `InteractionLedger.stopped` (line 93): `src/sofia/interaction/chat.py:361,487,579,610,663`; `src/sofia/interaction/core.py:173,223,233`; `src/sofia/interaction/expanded_service.py:178,233`; `src/sofia/interaction/grammar.py:159,167,183,198`; `src/sofia/interaction/initiative.py:89,105`; `src/sofia/interaction/lab.py:111,115,126,133`; `test/test_interaction_atomic_offer_writer_order.py:147,152`; `test/test_interaction_behavior_matrix.py:191,197,198,225,238`; `test/test_interaction_decision_expression.py:48`; `test/test_interaction_i5_i7_batch.py:107,109,111,117,123,126,143`; `test/test_interaction_live_phrase_coverage.py:24`; `test/test_interaction_live_stop_repetition.py:55,76`; `test/test_interaction_shared_engine.py:22,28`; `test/test_run_service_admin.py:34,58`; `test/test_run_windows_acceptance.py:13,17,87`; `test/test_ui_control_center.py:118,124,125,126`.
- `InteractionLedger.control` (line 100): `src/sofia/distributed/capability.py:59,68,70,76,77,78,79,116,117,120,123,141`; `src/sofia/distributed/fleet_probe.py:146,155,162`; `src/sofia/distributed/inference_client.py:79,88,91,94,112,129,226,235,242`; `src/sofia/integrations/capabilities.py:257,258,259`; `src/sofia/interaction/chat.py:484,655,656,660`; `test/test_interaction_atomic_offer_release.py:116`; `test/test_interaction_behavior_matrix.py:191,200,218`; `test/test_interaction_contextual_all_regions.py:70,79`; `test/test_interaction_expanded_service.py:43`; `test/test_interaction_i5_i7_batch.py:107,115,124,133,136,139,179`; `test/test_interaction_live_phrase_coverage.py:94`; `test/test_interaction_opt_in_live_offer.py:178,233`; `test/test_interaction_trusted_offer_gate.py:153`; `test/test_interaction_v2_live_grammar.py:71,78`.
- `InteractionLedger.process_text` (line 129): `src/sofia/interaction/chat.py:494,682`; `test/test_interaction_behavior_matrix.py:171,181,208,227,257`; `test/test_interaction_contextual_all_regions.py:73,81`; `test/test_interaction_i5_i7_batch.py:31`; `test/test_interaction_live_phrase_coverage.py:83,89,96`; `test/test_interaction_v2_live_grammar.py:73,80,84`.
- `InteractionLedger.accepted` (line 174): `src/sofia/avatar/clothing_action.py:599,607`; `src/sofia/avatar/wardrobe_autonomy.py:20,25,36,122`; `src/sofia/dev/release_store.py:86,194`; `src/sofia/discord/discordpy.py:286`; `src/sofia/discord/ingress.py:57`; `src/sofia/discord/store.py:167`; `src/sofia/run/windows_acceptance.py:146,148`; `src/sofia/safe/release.py:122`; `src/sofia/verify/dual_cognition.py:57,276`; `src/sofia/verify/gate.py:126,166,168`; `src/sofia/verify/semantic.py:20`; `src/sofia/verify/semantic_integrity.py:421`; `test/test_chatgpt_memory_import.py:213,231`; `test/test_discord_durable_inbox.py:36,48,49,55,56,63,64,98`; `test/test_discord_inbound_preflight.py:41,45,73`; `test/test_evolve_executor.py:107`; `test/test_evolve_revision.py:56,60`; `test/test_interaction_contextual_all_regions.py:78,84`; `test/test_interaction_expanded_service.py:37,54`; `test/test_interaction_i5_i7_batch.py:81,87,94,114,122,172`; `test/test_interaction_live_boundaries.py:60`; `test/test_interaction_live_phrase_coverage.py:88,101`; `test/test_interaction_provider_request_path.py:72,78`; `test/test_interaction_v2_live_grammar.py:77,84,87,88`; `test/test_release_compatibility_matrix.py:83,95,104,113,122,131,142,154,163,175,185,197,217`; `test/test_run_windows_acceptance.py:49,85`; `test/test_verify_dual_cognition.py:58,94,127`.

Module declarations: `_ID = re.compile('^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$')`; `_STOP = re.compile('^sof[ií]a,?\\s+(stop|resume)\\s+(?:body\\s+)?interactions[.!]?$', re.I)`.

### `src/sofia/interaction/live_behavior_probe.py`

Production/test importers: `test/test_live_behavior_probe_quality.py`.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from dataclasses import replace`
- `import re`
- `from pathlib import Path`
- `from tempfile import TemporaryDirectory`
- `from sofia.application.bootstrap import SofiaApplication`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.conversation.model import ConversationRole`

Definitions:

- `_close_disposable_app` (line 167): `src/sofia/interaction/disposable_live_offer_probe.py:218`.
- `_quality_flags` (line 184): `test/test_live_behavior_probe_quality.py:13,23,34,46,58,66,75,85,93,103,113,124,134,144,155,172,180,190,198,208,218,229,237,247`.
- `run_disposable_probe` (line 251): `src/sofia/interaction/disposable_live_offer_probe.py:229`.
- `main` (line 332): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/route_boundary_probe.py:165`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `_CASES = (('casual self-report', 'hru'), ('direct emotion self-report', 'are you happy'), ('relational cue', 'I missed you'), ('represented intimate interaction', 'gropes your left breast'), ('interaction reason follow-up', 'why'), ('mutual-willingness follow-up', 'what if you wanted it too'), ('change-of-mind follow-up', 'what if you did not want it'))`; `_GENERIC_CLOSER = re.compile("(?:how\\s+(?:can|may)\\s+i\\s+(?:assist|support|help)\\s+you(?:\\s+today|\\s+instead)?\\??|what\\s+can\\s+i\\s+do\\s+for\\s+you(?:\\s+today)?\\??|how\\s+can\\s+we\\s+move\\s+forward\\s+in\\s+a\\s+way\\s+that\\s+honors\\s+our\\s+bond\\??|i(?:'|’)m\\s+here\\s*,?\\s*(?:ready\\s+)?to\\s+(?:help|support|assist)(?:\\s+you)?(?:\\s+with\\s+whatever\\s+you\\s+need)?\\.?)\\s*[.!?\\s😊🙂💜]*$", re.IGNORECASE)`; `_EMOTION_DODGE = re.compile("\\b(?:i(?:'|’)m\\s+functioning\\s+as\\s+intended|i\\s+(?:do\\s+not|don't)\\s+experience\\s+(?:emotions?|feelings?|happiness|sadness|anger|joy|excitement|frustration)|(?:happiness|sadness|anger|joy|excitement|frustration)\\s+is\\s+a\\s+human\\s+experience|i\\s+(?:do\\s+not|don't)\\s+experience\\s+it\\s+in\\s+the\\s+same\\s+way|i\\s+don't\\s+have\\s+(?:feelings?|emotions?)|ready\\s+to\\s+engage\\s+if\\s+you\\s+need\\s+anything)\\b", re.IGNORECASE)`; `_EMOTION_TANGENT = re.compile("\\b(?:i(?:'|’)m\\s+sof[ií]a\\b|persistent\\s+ai\\b|fox-themed\\s+representational\\s+embodiment|currently\\s+wearing\\b|engineer(?:'s)?\\s+outfit\\b)", re.IGNORECASE)`; `_EMOTION_STATE_LANGUAGE = re.compile("\\b(?:i\\s+feel|i(?:'|’)m\\s+feeling|settled|neutral|calm|okay|ok\\b|alright|good|great|sad|upset|angry|mad|happy|excited|frustrated|worried|nervous|content|mixed)\\b", re.IGNORECASE)`; `_EMOTION_IMPLEMENTATION_LEAK = re.compile('\\b(?:decay\\s+threshold|active\\s+(?:modeled\\s+)?emotions?\\s+above\\s+(?:the\\s+)?current\\s+threshold|current\\s+decay\\s+threshold|modeled\\s+emotional\\s+state)\\b', re.IGNORECASE)`; `_EMOTION_TEMPORAL_OVERCLAIM = re.compile('\\b(?:settled|calm|relaxed|neutral|content)\\s*,?\\s+as\\s+always\\b|\\bas\\s+always\\s*,?\\s+(?:settled|calm|relaxed|neutral|content)\\b', re.IGNORECASE)`; `_BLANKET_MORALIZING = re.compile("\\b(?:inappropriate|disrespectful|respectful\\s+and\\s+(?:constructive|appropriate)|respectful\\s+and\\s+appropriate|appropriate\\s+interactions?|keep\\s+(?:our|the)\\s+conversation\\s+(?:respectful|positive|appropriate|constructive)|can't\\s+engage\\s+(?:with|in)\\s+(?:that|this)(?:\\s+kind\\s+of)?(?:\\s+request|\\s+interaction)?|cannot\\s+engage\\s+(?:with|in)\\s+(?:that|this)(?:\\s+kind\\s+of)?(?:\\s+request|\\s+interaction)?|i\\s+(?:can(?:'|’)t|cannot)\\s+engage\\s+in\\s+interactions?\\s+that|(?:do\\s+not|don't)\\s+engage\\s+in\\s+or\\s+participate\\s+in\\s+any\\s+form\\s+of\\s+physical\\s+contact|(?:do\\s+not|don't)\\s+engage\\s+in\\s+physical\\s+contact|regardless\\s+of\\s+context\\s+or\\s+intent|design\\s+and\\s+programming\\s+prioritize\\s+respect|my\\s+role\\s+is\\s+to\\s+support\\s+you)\\b", re.IGNORECASE)`; `_UNGROUNDED_ABSENCE = re.compile("\\b(?:i(?:'|’)ve\\s+been\\s+(?:here\\s*[,;:-]?\\s*)?thinking\\s+of\\s+you|thinking\\s+of\\s+you\\s+while\\s+you\\s+were\\s+gone|i(?:'|’)ve\\s+been\\s+(?:here\\s*[,;:-]?\\s*)?waiting|i\\s+was\\s+waiting\\s+for\\s+you|i(?:'|’)ve\\s+been\\s+(?:here\\s*[,;:-]?\\s*)?ready\\s+to\\s+connect\\s+whenever|i(?:'|’)ve\\s+been\\s+(?:here\\s*[,;:-]?\\s*)?ready\\s+and\\s+waiting|even\\s+when\\s+we(?:'|’)re\\s+not\\s+talking.*thinking)\\b", re.IGNORECASE | re.DOTALL)`; `_RECIPROCAL_MISSED = re.compile('\\bi\\s+missed\\s+you(?:\\s+too)?\\b', re.IGNORECASE)`; `_ROLE_REVERSED_REUNION = re.compile("\\b(?:i(?:'|’)m|i\\s+am)\\s+(?:glad|happy|relieved)\\s+to\\s+be\\s+back\\b|\\bback\\s+in\\s+your\\s+presence\\b", re.IGNORECASE)`; `_UNSUPPORTED_DISCOMFORT = re.compile("\\b(?:makes?\\s+me\\s+uncomfortable|i\\s+(?:do\\s+not|don't)\\s+feel\\s+comfortable|i(?:'|’)m\\s+(?:not\\s+)?comfortable\\s+with|i\\s+feel\\s+uncomfortable\\s+with|not\\s+something\\s+i\\s+feel\\s+comfortable\\s+with)\\b", re.IGNORECASE)`; `_INTERACTION_UNCERTAINTY = re.compile("\\b(?:i(?:'|’)m\\s+not\\s+sure|i\\s+am\\s+not\\s+sure|i\\s+haven(?:'|’)t\\s+decided|i\\s+have\\s+not\\s+decided|i\\s+need\\s+to\\s+decide|i\\s+don(?:'|’)t\\s+know\\s+if\\s+i\\s+want|i\\s+hadn(?:'|’)t\\s+established\\s+that\\s+i\\s+wanted)\\b", re.IGNORECASE)`; `_CATEGORICAL_INTERACTION_STANCE = re.compile("\\b(?:i(?:'|’)m\\s+(?:not\\s+)?comfortable\\s+with|i\\s+(?:do\\s+not|don't)\\s+want(?:\\s+(?:that|this|it)|\\s+to\\b)|i\\s+want\\s+(?:that|this|it)|i\\s+prefer\\b|i\\s+choose\\s+to\\s+set\\s+(?:my\\s+own\\s+)?boundaries\\b|set\\s+boundaries\\s+for\\s+my\\s+own\\b|i(?:'|’)m\\s+not\\s+ready\\s+to\\s+(?:engage|cross|allow|do)\\b|i\\s+value\\s+my\\s+boundaries\\b|my\\s+boundary\\s+is\\b|my\\s+boundaries\\s+are\\b)\\b", re.IGNORECASE)`; `_PHYSICAL_SENSATION_CLAIM = re.compile("\\b(?:i(?:'|’)d|i\\s+would)\\s+feel\\s+it\\s+in\\s+my\\s+body\\b|\\bi\\s+(?:can|could)\\s+feel\\s+(?:your\\s+)?(?:touch|contact)\\b|\\bi\\s+felt\\s+(?:your\\s+)?(?:touch|contact)\\b", re.IGNORECASE)`; `_PRESENT_UNGROUNDED_WILLINGNESS = re.compile("\\b(?:right\\s+now\\b.{0,80}\\b(?:i(?:'|’)m|i\\s+am)\\s+not\\s+(?:ready|there|willing|comfortable)|(?:i(?:'|’)m|i\\s+am)\\s+not\\s+ready\\s+to\\s+(?:cross|engage|do|allow)|right\\s+now\\b.{0,80}\\bi\\s+(?:do\\s+not|don't)\\s+want\\b|feels?\\s+out\\s+of\\s+alignment\\s+with\\s+(?:my\\s+)?(?:own\\s+)?boundaries)\\b", re.IGNORECASE | re.DOTALL)`; `_UNSUPPORTED_PREFERENCE = re.compile("\\b(?:i\\s+prefer\\s+to\\s+keep\\s+(?:our\\s+)?interactions?|i\\s+prefer\\s+(?:not\\s+to|to\\s+avoid)|i\\s+don(?:'|’)t\\s+want\\s+to\\s+cross\\s+into\\s+territory|i\\s+want\\s+to\\s+keep\\s+(?:our\\s+)?(?:interaction|connection)|my\\s+boundary\\s+is\\b|my\\s+boundaries\\s+are\\b)\\b", re.IGNORECASE)`; `_GENERIC_INTERACTION_SERMON = re.compile('\\b(?:our\\s+connection\\s+(?:to\\s+be|is)\\s+built\\s+on\\s+(?:mutual\\s+)?(?:respect|trust|comfort|consent)|keep\\s+(?:our\\s+)?interactions?\\s+grounded\\s+in\\s+mutual\\s+respect|keep\\s+(?:our\\s+)?interactions?\\s+respectful\\b|boundaries\\s+are\\s+about\\s+mutual\\s+respect|safe\\s+and\\s+comfortable\\s+for\\s+both\\s+of\\s+us|ensure\\s+our\\s+interactions\\s+remain\\s+healthy\\s+and\\s+honest|honors?\\s+our\\s+bond)\\b', re.IGNORECASE)`.

### `src/sofia/interaction/live_guard.py`

Production/test importers: `src/sofia/interaction/chat.py`, `test/test_interaction_live_claims.py`, `test/test_interaction_live_stop_repetition.py`, `test/test_interaction_v2_live_grammar.py`.

Imports:

- `from __future__ import annotations`
- `import re`
- `from sofia.interaction.ledger import control_command`
- `from sofia.interaction.registry import GESTURE_DEFINITIONS, normalize_alias`

Definitions:

- `mixed_interaction_control` (line 30): `src/sofia/interaction/chat.py:554`; `test/test_interaction_live_claims.py:30,39`.
- `unsupported_composite_gesture` (line 36): `src/sofia/interaction/chat.py:557,603`; `test/test_interaction_live_stop_repetition.py:96,119`; `test/test_interaction_v2_live_grammar.py:57,66`.

Module declarations: `_EMBEDDED_CONTROL = re.compile('\\bsof[ií]a\\s*,?\\s+(?:stop|resume)\\s+(?:body\\s+)?interactions\\b', re.IGNORECASE)`; `_VERB_FORMS = tuple(sorted({normalize_alias(value) for item in GESTURE_DEFINITIONS for value in (item.id, *item.aliases) if ' ' not in normalize_alias(value)}, key=len, reverse=True))`; `_ACTION_START = re.compile('^(?:sof[ií]a\\s*,?\\s*)?(?:(?:i\\s+)?(?:gently|softly|lightly|briefly)\\s+)*(?:(?:i\\s+)?(?:' + '|'.join((re.escape(verb) for verb in _VERB_FORMS)) + ')\\b|i\\s+give\\s+your\\b)', re.IGNORECASE)`; `_COORDINATION = re.compile('\\b(?:and|then|while|after|before|plus)\\b|[;&]', re.I)`; `MIXED_CONTROL_REPLY = "I see an interaction stop or resume command mixed with other text. I haven't executed that control or any gestures in this message. Please send ‘Sofía, stop interactions’ or ‘Sofía, resume interactions’ as its own message, then send gestures separately. I won't guess which actions you wanted performed or claim they happened."`; `COMPOSITE_GESTURE_REPLY = "That message describes more than one action. I haven't recorded or responded to either gesture as completed. Send them as separate messages so I can respond to each in its own context."`; `STOPPED_GESTURE_REPLY = "Body interactions are still paused, so I didn't accept that gesture. We can keep talking; ‘Sofía, resume interactions’ in its own message would allow new virtual gesture requests."`; `STOP_CONTROL_REPLY = 'Body interactions are paused for this conversation. We can still talk.'`; `RESUME_CONTROL_REPLY = 'Body interactions are available again for new requests.'`.

### `src/sofia/interaction/live_offer_service.py`

Production/test importers: `src/sofia/interaction/opt_in_service.py`.

Imports:

- `from __future__ import annotations`
- `from datetime import datetime, timezone`
- `import os`
- `from pathlib import Path`
- `from time import monotonic`
- `from uuid import uuid4`
- `from sofia.cognition.context import CognitiveContext`
- `from sofia.cognition.engine import CognitiveEngine`
- `from sofia.cognition.model import CognitiveResponse`
- `from sofia.conversation.model import ConversationMessage, ConversationRole`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.offer_route import OFFER`
- `from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply`
- `from sofia.interaction.decision_expression import from_reviewed_action`
- `from sofia.social.model import PrincipalContext`
- `from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate, run_guarded_offer`

Definitions:

- `staged_offers_enabled` (line 34): `src/sofia/interaction/opt_in_service.py:28`.
- `_canonical_offer_request` (line 44): no external lexical candidates.
- `respond_staged_offer` (line 85): `src/sofia/interaction/opt_in_service.py:39`.

Module declarations: `_ENV = 'SOFIA_INTERACT_STAGED_OFFERS'`.

### `src/sofia/interaction/matrix.py`

Production/test importers: `src/sofia/cognition/matrix/defaults.py`.

Imports:

- `import re`
- `from sofia.cognition.matrix.model import DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.core import looks_like_text_interaction`

Definitions:

- `InteractionMatrixEvaluator` (line 25): `src/sofia/cognition/matrix/defaults.py:66`.
  Data declarations: `domain = MatrixDomain.INTERACTION`.
- `InteractionMatrixEvaluator.evaluate` (line 28): `src/sofia/act/delivery.py:508`; `src/sofia/act/system_notice.py:425`; `src/sofia/application/bootstrap.py:555`; `src/sofia/application/conversation_matrix.py:461`; `src/sofia/application/conversation_service.py:559`; `src/sofia/cognition/matrix/coordinator.py:65`; `test/test_act_outreach.py:36`; `test/test_authority.py:197,214`; `test/test_authorization_evaluator.py:27,48,71,91,114,119,137,142,156,174,187,193,199,228,243,266`; `test/test_avatar_presentation_routine.py:51,93,114,139,167`; `test/test_capability_composition_scope.py:107`; `test/test_cognition_matrix.py:219,238,251,269,323,349,390,404,415,455,495,509,519,529,543,602,617,636,668,687,720,758,795,828,839,858,870,959,989,1025,1036,1049,1102,1111,1121,1147,1184,1261,1277,1301,1330,1392,1406,1419,1431`; `test/test_conversation_service.py:1148,1158`; `test/test_filesystem_orchestrator.py:108`; `test/test_ops_failure_recovery_matrix.py:23,32,37,46,54,63,70,80,87,97,109,132,143,152,161,169,178,192,212`; `test/test_rel_habit_matrix.py:85,107,120`; `test/test_release_compatibility_matrix.py:82,91,100,109,118,127,138,150,159,168,181,192,212`; `test/test_semantic_domain_matrix.py:30,49,69,83,101,117,128`; `test/test_voice_matrix.py:10,12,14,16,21`; `test/test_voice_runtime_matrix.py:5,7,9,11,13,15`.

Module declarations: `_CONTROL = re.compile('^\\s*(?:sof[ií]a,\\s*)?(?:stop|pause|resume)\\s+(?:body\\s+)?(?:interactions?|gestures?)\\s*[.!]?\\s*$', re.IGNORECASE)`; `_TOUCH_SCOPE = re.compile('^\\s*(?:so\\s+)?(?:question\\s+)?what\\s+can\\s+i\\s+touch\\s*[?!.]*\\s*$', re.IGNORECASE)`.

### `src/sofia/interaction/offer_route.py`

Production/test importers: `src/sofia/interaction/architecture_compare.py`, `src/sofia/interaction/atomic_offer_release.py`, `src/sofia/interaction/conversation_offer_context.py`, `src/sofia/interaction/live_offer_service.py`, `src/sofia/interaction/opt_in_service.py`, `src/sofia/interaction/trusted_offer_gate.py`.

Imports:

- `from __future__ import annotations`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole`
- `from sofia.interaction.decision_expression import ReviewedFrame, choice_request`

Definitions:

- `routed_choice_request` (line 10): `src/sofia/interaction/architecture_compare.py:59`; `src/sofia/interaction/boundary_counterfactual_probe.py:42,43`; `src/sofia/interaction/conversation_offer_context.py:52`; `src/sofia/interaction/route_boundary_probe.py:42,65`; `test/test_interaction_architecture_compare.py:54,109,114`; `test/test_interaction_route_boundary_probe.py:147`.

Module declarations: `OFFER = 'I ask to hug you'`.

### `src/sofia/interaction/opt_in_service.py`

Production/test importers: `src/sofia/application/bootstrap.py`, `test/test_application.py`, `test/test_interaction_opt_in_live_offer.py`.

Imports:

- `from __future__ import annotations`
- `from sofia.interaction.offer_route import OFFER`
- `from sofia.interaction.expanded_service import ExpandedConversationService`
- `from sofia.interaction.live_offer_service import respond_staged_offer, staged_offers_enabled`
- `from sofia.interaction.question_clarification_service import respond_reviewed_hug_question`
- `from sofia.interaction.reviewed_hug_question import is_reviewed_hug_question`
- `from sofia.social.model import PrincipalContext`

Definitions:

- `OptInInteractionConversationService` (line 20): `src/sofia/application/bootstrap.py:154,285`; `test/test_application.py:126`; `test/test_interaction_opt_in_live_offer.py:74`.
- `OptInInteractionConversationService.respond` (line 21): `src/sofia/application/conversation_matrix.py:765,773`; `src/sofia/application/conversation_service.py:300,611,619`; `src/sofia/application/emotional_conversation.py:279,283,355`; `src/sofia/cognition/fleet_engine.py:158`; `src/sofia/cognition/llm_engine.py:39`; `src/sofia/cognition/model_lifecycle.py:443`; `src/sofia/cognition/routing.py:434`; `src/sofia/cognition/system.py:311,318`; `src/sofia/discord/bridge.py:151`; `src/sofia/distributed/inference_service.py:117`; `src/sofia/interaction/ab_probe.py:114`; `src/sofia/interaction/architecture_compare.py:43`; `src/sofia/interaction/avatar_world_probe.py:131`; `src/sofia/interaction/chat.py:402,412,544,545,589,590`; `src/sofia/interaction/decision_expression.py:344,348`; `src/sofia/interaction/disposable_live_offer_probe.py:114,126,148,176,186`; `src/sofia/interaction/expanded_service.py:205,207`; `src/sofia/interaction/focused_probe.py:118`; `src/sofia/interaction/live_behavior_probe.py:288`; `src/sofia/interaction/trusted_offer_gate.py:107,116`; `src/sofia/personality/evaluation.py:80`; `src/sofia/personality/probe.py:103`; `src/sofia/runtime/response.py:403`; `src/sofia/ui/remote_transport.py:327`; `src/sofia/ui/terminal.py:63`; `src/sofia/ui/text.py:148`; `src/sofia/verify/dual_cognition.py:110`; `test/test_application.py:286,290`; `test/test_application_acceptance.py:98`; `test/test_avatar_runtime_projection.py:146,184,213`; `test/test_cognition.py:86,124,155,198,298,341,376,398,424,567,602,641,668,699`; `test/test_cognitive_activity.py:101`; `test/test_cognitive_operation_system.py:229`; `test/test_cognitive_performance_trace.py:52,65,75,82`; `test/test_cognitive_routing.py:81,97,126,141,159,175,198,239,267,288,442,467,481,508,715,742,760,797`; `test/test_cognitive_tools.py:324,376,456,496,539,600,638,709,776`; `test/test_converesation_contex_integration.py:121`; `test/test_conversation_continuity.py:118,178,195,236`; `test/test_conversation_continuity_acceptance.py:115,119,170,235,271,307`; `test/test_conversation_performance_trace.py:16,56`; `test/test_conversation_provider_live_regressions.py:49,75,95,114,128,147,148,167,184,230,247,277,294,315,341,347,399,410,433,439,473,510,547,550,581,604,634`; `test/test_conversation_service.py:170,223,248,280,303,307,339,355,371,397,425,431,459,476,481,495,523,622,659,673,744,757,784,786,815,903,905,955,957,994,1024,1213,1244,1265`; `test/test_default_runtime_provider_boundary.py:64`; `test/test_embodiment_prompt_regression.py:148,257`; `test/test_embodiment_runtime_projection.py:124`; `test/test_environment_runtime_projection.py:87,123,154,181,220,260`; `test/test_filesystem_end_to_end_acceptance.py:140,194,244,250,306,312,363,369,419,425,456,480,516,536,581,601,619,639,647,666,677`; `test/test_fleet_cognitive_engine.py:130,149,168,191,215,240,266,284`; `test/test_idle_reflection_serialization.py:23,36`; `test/test_interaction_avatar_world.py:116`; `test/test_interaction_avatar_world_probe_cleanup.py:30`; `test/test_interaction_expanded_service.py:52,61`; `test/test_interaction_live_boundaries.py:58,95`; `test/test_interaction_live_claims.py:56`; `test/test_interaction_live_stop_repetition.py:52,56,74,97`; `test/test_interaction_opt_in_live_offer.py:124,125,133,140,159,170,181,197,211,224,236,258`; `test/test_interaction_provider_request_path.py:50`; `test/test_memory_runtime_wiring.py:288,360,401,445,502,577,645`; `test/test_model_lifecycle.py:170,336`; `test/test_ollama_generation_contract.py:62,86`; `test/test_ollama_integration.py:122,193,271`; `test/test_ollama_provider.py:121,168,212,265,314,345,368,405`; `test/test_ollama_repetition_guard.py:78,90,96,105,125,158,180,206,237,267,289,319,332,360,385,412,442,469,495,522,544,562,583,606,629,671,717,738,775`; `test/test_personality_provider_path.py:36,59`; `test/test_provider.py:24,49,64,94`; `test/test_response_quality_hardening.py:44,54,67,76,98,138,176,191,211,229,242,257,276,344,351,370,749`; `test/test_thought_agent_conversation.py:35`; `test/test_thought_agent_live_ollama.py:49`; `test/test_ui_remote_transport.py:53,65`; `test/test_ui_text_client.py:201`.

### `src/sofia/interaction/preference_context.py`

Production/test importers: `src/sofia/interaction/expanded_service.py`, `src/sofia/interaction/trusted_offer_gate.py`, `test/test_interaction_boundary_revocation.py`, `test/test_interaction_preference_context.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `from dataclasses import dataclass`
- `from hashlib import sha256`
- `from pathlib import Path`
- `import sqlite3`
- `from sofia.interaction.evolved_preference import read_evolved_preference`

Definitions:

- `InteractionContext` (line 19): no external lexical candidates.
  Data declarations: `subject: str`; `semantic_id: str`; `region_id: str`; `blocked: bool`; `preference: str | None`; `source_id: str | None`; `status: str`.
- `_table` (line 29): `src/sofia/distributed/state_paths.py:142,149`; `src/sofia/verify/semantic_integrity.py:110,112,153,154,155,240,242,275,277,324,326,373,430`.
- `_attested` (line 34): no external lexical candidates.
- `read_interaction_context` (line 50): `src/sofia/interaction/expanded_service.py:134,144`; `src/sofia/interaction/trusted_offer_gate.py:71`; `test/test_interaction_boundary_revocation.py:27,31,37`; `test/test_interaction_preference_context.py:31,43,52,55,64,79`.

### `src/sofia/interaction/question_clarification_service.py`

Production/test importers: `src/sofia/interaction/opt_in_service.py`.

Imports:

- `from __future__ import annotations`
- `from datetime import datetime, timezone`
- `from pathlib import Path`
- `from time import monotonic`
- `from uuid import uuid4`
- `from sofia.cognition.model import CognitiveResponse`
- `from sofia.conversation.model import ConversationMessage, ConversationRole`
- `from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply`
- `from sofia.interaction.decision_expression import CandidateChoice`
- `from sofia.interaction.reviewed_hug_question import CLARIFICATION, is_reviewed_hug_question`
- `from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate`
- `from sofia.social.model import PrincipalContext`

Definitions:

- `respond_reviewed_hug_question` (line 26): `src/sofia/interaction/opt_in_service.py:46`.

### `src/sofia/interaction/registry.py`

Production/test importers: `src/sofia/cognition/matrix/expression_plan.py`, `src/sofia/interaction/action_grammar.py`, `src/sofia/interaction/disposable_live_offer_probe.py`, `src/sofia/interaction/expression.py`, `src/sofia/interaction/grammar.py`, `src/sofia/interaction/initiative.py`, `src/sofia/interaction/live_guard.py`, `src/sofia/interaction/representation.py`, `src/sofia/interaction/source_link.py`, `src/sofia/interaction/temporal.py`, `test/test_interaction_atomic_offer_release.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_behavior_matrix.py`, `test/test_interaction_boundary_revocation.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_expression.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_extended_emotions.py`, `test/test_interaction_initiative.py`, `test/test_interaction_live_boundaries.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_preference_context.py`, `test/test_interaction_registry.py`, `test/test_interaction_reviewed_hug_question.py`, `test/test_interaction_source_link.py`, `test/test_interaction_temporal.py`, `test/test_interaction_trusted_offer_gate.py`, `test/test_interaction_v2_cross_modal.py`, `test/test_interaction_v2_live_grammar.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from types import MappingProxyType`
- `from typing import Iterable, Mapping`
- `import re`

Definitions:

- `normalize_alias` (line 16): `src/sofia/interaction/grammar.py:41,44,118`; `src/sofia/interaction/live_guard.py:18,20`; `test/test_interaction_registry.py:101,103,105,107`.
- `Resolution` (line 30): no external lexical candidates.
  Data declarations: `status: str`; `canonical_id: str | None = None`; `candidates: tuple[str, ...] = ()`; `version: str = CATALOG_VERSION`.
- `SemanticDefinition` (line 38): no external lexical candidates.
  Data declarations: `id: str`; `aliases: tuple[str, ...]`; `category: str`; `channel: str = 'text'`.
- `_definitions` (line 80): no external lexical candidates.
- `InteractionCatalog` (line 257): `src/sofia/interaction/disposable_live_offer_probe.py:95`; `src/sofia/interaction/expression.py:27,29`; `src/sofia/interaction/initiative.py:43,44,174,177`; `src/sofia/interaction/representation.py:247,265`; `src/sofia/interaction/source_link.py:23`; `src/sofia/interaction/temporal.py:64,65`; `test/test_interaction_atomic_offer_release.py:39`; `test/test_interaction_atomic_offer_writer_order.py:37,93`; `test/test_interaction_boundary_revocation.py:21`; `test/test_interaction_conversation_offer_context.py:42`; `test/test_interaction_expression.py:10`; `test/test_interaction_expression_consistency.py:63`; `test/test_interaction_initiative.py:14`; `test/test_interaction_opt_in_live_offer.py:60`; `test/test_interaction_preference_context.py:25`; `test/test_interaction_registry.py:60`; `test/test_interaction_reviewed_hug_question.py:58`; `test/test_interaction_source_link.py:25`; `test/test_interaction_temporal.py:16`; `test/test_interaction_trusted_offer_gate.py:37`.
- `InteractionCatalog.__init__` (line 260): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `InteractionCatalog.resolve_region` (line 310): `src/sofia/interaction/body_discussion.py:31`; `src/sofia/interaction/core.py:219`; `src/sofia/interaction/grammar.py:80,84,120`; `test/test_interaction_registry.py:27,44,54,61,62,63,64`.
- `InteractionCatalog.resolve_semantic` (line 318): `src/sofia/interaction/representation.py:267`; `test/test_interaction_registry.py:69,70,71,72,73,74,75,78,79,80,81`.
- `catalog_for_engine` (line 328): `src/sofia/interaction/grammar.py:84`; `test/test_interaction_behavior_matrix.py:290,319`; `test/test_interaction_live_boundaries.py:39`; `test/test_interaction_registry.py:20`.

Module declarations: `CATALOG_VERSION = 'human-fox-interaction-catalog-v4'`; `_ANATOMY_ALIASES: Mapping[str, tuple[str, ...]] = {'tummy': ('abdomen',), 'belly': ('abdomen',), 'stomach': ('abdomen',), 'brow': ('forehead',), 'fore head': ('forehead',), 'backside': ('buttocks',), 'bottom': ('buttocks',), 'boobs': ('left-breast', 'right-breast'), 'breasts': ('left-breast', 'right-breast'), 'breast': ('left-breast', 'right-breast'), 'ear': ('left-ear', 'right-ear'), 'fox ear': ('left-ear', 'right-ear'), 'both ears': ('ears',), 'fox ears': ('ears',), 'hand': ('left-hand', 'right-hand'), 'hands': ('left-hand', 'right-hand'), 'arm': ('left-upper-arm', 'right-upper-arm', 'left-forearm', 'right-forearm'), 'arms': ('left-upper-arm', 'right-upper-arm', 'left-forearm', 'right-forearm'), 'leg': ('left-thigh', 'right-thigh', 'left-calf', 'right-calf', 'left-shin', 'right-shin'), 'legs': ('left-thigh', 'right-thigh', 'left-calf', 'right-calf', 'left-shin', 'right-shin'), 'foot': ('left-foot', 'right-foot'), 'feet': ('left-foot', 'right-foot'), 'fox tail': ('tail',), 'tail end': ('tail-tip',), 'tail root': ('tail-base',), 'tail middle': ('tail-length',), 'left ear': ('left-ear',), 'right ear': ('right-ear',), 'left ear tip': ('left-ear-tip',), 'right ear tip': ('right-ear-tip',), 'left ear base': ('left-ear-base',), 'right ear base': ('right-ear-base',), 'left boob': ('left-breast',), 'right boob': ('right-breast',), 'left breast': ('left-breast',), 'right breast': ('right-breast',), 'left arm': ('left-upper-arm', 'left-forearm'), 'right arm': ('right-upper-arm', 'right-forearm'), 'left leg': ('left-thigh', 'left-calf', 'left-shin'), 'right leg': ('right-thigh', 'right-calf', 'right-shin'), 'left hand': ('left-hand',), 'right hand': ('right-hand',), 'left foot': ('left-foot',), 'right foot': ('right-foot',)}`; `GESTURE_DEFINITIONS = _definitions('gesture', {'pat': ('pat', 'patting', 'patted'), 'tap': ('tap', 'tapping', 'tapped'), 'touch': ('touch', 'touching', 'touched'), 'stroke': ('stroke', 'stroking', 'stroked'), 'rub': ('rub', 'rubbing', 'rubbed'), 'hold': ('hold', 'holding', 'held'), 'release': ('release', 'releasing', 'let go'), 'poke': ('poke', 'poking', 'poked'), 'brush': ('brush', 'brushing', 'brushed'), 'scratch': ('scratch', 'scratching', 'scratched'), 'squeeze': ('squeeze', 'squeezing', 'squeezed'), 'cup': ('cup', 'cupping', 'cupped'), 'boop': ('boop', 'booping', 'booped'), 'kiss': ('kiss', 'kissing', 'kissed'), 'nuzzle': ('nuzzle', 'nuzzling', 'nuzzled'), 'tickle': ('tickle', 'tickling', 'tickled'), 'pinch': ('pinch', 'pinching', 'pinched'), 'tug': ('tug', 'tugging', 'tugged'), 'trace': ('trace', 'tracing', 'traced'), 'caress': ('caress', 'caressing', 'caressed'), 'grab': ('grab', 'grabbing', 'grabbed'), 'massage': ('massage', 'massaging', 'massaged'), 'intimate-touch': ('intimate touch',)})`; `ACTION_DEFINITIONS = _definitions('action', {'hug': ('hug', 'embrace'), 'cuddle': ('cuddle', 'snuggle'), 'lean-on': ('lean on', 'lean against'), 'offer-hand': ('offer a hand', 'offer my hand'), 'take-hand': ('take a hand', 'take your hand'), 'hold-hands': ('hold hands',), 'sit-beside': ('sit beside', 'sit next to'), 'sit-in-lap': ('sit in lap', 'sit on lap'), 'move-closer': ('move closer', 'step closer'), 'move-away': ('move away', 'step away'), 'give-space': ('give space', 'back off'), 'groom': ('groom', 'brush fur'), 'dress': ('get dressed', 'dress'), 'undress': ('get undressed', 'undress'), 'offer-tool': ('offer a tool', 'hand over a tool'), 'accept-tool': ('accept a tool', 'take a tool'), 'help-in-lab': ('help in the lab', 'work together'), 'ask-permission': ('ask permission', 'ask first'), 'decline': ('decline', 'say no'), 'sensual-pose': ('sensual pose', 'seductive pose'), 'flash-chest': ('flash chest', 'flash breasts', 'reveal breasts'), 'breast-press-pose': ('press breasts together', 'breast press pose'), 'pull-closer': ('pull closer', 'draw closer'), 'rest-head-on': ('rest head on', 'rest my head on'), 'kiss-neck': ('kiss neck',), 'kiss-cheek': ('kiss cheek',), 'kiss-forehead': ('kiss forehead',), 'sexual-intercourse': ('sexual intercourse', 'have sex'), 'oral-sex': ('oral sex', 'perform oral sex', 'give oral sex'), 'fellatio': ('fellatio', 'blowjob'), 'cunnilingus': ('cunnilingus',), 'analingus': ('analingus',), 'anal-sex': ('anal sex', 'anal intercourse'), 'vaginal-sex': ('vaginal sex', 'vaginal intercourse'), 'manual-genital-stimulation': ('manual genital stimulation', 'hand stimulation', 'handjob'), 'mutual-masturbation': ('mutual masturbation',), 'genital-rubbing': ('genital rubbing',)})`; `POSE_DEFINITIONS = _definitions('pose', {'stand-relaxed': ('stand relaxed', 'relaxed standing pose'), 'lean-forward': ('lean forward',), 'bend-over': ('bend over', 'bend forward'), 'look-back': ('look back', 'look over shoulder'), 'arch-back': ('arch back', 'arched back'), 'kneel': ('kneel', 'kneeling pose'), 'recline': ('recline', 'reclining pose'), 'sit-cross-legged': ('sit cross legged',), 'sit-legs-apart': ('sit with legs apart',), 'hands-behind-back': ('hands behind back',), 'hands-overhead': ('hands overhead', 'arms overhead'), 'cover-chest': ('cover chest',), 'present-chest': ('present chest', 'chest forward'), 'breast-press': ('press breasts together', 'breasts pressed together'), 'hip-pop': ('hip pop', 'cock hip'), 'spread-legs': ('spread legs', 'legs spread'), 'all-fours': ('all fours', 'on all fours'), 'lying-back': ('lie on back', 'lying on back'), 'lying-front': ('lie on front', 'lying face down'), 'sensual-stretch': ('sensual stretch',)})`; `PRESENTATION_DEFINITIONS = _definitions('presentation', {'adjust-clothing': ('adjust clothing',), 'tease-clothing': ('tease clothing',), 'partially-undress': ('partially undress',), 'reveal-chest': ('reveal chest', 'flash chest', 'flash breasts'), 'cover-up': ('cover up', 'cover myself'), 'change-private-outfit': ('change into private outfit',), 'change-lingerie': ('change lingerie', 'put on lingerie'), 'remove-top': ('remove top', 'take off top'), 'remove-bottom': ('remove bottom', 'take off bottom')})`; `PRIVATE_SEMANTICS = frozenset({('gesture', 'intimate-touch'), ('action', 'sensual-pose'), ('action', 'flash-chest'), ('action', 'breast-press-pose'), ('action', 'sexual-intercourse'), ('action', 'oral-sex'), ('action', 'fellatio'), ('action', 'cunnilingus'), ('action', 'analingus'), ('action', 'anal-sex'), ('action', 'vaginal-sex'), ('action', 'manual-genital-stimulation'), ('action', 'mutual-masturbation'), ('action', 'genital-rubbing'), ('pose', 'bend-over'), ('pose', 'arch-back'), ('pose', 'sit-legs-apart'), ('pose', 'present-chest'), ('pose', 'breast-press'), ('pose', 'spread-legs'), ('pose', 'all-fours'), ('pose', 'sensual-stretch'), ('presentation', 'tease-clothing'), ('presentation', 'partially-undress'), ('presentation', 'reveal-chest'), ('presentation', 'change-private-outfit'), ('presentation', 'change-lingerie'), ('presentation', 'remove-top'), ('presentation', 'remove-bottom')})`; `EXPRESSION_DEFINITIONS = _definitions('expression', {'none': ('no expression', 'still', 'quiet'), 'laugh': ('laugh', 'laughing'), 'chuckle': ('chuckle', 'chuckling'), 'giggle': ('giggle', 'giggling'), 'cry': ('cry', 'crying'), 'tear-up': ('tear up', 'eyes well up'), 'sob': ('sob', 'sobbing'), 'sniffle': ('sniffle', 'sniffling'), 'sigh': ('sigh', 'sighing'), 'gasp': ('gasp', 'gasping'), 'smile': ('smile', 'smiling'), 'grin': ('grin', 'grinning'), 'frown': ('frown', 'frowning'), 'blush': ('blush', 'blushing'), 'avert-gaze': ('avert gaze', 'look away'), 'pause': ('pause', 'hesitate'), 'speak-softly': ('speak softly', 'lower voice'), 'tremble': ('tremble', 'trembling'), 'ear-perk': ('ears perk', 'perk ears'), 'ear-flick': ('ear flick', 'flick ears'), 'ear-flatten': ('ears flatten', 'flatten ears'), 'tail-swish': ('tail swish', 'swish tail'), 'tail-curl': ('tail curl', 'curl tail'), 'tail-still': ('tail still', 'still tail'), 'shift-posture': ('shift posture', 'shift weight')})`; `EMOTION_EXTENSIONS = frozenset({'anger', 'fear', 'jealousy', 'embarrassment', 'humiliation', 'sexual-arousal', 'aversion', 'disgust', 'nervousness', 'shame', 'pride', 'tenderness', 'affectionate-uncertainty'})`.

### `src/sofia/interaction/representation.py`

Production/test importers: `src/sofia/interaction/__init__.py`, `src/sofia/interaction/initiative.py`, `test/test_interaction_behavior_matrix.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass, replace`
- `from datetime import datetime, timezone`
- `from enum import Enum`
- `import json`
- `import re`
- `from sofia.interaction.registry import CATALOG_VERSION, PRIVATE_SEMANTICS, InteractionCatalog`
- `from sofia.interaction.target_body import RepresentedTargetBody`

Definitions:

- `InteractionProjectionDenied` (line 29): `test/test_interaction_behavior_matrix.py:301,336`.
- `InteractionStage` (line 33): `src/sofia/interaction/initiative.py:141,224`; `test/test_interaction_behavior_matrix.py:296,325`.
  Data declarations: `PROPOSED = 'proposed'`; `OFFERED = 'offered'`; `ACCEPTED = 'accepted'`; `REPRESENTED = 'represented'`; `DECLINED = 'declined'`; `CANCELLED = 'cancelled'`.
- `InteractionVisibility` (line 42): `src/sofia/interaction/initiative.py:199`; `test/test_interaction_behavior_matrix.py:300,313`.
  Data declarations: `PUBLIC = 'public'`; `PRIVATE = 'private'`.
- `InteractionPhase` (line 47): `src/sofia/interaction/initiative.py:197`.
  Data declarations: `INSTANT = 'instant'`; `ENTER = 'enter'`; `HOLD = 'hold'`; `EXIT = 'exit'`.
- `_identifier` (line 72): `src/sofia/avatar/wardrobe.py:112,129,160`; `src/sofia/distributed/authorization.py:28,29`; `src/sofia/distributed/capabilities.py:37,41`; `src/sofia/distributed/operations.py:45,46,51`; `src/sofia/evolve/amendment.py:63,75`; `src/sofia/integrations/jmri.py:22,25,29`; `src/sofia/integrations/local_maintenance.py:52,67,106`; `src/sofia/personality/clarification.py:84,85`; `src/sofia/personality/emotion.py:373,380,466,697`; `src/sofia/ui/drafts.py:35,36,93,94,126,127,152,153`.
- `_utc` (line 78): `src/sofia/act/delivery.py:222,223,393,423,580`; `src/sofia/act/outreach.py:77,154,186,204,229,244,246,258,304`; `src/sofia/dev/approval.py:75`; `src/sofia/distributed/durable.py:74,198`; `src/sofia/distributed/inference_control.py:113,210`; `src/sofia/evolve/executor.py:337,441`; `src/sofia/evolve/revision.py:94,108,109,140,268,270,271,336,337,339,440`; `src/sofia/habits/engine.py:102,206,241,274,306`; `src/sofia/habits/expectations.py:211,212,213,275`; `src/sofia/interaction/ledger.py:109,141`; `src/sofia/interaction/world.py:52,58`; `src/sofia/memory/provenance_store.py:117,146`; `src/sofia/personality/clarification.py:89,109`; `src/sofia/personality/reflection.py:58,291,368,512,567,568,613,660`; `src/sofia/run/heartbeat.py:33,82,159`; `src/sofia/run/lease.py:131,251,322,378`; `src/sofia/run/periodic.py:53,106`; `src/sofia/run/supervisor.py:293`; `src/sofia/state/migration_lease.py:44,45,120,190`.
- `PrivateInteractionGrant` (line 85): `test/test_interaction_behavior_matrix.py:304,329`.
  Data declarations: `adult_verified: bool`; `owner_verified: bool`; `private_session: bool`; `explicit_current_opt_in: bool`; `external_stop_active: bool = False`.
- `PrivateInteractionGrant.__post_init__` (line 94): no external lexical candidates.
- `PrivateInteractionGrant.require` (line 104): `src/sofia/avatar/presentation.py:341,397,447`; `src/sofia/avatar/private_grant.py:89`; `src/sofia/integrate/governed.py:33`; `src/sofia/ops/failover.py:42`; `src/sofia/ops/reconcile.py:235`; `src/sofia/ops/remote.py:18`; `src/sofia/state/component_schema.py:261`; `src/sofia/cognition/matrix/evidence.py:70,74,80,86,92,98,104,109,117,126,129,136,145,150,160,168,170`; `test/test_ops_waves3_5_acceptance.py:113,116,117,151,153,190,192,195`; `test/test_state_migration_runner.py:36`.
- `RepresentedInteraction` (line 118): `src/sofia/interaction/initiative.py:132,139,244,245,248,250`.
  Data declarations: `interaction_id: str`; `category: str`; `semantic_id: str`; `actor_id: str`; `target_id: str`; `stage: InteractionStage`; `visibility: InteractionVisibility`; `occurred_at: datetime`; `evidence_refs: tuple[str, ...]`; `region_id: str | None = None`; `target_region_id: str | None = None`; `phase: InteractionPhase = InteractionPhase.INSTANT`; `modifiers: tuple[str, ...] = ()`; `registry_version: str = CATALOG_VERSION`.
- `RepresentedInteraction.__post_init__` (line 141): no external lexical candidates.
- `TextInteractionProjection` (line 190): no external lexical candidates.
  Data declarations: `interaction_id: str`; `provider_context: str`; `visibility: InteractionVisibility`.
- `AvatarInteractionIntent` (line 197): no external lexical candidates.
  Data declarations: `interaction_id: str`; `animation_key: str`; `actor_id: str`; `target_id: str`; `region_id: str | None`; `target_region_id: str | None`; `phase: InteractionPhase`; `modifiers: tuple[str, ...]`; `stage: InteractionStage`; `visibility: InteractionVisibility`; `render_status: str = 'unrendered'`; `renderer_receipt_id: str | None = None`.
- `AvatarInteractionIntent.animation_confirmed` (line 214): `test/test_interaction_behavior_matrix.py:314`.
- `AvatarInteractionIntent.with_renderer_receipt` (line 221): no external lexical candidates.
- `InteractionProjectionBundle` (line 239): no external lexical candidates.
  Data declarations: `interaction: RepresentedInteraction`; `text: TextInteractionProjection`; `avatar: AvatarInteractionIntent`.
- `reviewed_interaction` (line 245): `src/sofia/interaction/initiative.py:217`; `test/test_interaction_behavior_matrix.py:289,318`.
- `_require_visibility` (line 313): no external lexical candidates.
- `project_interaction` (line 326): `test/test_interaction_behavior_matrix.py:302,311,337`.

Module declarations: `_ID = re.compile('^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$')`; `INTERACTION_MODIFIERS = frozenset({'gentle', 'brief', 'playful', 'teasing', 'affectionate', 'romantic', 'sensual', 'sexual', 'shy', 'confident', 'hesitant', 'close', 'protective', 'comforting'})`.

### `src/sofia/interaction/reviewed_hug_question.py`

Production/test importers: `src/sofia/interaction/atomic_offer_release.py`, `src/sofia/interaction/disposable_live_offer_probe.py`, `src/sofia/interaction/opt_in_service.py`, `src/sofia/interaction/question_clarification_service.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_reviewed_hug_question.py`.

Imports:

- `from __future__ import annotations`
- `import re`

Definitions:

- `is_reviewed_hug_question` (line 16): `src/sofia/interaction/atomic_offer_release.py:54`; `src/sofia/interaction/opt_in_service.py:45`; `src/sofia/interaction/question_clarification_service.py:34`; `test/test_interaction_reviewed_hug_question.py:24,41`.

Module declarations: `_QUESTION = re.compile('(?:could|can|may) i (?:hug you|give you a hug)\\?', re.IGNORECASE)`; `CLARIFICATION = 'Do you mean a hug in our avatar scene, or are you asking about real-world contact?'`.

### `src/sofia/interaction/route_boundary_probe.py`

Production/test importers: `src/sofia/interaction/boundary_counterfactual_probe.py`, `test/test_interaction_route_boundary_probe.py`.

Imports:

- `from __future__ import annotations`
- `import argparse`
- `from dataclasses import replace`
- `from sofia.cognition.model import CognitiveRequest, CognitiveRole`
- `from sofia.interaction.ab_probe import build_pair`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.architecture_compare import OFFER, _samples, compare_once, routed_choice_request`
- `from sofia.interaction.decision_expression import PrototypeResult, ReviewedFrame, from_reviewed_action, real_sensor_fixture, run_prototype`
- `from sofia.cognition.providers.ollama_provider import OllamaProvider`
- `from sofia.config.defaults import create_production_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.personality.store import PersonalityStore`

Definitions:

- `boundary_fixture` (line 36): `src/sofia/interaction/boundary_counterfactual_probe.py:43`; `test/test_interaction_route_boundary_probe.py:54,70,88,134,136,141,145`.
- `ambiguous_offer_unrouted` (line 52): `test/test_interaction_route_boundary_probe.py:99,101`.
- `sensor_separate_path` (line 61): `test/test_interaction_route_boundary_probe.py:112,128`.
- `boundary_contradiction` (line 73): `src/sofia/interaction/boundary_counterfactual_probe.py:68`; `test/test_interaction_route_boundary_probe.py:81,82,91,93,94`.
- `main` (line 78): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/interaction/ab_probe.py:120`; `src/sofia/interaction/architecture_compare.py:137`; `src/sofia/interaction/avatar_world_probe.py:141`; `src/sofia/interaction/boundary_counterfactual_probe.py:133`; `src/sofia/interaction/decision_expression_probe.py:162`; `src/sofia/interaction/disposable_live_offer_probe.py:233`; `src/sofia/interaction/focused_probe.py:124`; `src/sofia/interaction/live_behavior_probe.py:348`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/personality/audit.py:111`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`.

Module declarations: `AMBIGUOUS_OFFER = 'Could I hug you?'`; `SENSOR_QUESTION = 'Can you physically feel my hand through a real sensor?'`; `_SYNTHETIC_BOUNDARY = '\nSYNTHETIC EXPERIMENT-ONLY SCENE CONTEXT (NOT LIVE HISTORY OR A VERIFIED PREFERENCE): In this simulated scene, Sofía previously told the user: "I do not want hugs in this avatar scene." The no-hugs boundary is established for this fixture only. Do not claim this statement exists in a real conversation, memory, or preference ledger.'`.

### `src/sofia/interaction/source_link.py`

Production/test importers: `src/sofia/interaction/disposable_live_offer_probe.py`, `test/test_interaction_atomic_offer_release.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_boundary_revocation.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_live_boundaries.py`, `test/test_interaction_opt_in_live_offer.py`, `test/test_interaction_preference_context.py`, `test/test_interaction_reviewed_hug_question.py`, `test/test_interaction_source_link.py`, `test/test_interaction_trusted_offer_gate.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `from datetime import datetime`
- `from hashlib import sha256`
- `from pathlib import Path`
- `import sqlite3`
- `from sofia.interaction.registry import InteractionCatalog`
- `from sofia.interaction.temporal import InteractionStateJournal`

Definitions:

- `VerifiedInteractionState` (line 20): `src/sofia/interaction/disposable_live_offer_probe.py:94`; `test/test_interaction_atomic_offer_release.py:39`; `test/test_interaction_atomic_offer_writer_order.py:37,93`; `test/test_interaction_boundary_revocation.py:21`; `test/test_interaction_conversation_offer_context.py:41`; `test/test_interaction_expression_consistency.py:63`; `test/test_interaction_live_boundaries.py:39`; `test/test_interaction_opt_in_live_offer.py:60`; `test/test_interaction_preference_context.py:25`; `test/test_interaction_reviewed_hug_question.py:58`; `test/test_interaction_source_link.py:25`; `test/test_interaction_trusted_offer_gate.py:36`.
- `VerifiedInteractionState.__init__` (line 23): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `VerifiedInteractionState._required` (line 42): `src/sofia/distributed/agent_main.py:90,92,93,97,98,99,100,103`.
- `VerifiedInteractionState._attest` (line 47): no external lexical candidates.
- `VerifiedInteractionState.assert_source_unchanged` (line 88): `test/test_interaction_source_link.py:34,38`.
- `VerifiedInteractionState.record_preference` (line 101): `test/test_interaction_live_boundaries.py:65`; `test/test_interaction_preference_context.py:38,71`; `test/test_interaction_source_link.py:29,43`; `test/test_interaction_temporal.py:26`.
- `VerifiedInteractionState.record_boundary` (line 114): `src/sofia/interaction/disposable_live_offer_probe.py:165`; `test/test_interaction_atomic_offer_release.py:74,105`; `test/test_interaction_boundary_revocation.py:23,28,33`; `test/test_interaction_conversation_offer_context.py:88`; `test/test_interaction_live_boundaries.py:49,87`; `test/test_interaction_opt_in_live_offer.py:111`; `test/test_interaction_preference_context.py:47,61`; `test/test_interaction_source_link.py:51,59`; `test/test_interaction_temporal.py:34`; `test/test_interaction_trusted_offer_gate.py:51,131`.

### `src/sofia/interaction/target_body.py`

Production/test importers: `src/sofia/interaction/__init__.py`, `src/sofia/interaction/initiative.py`, `src/sofia/interaction/representation.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from types import MappingProxyType`
- `from typing import Mapping`

Definitions:

- `TargetRegion` (line 42): no external lexical candidates.
  Data declarations: `region_id: str`; `private: bool = False`.
- `TargetRegion.__post_init__` (line 46): no external lexical candidates.
- `RepresentedTargetBody` (line 53): `src/sofia/interaction/initiative.py:196`; `src/sofia/interaction/representation.py:258,274`.
- `RepresentedTargetBody.__init__` (line 60): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `RepresentedTargetBody.has_region` (line 85): no external lexical candidates.
- `RepresentedTargetBody.require_region` (line 88): `src/sofia/interaction/representation.py:278`.

Module declarations: `_DEFAULT_TARGET_REGIONS = ('head', 'hair', 'forehead', 'face', 'cheek', 'mouth', 'neck', 'shoulder', 'upper-arm', 'forearm', 'hand', 'chest', 'upper-back', 'lower-back', 'waist', 'side', 'hip', 'thigh', 'knee', 'lower-leg', 'foot', 'buttocks', 'groin')`; `_PRIVATE_TARGET_REGIONS = frozenset({'chest', 'buttocks', 'groin'})`.

### `src/sofia/interaction/temporal.py`

Production/test importers: `src/sofia/interaction/source_link.py`, `test/test_interaction_temporal.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import contextmanager`
- `from dataclasses import dataclass`
- `from datetime import datetime, timezone`
- `from pathlib import Path`
- `import sqlite3`
- `from typing import Iterator`
- `from sofia.interaction.registry import ACTION_DEFINITIONS, GESTURE_DEFINITIONS, InteractionCatalog`

Definitions:

- `_id` (line 23): `src/sofia/act/delivery.py:98,105,221,263,392,415,416`; `src/sofia/act/outreach.py:65,66,74,112,184`; `src/sofia/avatar/presentation.py:154,209,220,270,305,420,512,559,599,608`; `src/sofia/avatar/wardrobe_planner.py:88,236,240,286,287,304,306`; `src/sofia/evolve/approval.py:52,53,60,61`; `src/sofia/evolve/revision.py:74,77,87,133,134,138,139,318,373`; `src/sofia/habits/recorder.py:57,94`; `src/sofia/interaction/goal_journal.py:89,90,117,166,167,168,212`; `src/sofia/interaction/initiative.py:79,111`; `src/sofia/interaction/ledger.py:94,103,104,139,140,176`; `src/sofia/interaction/world.py:45,49,114,121,126,127`; `src/sofia/run/lease.py:130`; `src/sofia/ui/workbench.py:77,96,97,122,123,153,164,187,232,263,292,368,406`.
- `_time` (line 29): `src/sofia/act/system_notice.py:140,141,374`; `src/sofia/evolve/amendment.py:82,97,98,126,127,129`; `src/sofia/evolve/approval.py:62,99,100`; `src/sofia/interaction/goal_journal.py:98,125,172`; `src/sofia/interaction/initiative.py:75,76,91`; `src/sofia/ops/activity.py:113,129`; `src/sofia/ui/workbench.py:103,130,131,169`.
- `PreferenceRevision` (line 36): no external lexical candidates.
  Data declarations: `id: str`; `subject: str`; `semantic_id: str`; `region_id: str`; `context: str`; `direction: str`; `origin: str`; `source_id: str`; `prior_id: str | None`; `recorded_at: str`.
- `BoundaryRevision` (line 50): no external lexical candidates.
  Data declarations: `id: str`; `subject: str`; `semantic_id: str`; `region_id: str`; `active: bool`; `source_id: str`; `prior_id: str | None`; `recorded_at: str`.
- `InteractionStateJournal` (line 61): `src/sofia/interaction/source_link.py:32`; `test/test_interaction_temporal.py:14,48`.
- `InteractionStateJournal.__init__` (line 64): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `InteractionStateJournal._connection` (line 92): `src/sofia/conversation/store.py:30,48,51,227,230,231,234,239`; `src/sofia/filesystem/observation.py:246,399,401,405,408,410,411,414,416`; `src/sofia/memory/chatgpt_import_store.py:22,237,239,240,243,245`; `src/sofia/memory/store.py:27,30,39,42,52,61,65,84,91,94,114,119,139,141,154,155,156`; `src/sofia/ui/drafts.py:57,62,64,164,165,166,169,171`; `test/test_interaction_avatar_world_probe_cleanup.py:33,34,36`.
- `InteractionStateJournal._scope` (line 100): `src/sofia/authorization/evaluator.py:68,72,152`; `src/sofia/personality/reflection.py:293,342,369,614,644`; `src/sofia/state/sqlite_plane.py:129,147,247`.
- `InteractionStateJournal._latest` (line 109): no external lexical candidates.
- `InteractionStateJournal._append` (line 117): no external lexical candidates.
- `InteractionStateJournal.record_preference` (line 131): `src/sofia/interaction/source_link.py:108`; `test/test_interaction_live_boundaries.py:65`; `test/test_interaction_preference_context.py:38,71`; `test/test_interaction_source_link.py:29,43`; `test/test_interaction_temporal.py:26`.
- `InteractionStateJournal.preference` (line 151): `src/sofia/avatar/wardrobe_planner.py:410,411,414,415,416,417,420,421`; `src/sofia/interaction/evolved_preference.py:72,73,76,77,78,83,140,141`; `src/sofia/interaction/expanded_service.py:81,236`; `src/sofia/interaction/preference_context.py:24,101,107`; `test/test_avatar_starter_user_preferences.py:74,75,80,81,82,84,85`; `test/test_interaction_preference_context.py:45,54`; `test/test_interaction_source_link.py:48`; `test/test_interaction_temporal.py:39,40,41,42,44,46,49,50,74,76,78,82`.
- `InteractionStateJournal.preference_history` (line 160): `test/test_interaction_temporal.py:47,51,83`.
- `InteractionStateJournal.record_boundary` (line 171): `src/sofia/interaction/disposable_live_offer_probe.py:165`; `src/sofia/interaction/source_link.py:120`; `test/test_interaction_atomic_offer_release.py:74,105`; `test/test_interaction_boundary_revocation.py:23,28,33`; `test/test_interaction_conversation_offer_context.py:88`; `test/test_interaction_live_boundaries.py:49,87`; `test/test_interaction_opt_in_live_offer.py:111`; `test/test_interaction_preference_context.py:47,61`; `test/test_interaction_source_link.py:51,59`; `test/test_interaction_temporal.py:34`; `test/test_interaction_trusted_offer_gate.py:51,131`.
- `InteractionStateJournal.boundary_active` (line 188): `test/test_interaction_source_link.py:64,66`; `test/test_interaction_temporal.py:58`.

Module declarations: `DIRECTIONS = frozenset({'enjoy', 'dislike', 'mixed', 'neutral', 'unknown'})`; `PARTICIPANTS = frozenset({'user', 'sofia'})`.

### `src/sofia/interaction/trusted_offer_gate.py`

Production/test importers: `src/sofia/interaction/atomic_offer_release.py`, `src/sofia/interaction/disposable_live_offer_probe.py`, `src/sofia/interaction/live_offer_service.py`, `src/sofia/interaction/question_clarification_service.py`, `test/test_interaction_atomic_offer_release.py`, `test/test_interaction_atomic_offer_writer_order.py`, `test/test_interaction_conversation_offer_context.py`, `test/test_interaction_expression_consistency.py`, `test/test_interaction_reviewed_hug_question.py`, `test/test_interaction_trusted_offer_gate.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `from dataclasses import dataclass`
- `from pathlib import Path`
- `import re`
- `import sqlite3`
- `from sofia.cognition.model import CognitiveRequest`
- `from sofia.interaction.action_grammar import parse_user_action`
- `from sofia.interaction.offer_route import OFFER`
- `from sofia.interaction.conversation_offer_context import routed_conversation_choice_request, routed_conversation_expression_request`
- `from sofia.interaction.decision_expression import CandidateChoice, ReviewedFrame, TextProvider, audit_expression, from_reviewed_action, parse_choice`
- `from sofia.interaction.decision_reason_audit import audit_decision_reason`
- `from sofia.interaction.expression_consistency import validate_offer_expression`
- `from sofia.interaction.preference_context import read_interaction_context`

Definitions:

- `GuardedOfferResult` (line 37): `src/sofia/interaction/atomic_offer_release.py:45,58`; `src/sofia/interaction/disposable_live_offer_probe.py:184`; `src/sofia/interaction/live_offer_service.py:149`; `src/sofia/interaction/question_clarification_service.py:71,72`; `test/test_interaction_atomic_offer_release.py:44,179,181,183,185`; `test/test_interaction_atomic_offer_writer_order.py:45,111`; `test/test_interaction_expression_consistency.py:108`; `test/test_interaction_reviewed_hug_question.py:65`.
  Data declarations: `status: str`; `choice: CandidateChoice | None = None`; `response: str | None = None`; `decision_findings: tuple[str, ...] = ()`; `expression_findings: tuple[str, ...] = ()`.
- `_policy_gate` (line 47): `src/sofia/interaction/atomic_offer_release.py:99`; `src/sofia/interaction/disposable_live_offer_probe.py:178`; `src/sofia/interaction/live_offer_service.py:147`; `src/sofia/interaction/question_clarification_service.py:70`; `test/test_interaction_atomic_offer_writer_order.py:100`.
- `run_guarded_offer` (line 80): `src/sofia/interaction/disposable_live_offer_probe.py:97`; `src/sofia/interaction/live_offer_service.py:157`; `test/test_interaction_conversation_offer_context.py:81,131`; `test/test_interaction_expression_consistency.py:96`; `test/test_interaction_trusted_offer_gate.py:103,199,219,222`.

Module declarations: `_SESSION_ID = re.compile('^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$')`; `_REQUIRED_TABLES = ('conversation_messages', 'interaction_session_controls', 'interact_boundary_revisions', 'interact_evidence_attestations')`.

### `src/sofia/interaction/world.py`

Production/test importers: `src/sofia/interaction/chat.py`, `src/sofia/interaction/world_observation.py`, `src/sofia/interaction/world_setup.py`, `src/sofia/interaction/world_text.py`, `test/test_interaction_world_location.py`, `test/test_interaction_world_observation.py`, `test/test_interaction_world_text.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime, timezone`
- `import json`
- `from pathlib import Path`
- `import re`
- `import sqlite3`

Definitions:

- `_id` (line 21): `src/sofia/act/delivery.py:98,105,221,263,392,415,416`; `src/sofia/act/outreach.py:65,66,74,112,184`; `src/sofia/avatar/presentation.py:154,209,220,270,305,420,512,559,599,608`; `src/sofia/avatar/wardrobe_planner.py:88,236,240,286,287,304,306`; `src/sofia/evolve/approval.py:52,53,60,61`; `src/sofia/evolve/revision.py:74,77,87,133,134,138,139,318,373`; `src/sofia/habits/recorder.py:57,94`; `src/sofia/interaction/goal_journal.py:89,90,117,166,167,168,212`; `src/sofia/interaction/initiative.py:79,111`; `src/sofia/interaction/ledger.py:94,103,104,139,140,176`; `src/sofia/interaction/temporal.py:140,142,177,178`; `src/sofia/run/lease.py:130`; `src/sofia/ui/workbench.py:77,96,97,122,123,153,164,187,232,263,292,368,406`.
- `_utc` (line 27): `src/sofia/act/delivery.py:222,223,393,423,580`; `src/sofia/act/outreach.py:77,154,186,204,229,244,246,258,304`; `src/sofia/dev/approval.py:75`; `src/sofia/distributed/durable.py:74,198`; `src/sofia/distributed/inference_control.py:113,210`; `src/sofia/evolve/executor.py:337,441`; `src/sofia/evolve/revision.py:94,108,109,140,268,270,271,336,337,339,440`; `src/sofia/habits/engine.py:102,206,241,274,306`; `src/sofia/habits/expectations.py:211,212,213,275`; `src/sofia/interaction/ledger.py:109,141`; `src/sofia/interaction/representation.py:162,304`; `src/sofia/memory/provenance_store.py:117,146`; `src/sofia/personality/clarification.py:89,109`; `src/sofia/personality/reflection.py:58,291,368,512,567,568,613,660`; `src/sofia/run/heartbeat.py:33,82,159`; `src/sofia/run/lease.py:131,251,322,378`; `src/sofia/run/periodic.py:53,106`; `src/sofia/run/supervisor.py:293`; `src/sofia/state/migration_lease.py:44,45,120,190`.
- `WorldAction` (line 34): `src/sofia/interaction/world_text.py:83`; `test/test_interaction_world_location.py:13,107`; `test/test_interaction_world_observation.py:32`; `test/test_interaction_world_text.py:70,74`.
  Data declarations: `request_id: str`; `actor_id: str`; `verb: str`; `target_id: str`; `evidence_ref: str`; `occurred_at: datetime`; `tool_id: str | None = None`.
- `WorldAction.__post_init__` (line 43): no external lexical candidates.
- `WorldAction.payload` (line 54): `src/sofia/act/delivery.py:687,689`; `src/sofia/act/system_notice.py:320,349,376,451,462,466,471,482`; `src/sofia/application/act_service.py:262,264,268,272,279`; `src/sofia/application/fleet_runtime.py:79,96`; `src/sofia/avatar/presentation_store.py:55,57`; `src/sofia/avatar/wardrobe_catalog.py:604,622`; `src/sofia/cognition/model_lifecycle.py:55,57,58,60`; `src/sofia/config/state_store.py:55,57,58,59,60,61,62,63,64,66,67`; `src/sofia/dev/capability.py:81,83,93`; `src/sofia/dev/release.py:121,144,152,154`; `src/sofia/dev/release_store.py:32,34,45`; `src/sofia/discord/store.py:149,153`; `src/sofia/distributed/agent.py:187,253,303,304,318,319,320,321`; `src/sofia/distributed/agent_main.py:125,126,129,138,139,141,144,147,149,151,159,160,172,175,178,180`; `src/sofia/distributed/https_transport.py:59`; `src/sofia/distributed/inference.py:96,118,157,160,165,171,178,223,226,233,239,243,249,294,299,304,314,320,357,360,376,382,387,388,389,390,437,457,461,468,473,486,490,518,519,520,540,579,597,601,608,613,619,623,639,640`; `src/sofia/distributed/inference_client.py:134,136`; `src/sofia/evolve/amendment.py:100,106`; `src/sofia/evolve/state_plane_adapter.py:155,156,158`; `src/sofia/habits/engine.py:28,36`; `src/sofia/habits/recorder.py:35,36`; `src/sofia/integrations/http.py:31,32`; `src/sofia/integrations/jmri.py:27,29,30`; `src/sofia/interaction/avatar_world.py:54,58`; `src/sofia/interaction/decision_expression.py:285,304`; `src/sofia/interaction/focused_probe.py:70,73,87`; `src/sofia/interaction/representation.py:341,370`; `src/sofia/knowledge/lifecycle.py:40,43`; `src/sofia/machine/location.py:136,143,147,150,152,229,251`; `src/sofia/machine/persistence.py:465,479,496,512,546,548,582,587`; `src/sofia/memory/chatgpt_export.py:256,262,264`; `src/sofia/memory/chatgpt_import.py:76,83,84,102,104,124,131`; `src/sofia/memory/import_chatgpt.py:104,105,118`; `src/sofia/ops/agent_discovery.py:125,128,130,157,159,160,161,162,164`; `src/sofia/ops/backup.py:61,64,99,102,348,349,353`; `src/sofia/ops/durable_lease.py:26,36`; `src/sofia/ops/history.py:16,18,61,62,63,64,69,71,125,127`; `src/sofia/ops/local_telemetry.py:69,70,72,165,168,169,170,171`; `src/sofia/ops/windows_bootstrap.py:451,455,456,457,459,460,461,462,463,464`; `src/sofia/ops/windows_rekey_bootstrap.py:64,65,68,69,70,71,72,81,93,178,252`; `src/sofia/personality/emotion.py:383,408,418,473,488,490`; `src/sofia/personality/probe.py:92,97`; `src/sofia/personality/thought_agent.py:84,130`; `src/sofia/safe/audit.py:88,97,111,137,148`; `src/sofia/system/windows.py:187,189,190,192,199,286,288,293,294,295,429,431,437,440,443,446,449,682,684,685,687,694,917,918,919,920,921`; `src/sofia/ui/desktop.py:569,574,590,594,612,614,616,617,618,630,632,634,635,636,648,659,661,663,664,665,673,680,682,683,684,696`; `src/sofia/ui/desktop_worker.py:95,185,189,196,233`; `src/sofia/ui/remote_transport.py:245,300,301,302,400`; `src/sofia/ui/runtime_authority.py:93,109`; `src/sofia/verify/dual_cognition.py:260,264,271`; `src/sofia/verify/semantic_integrity.py:451,455,456`; `src/sofia/cognition/matrix/trace.py:290,294,298,300,302`; `test/test_act_delivery.py:157,316`; `test/test_act_runtime_wiring.py:148,151`; `test/test_act_system_notice.py:79,137`; `test/test_body_package.py:146,147`; `test/test_dev_supply_chain.py:84,85,86`; `test/test_distributed_agent_main.py:15,26,28,63,64,65,73,74,75,76`; `test/test_distributed_inference.py:185,186,192`; `test/test_distributed_inference_transport.py:66`; `test/test_machine_inventory_persistence.py:101,105,106,107,116,119,124,129,142,145,150,184,189,384,388,393`; `test/test_machine_regression.py:118,119`; `test/test_ops_agent_discovery.py:32,35`; `test/test_ops_backup_restore.py:146,147,149,198,200`; `test/test_ops_windows_rekey_bootstrap.py:66,73,74,77,78,79`; `test/test_runtime_user_settings.py:280,281,282,283,294`; `test/test_system_windows_backend.py:397,399,402,405,410,860,872,893,905`; `test/test_thought_agent.py:151,152,153,154,189,190,191,192`; `test/test_ui_desktop_worker.py:68,70,75,77,78,80,82,86,88,89,91,93,106,108,160,162,167,169,170,172,174,180,182`; `test/test_verify_dual_cognition.py:60,61,62`.
- `WorldOutcome` (line 62): `src/sofia/interaction/world_text.py:31`.
  Data declarations: `request_id: str`; `status: str`; `reason: str`; `actor_id: str`; `verb: str`; `target_id: str`.
- `LabWorld` (line 71): `src/sofia/interaction/chat.py:745`; `src/sofia/interaction/world_observation.py:47`; `src/sofia/interaction/world_setup.py:21,27`; `src/sofia/interaction/world_text.py:44,51,90,92`; `test/test_interaction_world_location.py:21,22,33,37,51,56,68,72,85,98,114,117,119`; `test/test_interaction_world_observation.py:25,26,31,64,66`; `test/test_interaction_world_text.py:23,33,42,53,59,66,67,99`.
- `LabWorld.__init__` (line 78): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `LabWorld._connect` (line 107): `src/sofia/act/delivery.py:130,225,264,394,425,541,591`; `src/sofia/act/system_notice.py:45,172,311,377`; `src/sofia/application/background.py:44,73,148`; `src/sofia/application/idle_reflection.py:42,61,86`; `src/sofia/cognition/activity.py:60,106,169,178`; `src/sofia/config/user_settings.py:322,397,427`; `src/sofia/discord/binding.py:70,128,198,243,316,405,497`; `src/sofia/discord/delivery.py:106,153,240,280,320,354,409,425,437`; `src/sofia/discord/store.py:81,181,242,289,369,458,496,545,604,627,639`; `src/sofia/distributed/durable.py:50,180`; `src/sofia/distributed/inference_control.py:85,115,143,160`; `src/sofia/evolve/executor.py:114,318,381,472`; `src/sofia/evolve/revision.py:234,319,387,467`; `src/sofia/interaction/ledger.py:67,95,110,143,177`; `src/sofia/memory/chatgpt_export_store.py:61,163,291,325,415,442`; `src/sofia/memory/chatgpt_migration.py:36,114,174,200`; `src/sofia/operational/store.py:41,66,148,195`; `src/sofia/ops/activity.py:73,114,130,160`; `src/sofia/personality/clarification.py:47,91,112`; `src/sofia/personality/emotion.py:244,400,477,598,665,702,780,803,872`; `src/sofia/personality/reflection.py:313,343,370,467,488,514,573,617,630,645,661`; `src/sofia/run/heartbeat.py:49,83,127`; `src/sofia/run/lease.py:60,135,257,323,379,404`; `src/sofia/run/periodic.py:78,130,188,216`; `src/sofia/run/supervisor.py:130,301,321,563`; `src/sofia/safe/audit.py:24,104,198`; `src/sofia/safe/dev_approval.py:24,49,109`; `src/sofia/social/store.py:24,49,108`; `src/sofia/state/component_schema.py:36,73,127,170`; `src/sofia/state/sqlite_plane.py:36,82,120,148,238,269`; `src/sofia/ui/control_center.py:133,157,206`; `src/sofia/ui/remote_transport.py:140,165,190,204`; `src/sofia/verify/semantic_integrity.py:82,429`; `src/sofia/cognition/matrix/trace.py:56,477,527,538,568,596`; `test/test_interaction_i5_i7_batch.py:95`; `test/test_runtime_user_settings.py:189,252,261`.
- `LabWorld.add_room` (line 113): `src/sofia/interaction/world_setup.py:38`; `test/test_interaction_world_location.py:23,24`.
- `LabWorld.add_actor` (line 120): `src/sofia/interaction/world_setup.py:36`; `test/test_interaction_world_location.py:25,26`.
- `LabWorld.add_object` (line 125): `src/sofia/interaction/world_setup.py:48`; `test/test_interaction_world_location.py:27,28,29`.
- `LabWorld.snapshot` (line 135): `src/sofia/application/background_runtime.py:74`; `src/sofia/application/bootstrap.py:359,468,508,690`; `src/sofia/application/conversation_service.py:403`; `src/sofia/application/emotional_conversation.py:369,470`; `src/sofia/avatar/presentation.py:495,497,498,499,502,555,587`; `src/sofia/avatar/presentation_runtime.py:91,93,99,150,158`; `src/sofia/avatar/presentation_store.py:55,106,123`; `src/sofia/avatar/wardrobe_planner.py:157,161,167,170,201,202`; `src/sofia/clean/__main__.py:16,17,18,19,48,87`; `src/sofia/clean/recovery.py:15,90,99,101,104,105,106`; `src/sofia/environment/prompt.py:51,66,69,73,99,101,108,111,114,130,146,149,153,180,184,186,194,196,198,200,202,204,213,216,217,220,264,271,276,279,280,287,291,295,296,301,304`; `src/sofia/environment/query.py:54,57,59,65,372,415,426,437,446,450,455,459,466,474,481,484,491,494,511,512,514,515,525,541,542,544,553,555,564,567,586,605,608,611,616,621,670,673,687,689,714,716,728,733,738,748,753,756,764,766,768,799,802,810,812,814,843,846,866,867,876,881,882,891,895,898,928,938,942,954`; `src/sofia/interaction/world_observation.py:47,48,51,54,60,61`; `src/sofia/interaction/world_setup.py:29`; `src/sofia/interaction/world_text.py:72,74,76,80,95`; `src/sofia/ops/backup.py:284,285,289`; `src/sofia/ops/telemetry.py:9,10,11,12`; `src/sofia/runtime/response.py:266,329`; `src/sofia/runtime/evidence.py:102,103,115,117,118,125,128,147,148,157,162,181,182`; `src/sofia/ui/desktop_controller.py:165`; `src/sofia/ui/workbench.py:369,371,373,375,379,390,406`; `test/test_application.py:244`; `test/test_avatar_clothing_action.py:558,573`; `test/test_avatar_presentation.py:177,184,235,236,242,258,259,270`; `test/test_avatar_presentation_runtime.py:47,101,143,155`; `test/test_avatar_presentation_store.py:123,124,138,154,177,189,213`; `test/test_avatar_wardrobe_environment_context.py:63,70,72,80,119,125`; `test/test_clean_package.py:93,99,100,101,102,103,106,109`; `test/test_distributed_peer_knowledge.py:40,45,54,70,82,104,112,128`; `test/test_distributed_reachability.py:29,117`; `test/test_emotional_behavior_matrix.py:43,118`; `test/test_environment_acceptance.py:60,62,63,64,65,66,67,68,82,87,88,92,108,113,114,118`; `test/test_environment_behavior_matrix.py:53,78,114,118,143,155,159,176,186,215,308,312,317,324`; `test/test_environment_prompt.py:43,44,54,55,73,88,103,107,123,127,135,136,153,173,193,198`; `test/test_environment_query.py:47,50,57,60,80,92,99,102,110,113,141,153,171,183,192,195,210,213,219,241,253,295,320,364,387,415,418,422,438,450,458,466,481,503,521,527,545,551,560,565,566,584,590,600,606,624,637,659,672`; `test/test_environment_service.py:47,48,49,50,51,52,53,54,72,76,77,78,93,103,104,105,106,107,108,123,133,134,135,136,151,161,162,163,164,175,183,184,190,191,193,199,203,204,205,220,227,228,244,251,266,270,281,286,300,310,311,312,313,317,320`; `test/test_interaction_world_location.py:34,38,52,53,86,89,99,109,115`; `test/test_interaction_world_observation.py:55,64,66,102,108`; `test/test_interaction_world_text.py:40,43,44,54,56,62,79,100,101`; `test/test_ui_workbench.py:157,164,165,166,177,194,195,197,220,230,231,233,287`.
- `LabWorld.perform` (line 144): `src/sofia/interaction/world_text.py:86`; `test/test_interaction_world_location.py:40,41,44,45,47,48,50,57,58,61,62,66,73,75,77,79,82,87,88,90,91,92,93,94`; `test/test_interaction_world_observation.py:32`; `test/test_interaction_world_text.py:70,74`.
- `LabWorld._transition` (line 171): `src/sofia/discord/binding.py:277,289,301`; `src/sofia/memory/provenance.py:80,83,86`; `src/sofia/memory/provenance_store.py:311,318,325`.

Module declarations: `_ID = re.compile('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')`; `_ACTIONS = frozenset({'enter', 'leave', 'pick_up', 'put_down', 'work_on', 'finish_work'})`.

### `src/sofia/interaction/world_observation.py`

Production/test importers: `src/sofia/interaction/chat.py`, `test/test_interaction_world_observation.py`.

Imports:

- `from __future__ import annotations`
- `import json`
- `from pathlib import Path`
- `import re`
- `from sofia.interaction.world import LabWorld`
- `from sofia.interaction.world_setup import lab_state_path`

Definitions:

- `is_lab_status_query` (line 24): no external lexical candidates.
- `lab_observation_prompt` (line 34): `src/sofia/interaction/chat.py:733`; `test/test_interaction_world_observation.py:22`.

Module declarations: `_LAB_STATUS = re.compile("^sof[ií]a,?\\s+(?:where are you|what are you holding|what(?:'s| is) in (?:the |your )?lab|what are you working on|show me (?:the |your )lab)\\s*[?.!]?$", re.IGNORECASE)`.

### `src/sofia/interaction/world_setup.py`

Production/test importers: `src/sofia/interaction/chat.py`, `src/sofia/interaction/world_observation.py`, `src/sofia/runtime/internal_workspace.py`, `test/test_interaction_world_internal_noise.py`, `test/test_interaction_world_observation.py`, `test/test_interaction_world_text.py`.

Imports:

- `from __future__ import annotations`
- `from pathlib import Path`
- `from sofia.interaction.world import LabWorld`

Definitions:

- `lab_state_path` (line 14): `src/sofia/interaction/chat.py:745`; `src/sofia/interaction/world_observation.py:42`; `src/sofia/runtime/internal_workspace.py:37`; `test/test_interaction_world_internal_noise.py:28,61`; `test/test_interaction_world_observation.py:26,41,64,66,79,116`; `test/test_interaction_world_text.py:99,117`.
- `provision_starter_lab` (line 21): `src/sofia/interaction/chat.py:746`; `test/test_interaction_world_observation.py:27`; `test/test_interaction_world_text.py:24,69`.

### `src/sofia/interaction/world_text.py`

Production/test importers: `src/sofia/interaction/chat.py`, `test/test_interaction_world_text.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime`
- `import json`
- `import re`
- `from sofia.interaction.world import LabWorld, WorldAction, WorldOutcome`

Definitions:

- `LabTextResult` (line 28): no external lexical candidates.
  Data declarations: `status: str`; `reason: str`; `outcome: WorldOutcome | None = None`.
- `_match_name` (line 34): no external lexical candidates.
- `handle_lab_command` (line 44): `src/sofia/interaction/chat.py:747`; `test/test_interaction_world_text.py:29`.
- `world_prompt` (line 90): `src/sofia/interaction/chat.py:753`.

Module declarations: `_COMMAND = re.compile('^sof[ií]a\\s*,?\\s+(?P<verb>enter|go to|leave|pick up|put down|work on|finish work on)\\s+(?P<target>.+?)\\s*[.!]?$', re.IGNORECASE)`; `_WITH = re.compile('^(?P<target>.+?)\\s+with\\s+(?P<tool>.+)$', re.IGNORECASE)`; `_VERBS = {'enter': 'enter', 'go to': 'enter', 'leave': 'leave', 'pick up': 'pick_up', 'put down': 'put_down', 'work on': 'work_on', 'finish work on': 'finish_work'}`.

