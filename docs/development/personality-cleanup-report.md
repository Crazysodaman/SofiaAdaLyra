# Phase 4: personality cleanup

## What was there and file classification

Sixteen original modules mixed stable personality, thought/reflection persistence,
emotional state, offline prototype observation harnesses and a runnable audit CLI.

| Original file | Decision | Responsibility / outcome |
| --- | --- | --- |
| `__init__.py` | KEEP | Existing empty package marker. |
| `model.py` | KEEP | Canonical immutable PersonalityProfile used by runtime/cognition/store. |
| `store.py` | KEEP | Atomic JSON persistence read by composition/runtime and operator/probe tooling. |
| `expression.py` | KEEP | Stable expression guidance inserted by cognition assembler. |
| `influence.py` | KEEP, FIX imports | Current contextual influence for application, cognition, voice and ACT. |
| `reflection.py` | KEEP, DELETE dead methods | Canonical scoped thought journal and ACT staging outbox. |
| `reflection_query.py` | KEEP | Runtime's deterministic reporting of actually recorded thoughts. |
| `thought_agent.py` | KEEP, FIX imports | Application/idle-worker bounded model reflection boundary. |
| `observation_bridge.py` | KEEP, DELETE dead bridges | Actual bootstrap workspace-delta ingestion only. |
| `emotion.py` | MOVE to emotion/journal.py | Emotional persistence belongs to EMOTION. |
| `clarification.py` | MOVE to emotion/clarification.py | Notes reference emotional events and revisions. |
| `audit.py` | MOVE to verify/reflection_audit.py | Explicit runnable read-only operator diagnostic. |
| `system.py` | DELETE | Test-only wrapper duplicating direct profile fields and context projection. |
| `probe.py` | DELETE | Prototype bounded harness reached only by its own tests, no CLI/production caller. |
| `evaluation.py` | DELETE | Second test-only prototype harness, no production/CLI entry point. |
| `review.py` | DELETE | Wrapper over that retired prototype observation, only its own tests. |

## Production traces and canonical state

Runtime opens PersonalityStore and passes PersonalityProfile to CognitiveContext;
the assembler consumes its fields directly and adds expression guidance. There
is no PersonalitySystem in this chain. Application constructs ReflectionJournal,
records actual workspace deltas through observation_bridge, and runs ThoughtAgent
through the existing runtime. Idle reflection and conversation history call
reflect_due. Runtime reflection queries read recent_thoughts and resolve recorded
content. ACT reads pending, queues into its authorized delivery owner, and calls
mark_outbox_bridged; ReflectionJournal does not deliver messages. Its serializer,
calendar helpers, SQL schema/migration, context manager and token matcher are all
internal callers on these production operations.

ContinuityInfluence.from_state/prompt and outreach_salience are called by bootstrap,
background work, conversation and ACT; daypart supports environment-aware influence.
Stable personality JSON, scoped reflection rows and emotional journal rows retain
their distinct ownership. Moving emotional classes changes Python ownership only;
SQL table names, schemas, migrations, stored values and instance ownership are unchanged.

## What was wrong, deleted, moved, renamed, merged, and fixed

Remove the direct-field PersonalitySystem wrapper and its five exclusive tests;
keep the profile's tests. Delete the two prototype harnesses and their review model
with their exclusive test modules: tests alone did not justify runtime package code.
The production personality pipeline/provider/embodiment/expression tests remain.

Delete record_verified_test_run (no actual result producer) and
record_user_reappraisal (unwired alternate correction bridge), plus their two
exclusive tests. Keep actual workspace ingestion, self-noise exclusion and startup
integration tests. The application already owns persisted-message validation and
ClarificationJournal association; there is no fictional test-result observation path.

Remove ReflectionJournal.due_followups (no reader) and confirm_delivery (explicitly
future-adapter code, own-test caller only). Preserve actual defer_followup writes
and persisted deferred records from ThoughtAgent's share-later path. No autonomous
follow-up processing is implied. Preserve queue deduplication, spacing and evidence
link tests; replace only their retired confirmation calls with the real ACT bridged
transition, including rejection of a second bridge. Actual delivery acknowledgment
continues to belong to ACT.

Move emotional journal/clarifications to their owner and the explicit read-only CLI
to verify; repair all application, UI, personality, test and current documentation
imports/references. No compatibility aliases remain. No merge was needed for the
remaining distinct stable profile, influence, reflection and language responsibilities.

## What remains and verification

Nine personality modules retain active production responsibilities. Emotion owns
its persistence; verify owns the runnable content-free reflection audit. Retired
names are absent from current source/test/docs; historical cleanup inventories are
kept as history. Compile and whitespace checks passed. Gate covering personality,
reflection, workspace ingestion, thought generation, emotional integration, idle
work, UI theme, ACT wiring and cognition matrix: **267 passed** (5.58 s).
Package ownership regression gate: **18 passed** (0.47 s). The first full run
found emotion missing from the test module ownership map; add its canonical core
classification and a fixture regression rather than a filename fallback. Final
full suite: **3,549 passed, 8 known failures, 2 skipped** (115.69 s). The 22 fewer
passing cases are the retired prototype/wrapper/bridge tests; the same five
unavailable-Ollama and three platform failures remain. No new failure, and live
integration tests remain enabled. Emotional journal and clarification moves were
verified AST-identical.

Commit: `git log -1 --format=%H -- docs/development/personality-cleanup-report.md`.


## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/personality/__init__.py`

Production/test importers: none in direct absolute imports.

Imports:

None.

Definitions:


### `src/sofia/personality/audit.py`

Production/test importers: `test/test_reflection_audit.py`.

Imports:

- `from __future__ import annotations`
- `from collections import Counter`
- `from hashlib import sha256`
- `import json`
- `from pathlib import Path`
- `import sqlite3`
- `from urllib.parse import quote`
- `from sofia.config.defaults import create_production_configuration`

Definitions:

- `_sqlite_uri_for_path` (line 17): `test/test_reflection_audit.py:13,16,19`.
- `reflection_audit` (line 31): `test/test_reflection_audit.py:26,27,35,59,75`.
- `main` (line 97): `src/sofia/__main__.py:102`; `src/sofia/clean/__main__.py:106`; `src/sofia/dev/dependency_lock.py:174`; `src/sofia/dev/release_cli.py:144`; `src/sofia/discord/__main__.py:25`; `src/sofia/distributed/agent_main.py:257`; `src/sofia/distributed/fleet_probe.py:258`; `src/sofia/distributed/operator.py:111`; `src/sofia/distributed/pki.py:349`; `src/sofia/distributed/systemd_agent_service.py:213`; `src/sofia/distributed/windows_agent_service_admin.py:264`; `src/sofia/environment/settings_cli.py:163`; `src/sofia/machine/location_cli.py:212`; `src/sofia/memory/import_chatgpt.py:167`; `src/sofia/ops/backup_cli.py:171`; `src/sofia/ops/discovery_canary.py:165`; `src/sofia/ops/windows_bootstrap.py:568`; `src/sofia/ops/windows_rekey_bootstrap.py:264`; `src/sofia/run/host.py:224`; `src/sofia/run/runtime_child.py:93`; `src/sofia/run/service_admin.py:279`; `src/sofia/run/windows_acceptance.py:159`; `src/sofia/safe/approve_execution.py:96`; `src/sofia/safe/capability_policy_cli.py:55`; `src/sofia/safe/dev_approve.py:121`; `src/sofia/safe/evolve_approve.py:113`; `src/sofia/safe/operator_stop_cli.py:50`; `src/sofia/ui/__main__.py:7`; `src/sofia/ui/desktop.py:934`; `src/sofia/ui/settings_window.py:898`; `src/sofia/ui/tray_agent.py:645`; `src/sofia/verify/dual_cognition.py:280`; `src/sofia/verify/gate.py:172`; `src/sofia/verify/semantic.py:42`; `src/sofia/voice/__main__.py:70`; `src/sofia/verify/interaction/live_behavior_probe.py:334`; `src/sofia/verify/interaction/route_boundary_probe.py:162`; `src/sofia/verify/interaction/avatar_world_probe.py:133`; `src/sofia/verify/interaction/focused_probe.py:128`; `src/sofia/verify/interaction/disposable_live_offer_probe.py:214`; `src/sofia/verify/interaction/architecture_compare.py:137`; `src/sofia/verify/interaction/decision_expression_probe.py:160`; `src/sofia/verify/interaction/ab_probe.py:124`; `src/sofia/verify/interaction/boundary_counterfactual_probe.py:131`; `test/test_application.py:542,544,548,554`; `test/test_cli.py:100,127,157`; `test/test_discord_entrypoint.py:8,13,20,25`; `test/test_environment_settings_cli.py:36`; `test/test_interaction_avatar_offer_scene_probe.py:78`; `test/test_interaction_decision_reason_audit.py:92,113`; `test/test_machine_location_cli.py:61`; `test/test_model_evaluation_harness.py:138,156`; `test/test_ops_backup_cli.py:53,85,104`; `test/test_ops_discovery_canary.py:76,101`; `test/test_ui_desktop.py:24`; `test/test_ui_tray_shutdown.py:30,46`; `test/test_interaction_probe_cli.py:16`.

### `src/sofia/personality/clarification.py`

Production/test importers: `src/sofia/application/emotional_conversation.py`, `test/test_emotional_clarifications.py`, `test/test_emotional_conversation_string_path_regression.py`, `test/test_personality_journal_thread_safety.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import contextmanager`
- `from dataclasses import dataclass`
- `from datetime import datetime, timezone`
- `import json`
- `from pathlib import Path`
- `import sqlite3`

Definitions:

- `_utc` (line 17): `src/sofia/act/delivery.py:222,223,393,423,580`; `src/sofia/act/outreach.py:77,154,186,204,229,244,246,258,304`; `src/sofia/dev/approval.py:75`; `src/sofia/distributed/durable.py:74,198`; `src/sofia/distributed/inference_control.py:113,210`; `src/sofia/evolve/executor.py:337,441`; `src/sofia/evolve/revision.py:94,108,109,140,268,270,271,336,337,339,440`; `src/sofia/habits/engine.py:102,206,241,274,306`; `src/sofia/habits/expectations.py:211,212,213,275`; `src/sofia/interaction/ledger.py:109,141`; `src/sofia/interaction/world.py:52,58`; `src/sofia/memory/provenance_store.py:117,146`; `src/sofia/personality/reflection.py:58,291,368,512,567,568,613,660`; `src/sofia/run/heartbeat.py:33,82,159`; `src/sofia/run/lease.py:131,251,322,378`; `src/sofia/run/periodic.py:53,106`; `src/sofia/run/supervisor.py:293`; `src/sofia/state/migration_lease.py:44,45,120,190`.
- `_identifier` (line 23): `src/sofia/avatar/wardrobe.py:112,129,160`; `src/sofia/distributed/authorization.py:28,29`; `src/sofia/distributed/capabilities.py:37,41`; `src/sofia/distributed/operations.py:45,46,51`; `src/sofia/evolve/amendment.py:63,75`; `src/sofia/integrations/jmri.py:22,25,29`; `src/sofia/integrations/local_maintenance.py:52,67,106`; `src/sofia/personality/emotion.py:373,380,466,697`; `src/sofia/ui/drafts.py:35,36,93,94,126,127,152,153`.
- `EventClarification` (line 31): no external lexical candidates.
  Data declarations: `event_id: str`; `message_id: str`; `content: str`; `created_at: datetime`; `original_emotions: tuple[str, ...]`; `current_emotions: tuple[str, ...]`; `latest_revision_reason: str | None`.
- `ClarificationJournal` (line 41): `src/sofia/application/emotional_conversation.py:99,127,155`; `test/test_emotional_clarifications.py:25,39,55`; `test/test_emotional_conversation_string_path_regression.py:38`; `test/test_personality_journal_thread_safety.py:61`.
- `ClarificationJournal.__init__` (line 44): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `ClarificationJournal._connect` (line 63): `src/sofia/act/delivery.py:130,225,264,394,425,541,591`; `src/sofia/act/system_notice.py:45,172,311,377`; `src/sofia/application/background.py:44,73,148`; `src/sofia/application/idle_reflection.py:42,61,86`; `src/sofia/cognition/activity.py:60,106,169,178`; `src/sofia/config/user_settings.py:322,397,427`; `src/sofia/discord/binding.py:70,128,198,243,316,405,497`; `src/sofia/discord/delivery.py:106,153,240,280,320,354,409,425,437`; `src/sofia/discord/store.py:81,181,242,289,369,458,496,545,604,627,639`; `src/sofia/distributed/durable.py:50,180`; `src/sofia/distributed/inference_control.py:85,115,143,160`; `src/sofia/evolve/executor.py:114,318,381,472`; `src/sofia/evolve/revision.py:234,319,387,467`; `src/sofia/interaction/ledger.py:67,95,110,143,177`; `src/sofia/interaction/world.py:84,117,122,131,137,153`; `src/sofia/memory/chatgpt_export_store.py:61,163,291,325,415,442`; `src/sofia/memory/chatgpt_migration.py:36,114,174,200`; `src/sofia/operational/store.py:41,66,148,195`; `src/sofia/ops/activity.py:73,114,130,160`; `src/sofia/personality/emotion.py:244,400,477,598,665,702,780,803,872`; `src/sofia/personality/reflection.py:313,343,370,467,488,514,573,617,630,645,661`; `src/sofia/run/heartbeat.py:49,83,127`; `src/sofia/run/lease.py:60,135,257,323,379,404`; `src/sofia/run/periodic.py:78,130,188,216`; `src/sofia/run/supervisor.py:130,301,321,563`; `src/sofia/safe/audit.py:24,104,198`; `src/sofia/safe/dev_approval.py:24,49,109`; `src/sofia/social/store.py:24,49,108`; `src/sofia/state/component_schema.py:36,73,127,170`; `src/sofia/state/sqlite_plane.py:36,82,120,148,238,269`; `src/sofia/ui/control_center.py:133,157,206`; `src/sofia/ui/remote_transport.py:140,165,190,204`; `src/sofia/verify/semantic_integrity.py:82,429`; `src/sofia/cognition/matrix/trace.py:56,477,527,538,568,596`; `test/test_interaction_i5_i7_batch.py:95`; `test/test_runtime_user_settings.py:189,252,261`.
- `ClarificationJournal.record` (line 75): `src/sofia/application/background_runtime.py:173,174`; `src/sofia/application/conversation_matrix.py:511,551`; `src/sofia/application/emotional_conversation.py:313,397`; `src/sofia/application/fleet_runtime.py:255,258,259,260,261,266,270,272,273`; `src/sofia/avatar/wardrobe_planner.py:433`; `src/sofia/cognition/assembler.py:615,618`; `src/sofia/cognition/context_evidence.py:15,16,19,22,25,27,30,32,35,39`; `src/sofia/composition/root.py:78,91,95,96,98,99,100`; `src/sofia/config/reviewed_projection.py:169,172,176`; `src/sofia/config/state_store.py:55,81,94,104,105,106`; `src/sofia/dev/capability.py:49,103,109,111,120,121,125`; `src/sofia/dev/release_store.py:57,63,65,160,166,168`; `src/sofia/discord/delivery.py:501,505,506,509,510,520,521,527,531,532,538,539,546,547`; `src/sofia/distributed/knowledge.py:53`; `src/sofia/evolve/state_plane_adapter.py:49,50,52`; `src/sofia/external/knowledge.py:181,188,189,192,194,234,255,303,308,310`; `src/sofia/filesystem/change_capability.py:25`; `src/sofia/habits/continuity.py:82`; `src/sofia/interaction/temporal.py:140,144,148,149,177,181,186`; `src/sofia/machine/inventory.py:75,90`; `src/sofia/machine/location.py:168,182,186,205,206,207,214,218,233,234,235,236,237,238,239,240,242`; `src/sofia/machine/location_cli.py:104,112,115,117,118,200,202,203`; `src/sofia/machine/location_state.py:36,37,38,39,40,41,42,43,52,70,73,74,75,76,77,78,79,80,87,93,103,104,105,109,113,121,122,123,130,131`; `src/sofia/machine/refresh.py:138`; `src/sofia/ops/reconcile.py:255,273,291,308,328`; `src/sofia/ops/reconciliation_journal.py:190,192`; `src/sofia/ops/state_registry.py:63,89,90`; `src/sofia/personality/emotion.py:446,672,763`; `src/sofia/personality/observation_bridge.py:66,106`; `src/sofia/runtime/runtime.py:594`; `src/sofia/safe/approve_execution.py:65`; `src/sofia/safe/capability_policy_cli.py:39,43`; `src/sofia/safe/dev_approve.py:88`; `src/sofia/state/json_repository.py:25,85,92,94,98,218,219,223`; `src/sofia/state/migration_lease.py:109,110,132,142,144,145,172,194,195,207,208`; `src/sofia/state/sqlite_plane.py:139,147,166,181,182,183,184,185,194,208,209,210,211,212,223`; `src/sofia/system/knowledge.py:184,197,200,202,220`; `src/sofia/system/machine_knowledge.py:125`; `src/sofia/ui/runtime_authority.py:61,64,66`; `src/sofia/ui/tray_agent.py:191,463`; `src/sofia/cognition/matrix/evidence.py:206,208,214,218`; `src/sofia/cognition/matrix/model.py:254,255,256`; `src/sofia/cognition/matrix/response.py:167,168,169`; `test/test_application_fleet_runtime.py:122,135,136`; `test/test_avatar_wardrobe_catalog.py:78,79,82,83,87`; `test/test_cognition_matrix.py:362,387,401,545,925,970,995`; `test/test_conversation_provider_live_regressions.py:388`; `test/test_conversation_service.py:856,857,858`; `test/test_current_emotional_state.py:12,94,113,118,348,439`; `test/test_discord_delivery.py:92,93,111,112`; `test/test_discord_durable_inbox.py:39,40,41,42,43,85,90,91,92,93`; `test/test_discord_recovery.py:63,68,69`; `test/test_distributed_identity.py:37,39,40,41,42,87,89,90`; `test/test_distributed_identity_bound_gateway.py:29`; `test/test_distributed_identity_durable.py:22,24,26,32,34,36,59,60,62`; `test/test_distributed_peer_knowledge.py:28,38,39,40,41,50,51,52,53,54,66,67,68,69,70,78,79,80,82,90,95,96,97,98,99,101,103,104,109,110,111,112,125,126,128,133,134,136`; `test/test_distributed_reachability.py:28,114,116,119`; `test/test_emotional_behavior_matrix.py:58,76,85,104,140,160,183,198,224,320,329`; `test/test_emotional_clarifications.py:20,33,34,50,67,68,70,72,75,105`; `test/test_emotional_conversation_integration.py:99`; `test/test_emotional_journal.py:18,19,32,34,39,73,85,87,89,91,96`; `test/test_environment_behavior_matrix.py:86`; `test/test_external_integration_verification.py:154`; `test/test_external_knowledge.py:100,109,123,140,154,171,188,220,233,269,275,276,277,289,333,352,372,394`; `test/test_filesystem_observation.py:62`; `test/test_habit_contextual_matrix.py:22`; `test/test_habit_foundation.py:39,67,81`; `test/test_idle_reflection_worker.py:19,178,195`; `test/test_interaction_extended_emotions.py:16,36`; `test/test_machine_inventory_contract.py:214,226,233,246,252,273,274,287`; `test/test_machine_inventory_lifecycle.py:150,178,215,222,236,281,296,304,328,332,359,392,423,427,465,474,527,564,585`; `test/test_machine_inventory_persistence.py:114,137,138,181,182,214,260,261,287,319,340,354,401`; `test/test_machine_location.py:32,37,40,46,51,61,63,92`; `test/test_machine_location_cli.py:63,66,67,68`; `test/test_machine_location_inventory.py:59`; `test/test_ops_activity.py:34,56,58`; `test/test_ops_activity_capability.py:104`; `test/test_personality_journal_thread_safety.py:53,64`; `test/test_reflection_conversation_integration.py:28`; `test/test_system_capability_assembler_integration.py:60,95,123,136,171,207`; `test/test_system_capability_context_integration.py:48,112,127,151,152,162,176`; `test/test_system_capability_integration.py:55,82,93,98,100,121,125,139,152,192,203,222,237,273,304,318,319,362,371,390,399,420,429,463,477,491,511,524,529,530,531,537,546,551,552,553,554`; `test/test_system_capability_integration_hardening.py:127,148,160,161,167,168,179,187,195,200,201,202,203,211,219,228,233,234,235,236,250,255,264,269,270,271,283,291,330,338,346,385,398,403,404,417,446,458,463,464,465,466,469,477,485,493,498,499,500,578,598,621,629,637,645,656,657,670`; `test/test_system_machine_knowledge_integration.py:115,148,160,174,184,189,190,191,198,213,223,228,229,230,237,246,267,276,284,292,303,304,314,323,331,339,344,346,355,364,410,426,436,446`; `test/test_thought_agent.py:19`; `test/test_thought_agent_conversation.py:20`; `test/test_thought_agent_live_ollama.py:33`; `test/test_thought_urgency_evidence.py:18`; `test/test_waves3_5_cross_package_acceptance.py:70,71`; `test/interaction_lab_support.py:157`.
- `ClarificationJournal.recent` (line 108): `src/sofia/application/background.py:290`; `src/sofia/application/emotional_conversation.py:344`; `src/sofia/application/idle_reflection.py:134`; `src/sofia/avatar/wardrobe_planner.py:389,433,438`; `src/sofia/personality/emotion.py:892,1072`; `src/sofia/personality/reflection_query.py:101,108,132,143`; `src/sofia/cognition/matrix/expression_plan.py:289,295,305,306,416,457,494,504`; `src/sofia/verify/interaction/live_behavior_probe.py:287`; `test/test_affection_cue_phrasings.py:21,34`; `test/test_current_emotional_state.py:41,57,66,148,169,192,292,317,341,376,398,419,431`; `test/test_distributed_peer_knowledge.py:97,98,99,104`; `test/test_emotional_behavior_matrix.py:135,240`; `test/test_emotional_clarifications.py:35,39,55,99,100`; `test/test_emotional_conversation_integration.py:39,41,48,78`; `test/test_emotional_conversation_string_path_regression.py:39`; `test/test_emotional_journal.py:21,22,45,57,67,68,77`; `test/test_interaction_extended_emotions.py:15,26`; `test/test_observation_bridge.py:50,66,82,93,125,142`; `test/test_observation_bridge_self_noise.py:38,57,78`; `test/test_personality_journal_thread_safety.py:72`; `test/test_thought_agent.py:22`; `test/test_thought_agent_conversation.py:52`; `test/test_thought_agent_live_ollama.py:41`; `test/test_thought_urgency_evidence.py:21`.
- `ClarificationJournal.prompt_context` (line 133): `src/sofia/application/emotional_conversation.py:558,573,583`; `test/test_emotional_clarifications.py:44,45,59`; `test/test_emotional_journal.py:49,76,99`; `test/test_reflection_journal.py:44`.

### `src/sofia/personality/communication_style.py`

Production/test importers: none in direct absolute imports.

Imports:

None.

Definitions:


### `src/sofia/personality/emotion.py`

Production/test importers: `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`, `src/sofia/personality/observation_bridge.py`, `src/sofia/personality/thought_agent.py`, `src/sofia/ui/theme.py`, `test/test_affection_cue_phrasings.py`, `test/test_avatar_behavior_matrix.py`, `test/test_current_emotional_state.py`, `test/test_emotional_behavior_matrix.py`, `test/test_emotional_clarifications.py`, `test/test_emotional_conversation_integration.py`, `test/test_emotional_conversation_string_path_regression.py`, `test/test_emotional_journal.py`, `test/test_environment_behavior_matrix.py`, `test/test_idle_reflection_worker.py`, `test/test_interaction_extended_emotions.py`, `test/test_observation_bridge.py`, `test/test_observation_bridge_self_noise.py`, `test/test_personality_journal_thread_safety.py`, `test/test_reflection_conversation_integration.py`, `test/test_thought_agent.py`, `test/test_thought_agent_conversation.py`, `test/test_thought_agent_live_ollama.py`, `test/test_thought_urgency_evidence.py`, `test/test_ui_theme.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import contextmanager`
- `from dataclasses import dataclass`
- `from datetime import datetime, timedelta, timezone`
- `import json`
- `from pathlib import Path`
- `import re`
- `import sqlite3`
- `from uuid import uuid4`
- `from sofia.social.model import AudienceKind, ScopeKind, SocialScope`
- `from sofia.social.principals import SPARKS_PRINCIPAL_ID`

Definitions:

- `_aware_utc` (line 110): `src/sofia/memory/chatgpt_export.py:227,237,238`.
- `_emotions` (line 116): no external lexical candidates.
- `_subject` (line 126): `src/sofia/environment/settings_cli.py:106`.
- `_social_scope` (line 135): no external lexical candidates.
- `_identifier` (line 151): `src/sofia/avatar/wardrobe.py:112,129,160`; `src/sofia/distributed/authorization.py:28,29`; `src/sofia/distributed/capabilities.py:37,41`; `src/sofia/distributed/operations.py:45,46,51`; `src/sofia/evolve/amendment.py:63,75`; `src/sofia/integrations/jmri.py:22,25,29`; `src/sofia/integrations/local_maintenance.py:52,67,106`; `src/sofia/personality/clarification.py:84,85`; `src/sofia/ui/drafts.py:35,36,93,94,126,127,152,153`.
- `_intensity_word` (line 158): no external lexical candidates.
- `EmotionalEvent` (line 169): `src/sofia/personality/thought_agent.py:54,58`.
  Data declarations: `event_id: str`; `occurred_at: datetime`; `source: str`; `evidence_ref: str`; `description: str`; `original_emotions: tuple[str, ...]`; `current_emotions: tuple[str, ...]`; `revision_count: int`; `subject: str | None = None`; `scope_kind: str = ScopeKind.GLOBAL.value`; `principal_id: str | None = None`; `audience_id: str | None = None`; `audience_kind: str | None = None`.
- `EmotionalEvent.scope` (line 185): `src/sofia/application/act_service.py:126,128,137,143`; `src/sofia/application/emotional_conversation.py:389,408,450,454,524,561,581,584`; `src/sofia/application/idle_reflection.py:111,114,138`; `src/sofia/authorization/evaluator.py:63,68`; `src/sofia/authorization/model.py:52,85`; `src/sofia/composition/authorization.py:148,174`; `src/sofia/config/model.py:257,258`; `src/sofia/dev/git_workspace.py:21,22`; `src/sofia/evolve/revision.py:63,75,101,199,345,353,368,374,378,400,413,453,459,464`; `src/sofia/evolve/state_plane_adapter.py:28,30,36,41,46,49,60,65,84,85,98,145,156`; `src/sofia/memory/chatgpt_export.py:311,313,315,316`; `src/sofia/personality/reflection.py:293,342,369,614,644,697`; `src/sofia/personality/thought_agent.py:79,177`; `src/sofia/runtime/runtime.py:692`; `src/sofia/state/sqlite_plane.py:147,157,180,213`; `src/sofia/verify/interaction/avatar_world_probe.py:117,121`; `test/test_authorization.py:44`; `test/test_authorization_evaluator.py:37`; `test/test_evolve_revision.py:29,32,38,44,48,51,74,77,152`; `test/test_interaction_temporal.py:38,39,47,49,51`; `test/test_reflection_conversation_integration.py:27,33,41,44`; `test/test_thought_agent_conversation.py:19,23`.
- `ActiveEmotion` (line 202): `test/test_avatar_behavior_matrix.py:30`; `test/test_ui_theme.py:99`.
  Data declarations: `name: str`; `intensity: float`; `evidence_refs: tuple[str, ...]`; `event_ids: tuple[str, ...]`.
- `ReturnExpectation` (line 210): `test/test_emotional_behavior_matrix.py:300`.
  Data declarations: `subject: str`; `source_ref: str`; `recorded_at: datetime`; `expected_return_at: datetime`.
- `ReunionAppraisal` (line 218): no external lexical candidates.
  Data declarations: `gap: timedelta`; `expected_return_at: datetime | None`; `lateness: timedelta | None`; `emotions: tuple[str, ...]`; `expectation_source_ref: str | None`.
- `CurrentEmotionalState` (line 227): `src/sofia/application/emotional_conversation.py:229`; `src/sofia/personality/influence.py:56,59`; `src/sofia/ui/theme.py:155,167`; `test/test_avatar_behavior_matrix.py:37`; `test/test_ui_theme.py:94`.
  Data declarations: `as_of: datetime`; `subject: str | None`; `tone: str`; `active: tuple[ActiveEmotion, ...]`.
- `CurrentEmotionalState.primary` (line 234): `src/sofia/application/emotional_conversation.py:531`; `src/sofia/avatar/wardrobe_catalog.py:430,442,449,466,473`; `src/sofia/cognition/model_lifecycle.py:114,130`; `src/sofia/cognition/routing.py:70,75`; `src/sofia/composition/root.py:401`; `src/sofia/composition/engines.py:122`; `src/sofia/config/cognitive_models.py:14,27,34,47,48`; `src/sofia/config/defaults.py:192,216`; `src/sofia/config/model.py:94,113`; `src/sofia/operational/status_queries.py:134,136,137`; `src/sofia/personality/influence.py:100,144,147,148`; `src/sofia/runtime/runtime.py:469`; `src/sofia/ui/desktop.py:160,337,401,451,728,743,762,780`; `src/sofia/ui/theme.py:111,190,224,225,229,230,281,304,308,312,353,356,364,368,381,384,392`; `src/sofia/ui/tray_agent.py:286,364,498,519`; `src/sofia/verify/dual_cognition.py:228`; `src/sofia/cognition/matrix/expression_plan.py:313,323,329,348,355,460,461,492,494,500`; `test/test_cognitive_activity.py:81,95,114`; `test/test_cognitive_operation_system.py:187,191`; `test/test_cognitive_routing.py:69,75,78,86,91,94,110,120,123,130,135,138,154,156,163,167,172,182,187,195,205,210,233,236,246,256,264,272,276,277,281,284,295,343,345,346,405,431,438,446,451,453,472,478,479,485,489,494,513,604,606,711,713,725,738,740,748,753,758,766,791,795,807`; `test/test_conversation_provider_live_regressions.py:416,565`; `test/test_conversation_service.py:190,210`; `test/test_default_runtime_provider_boundary.py:54`; `test/test_embodied_expression_plan.py:59,87,102,115,159,180`; `test/test_environment_behavior_matrix.py:140`; `test/test_environment_nws.py:25,41`; `test/test_model_configuration_independence.py:84`; `test/test_model_lifecycle.py:67,319,331`; `test/test_production_dual_cognition.py:43,46,48,51,53,66,68`; `test/test_runtime_user_settings_defaults.py:161,163,165,190,191,257,261`; `test/test_ui_desktop_application.py:118`; `test/test_ui_theme.py:142,173,203`; `test/test_ui_tray_models.py:17,24,25,26`; `test/test_verify_dual_cognition.py:35,39,47,51,53,70,74,79,84,88,89`.
- `EmotionalJournal` (line 238): `src/sofia/application/emotional_conversation.py:97,125,143`; `src/sofia/personality/observation_bridge.py:20,30,81,99,121,134`; `test/test_affection_cue_phrasings.py:18,32`; `test/test_current_emotional_state.py:11,28,50,61,80,93,112,137,155,177,201,221,235,246,257,268,279,298,323,347,367,386,407,428,438,455,473,508`; `test/test_emotional_behavior_matrix.py:57,75,103,139,159,182,223,289,306,319`; `test/test_emotional_clarifications.py:19,35`; `test/test_emotional_conversation_integration.py:28,67,93,143`; `test/test_emotional_conversation_string_path_regression.py:36`; `test/test_emotional_journal.py:14,20,29,38,45,53,61,72,81,95`; `test/test_environment_behavior_matrix.py:85,217`; `test/test_idle_reflection_worker.py:17,100,123,151,176`; `test/test_interaction_extended_emotions.py:13,33`; `test/test_observation_bridge.py:38,50,82`; `test/test_observation_bridge_self_noise.py:31,45`; `test/test_personality_journal_thread_safety.py:52`; `test/test_reflection_conversation_integration.py:25,54`; `test/test_thought_agent.py:18`; `test/test_thought_agent_conversation.py:17`; `test/test_thought_agent_live_ollama.py:30`; `test/test_thought_urgency_evidence.py:17`.
- `EmotionalJournal.__init__` (line 241): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `EmotionalJournal._connect` (line 352): `src/sofia/act/delivery.py:130,225,264,394,425,541,591`; `src/sofia/act/system_notice.py:45,172,311,377`; `src/sofia/application/background.py:44,73,148`; `src/sofia/application/idle_reflection.py:42,61,86`; `src/sofia/cognition/activity.py:60,106,169,178`; `src/sofia/config/user_settings.py:322,397,427`; `src/sofia/discord/binding.py:70,128,198,243,316,405,497`; `src/sofia/discord/delivery.py:106,153,240,280,320,354,409,425,437`; `src/sofia/discord/store.py:81,181,242,289,369,458,496,545,604,627,639`; `src/sofia/distributed/durable.py:50,180`; `src/sofia/distributed/inference_control.py:85,115,143,160`; `src/sofia/evolve/executor.py:114,318,381,472`; `src/sofia/evolve/revision.py:234,319,387,467`; `src/sofia/interaction/ledger.py:67,95,110,143,177`; `src/sofia/interaction/world.py:84,117,122,131,137,153`; `src/sofia/memory/chatgpt_export_store.py:61,163,291,325,415,442`; `src/sofia/memory/chatgpt_migration.py:36,114,174,200`; `src/sofia/operational/store.py:41,66,148,195`; `src/sofia/ops/activity.py:73,114,130,160`; `src/sofia/personality/clarification.py:47,91,112`; `src/sofia/personality/reflection.py:313,343,370,467,488,514,573,617,630,645,661`; `src/sofia/run/heartbeat.py:49,83,127`; `src/sofia/run/lease.py:60,135,257,323,379,404`; `src/sofia/run/periodic.py:78,130,188,216`; `src/sofia/run/supervisor.py:130,301,321,563`; `src/sofia/safe/audit.py:24,104,198`; `src/sofia/safe/dev_approval.py:24,49,109`; `src/sofia/social/store.py:24,49,108`; `src/sofia/state/component_schema.py:36,73,127,170`; `src/sofia/state/sqlite_plane.py:36,82,120,148,238,269`; `src/sofia/ui/control_center.py:133,157,206`; `src/sofia/ui/remote_transport.py:140,165,190,204`; `src/sofia/verify/semantic_integrity.py:82,429`; `src/sofia/cognition/matrix/trace.py:56,477,527,538,568,596`; `test/test_interaction_i5_i7_batch.py:95`; `test/test_runtime_user_settings.py:189,252,261`.
- `EmotionalJournal.record` (line 364): `src/sofia/application/background_runtime.py:173,174`; `src/sofia/application/conversation_matrix.py:511,551`; `src/sofia/application/emotional_conversation.py:313,397`; `src/sofia/application/fleet_runtime.py:255,258,259,260,261,266,270,272,273`; `src/sofia/avatar/wardrobe_planner.py:433`; `src/sofia/cognition/assembler.py:615,618`; `src/sofia/cognition/context_evidence.py:15,16,19,22,25,27,30,32,35,39`; `src/sofia/composition/root.py:78,91,95,96,98,99,100`; `src/sofia/config/reviewed_projection.py:169,172,176`; `src/sofia/config/state_store.py:55,81,94,104,105,106`; `src/sofia/dev/capability.py:49,103,109,111,120,121,125`; `src/sofia/dev/release_store.py:57,63,65,160,166,168`; `src/sofia/discord/delivery.py:501,505,506,509,510,520,521,527,531,532,538,539,546,547`; `src/sofia/distributed/knowledge.py:53`; `src/sofia/evolve/state_plane_adapter.py:49,50,52`; `src/sofia/external/knowledge.py:181,188,189,192,194,234,255,303,308,310`; `src/sofia/filesystem/change_capability.py:25`; `src/sofia/habits/continuity.py:82`; `src/sofia/interaction/temporal.py:140,144,148,149,177,181,186`; `src/sofia/machine/inventory.py:75,90`; `src/sofia/machine/location.py:168,182,186,205,206,207,214,218,233,234,235,236,237,238,239,240,242`; `src/sofia/machine/location_cli.py:104,112,115,117,118,200,202,203`; `src/sofia/machine/location_state.py:36,37,38,39,40,41,42,43,52,70,73,74,75,76,77,78,79,80,87,93,103,104,105,109,113,121,122,123,130,131`; `src/sofia/machine/refresh.py:138`; `src/sofia/ops/reconcile.py:255,273,291,308,328`; `src/sofia/ops/reconciliation_journal.py:190,192`; `src/sofia/ops/state_registry.py:63,89,90`; `src/sofia/personality/observation_bridge.py:66,106`; `src/sofia/runtime/runtime.py:594`; `src/sofia/safe/approve_execution.py:65`; `src/sofia/safe/capability_policy_cli.py:39,43`; `src/sofia/safe/dev_approve.py:88`; `src/sofia/state/json_repository.py:25,85,92,94,98,218,219,223`; `src/sofia/state/migration_lease.py:109,110,132,142,144,145,172,194,195,207,208`; `src/sofia/state/sqlite_plane.py:139,147,166,181,182,183,184,185,194,208,209,210,211,212,223`; `src/sofia/system/knowledge.py:184,197,200,202,220`; `src/sofia/system/machine_knowledge.py:125`; `src/sofia/ui/runtime_authority.py:61,64,66`; `src/sofia/ui/tray_agent.py:191,463`; `src/sofia/cognition/matrix/evidence.py:206,208,214,218`; `src/sofia/cognition/matrix/model.py:254,255,256`; `src/sofia/cognition/matrix/response.py:167,168,169`; `test/test_application_fleet_runtime.py:122,135,136`; `test/test_avatar_wardrobe_catalog.py:78,79,82,83,87`; `test/test_cognition_matrix.py:362,387,401,545,925,970,995`; `test/test_conversation_provider_live_regressions.py:388`; `test/test_conversation_service.py:856,857,858`; `test/test_current_emotional_state.py:12,94,113,118,348,439`; `test/test_discord_delivery.py:92,93,111,112`; `test/test_discord_durable_inbox.py:39,40,41,42,43,85,90,91,92,93`; `test/test_discord_recovery.py:63,68,69`; `test/test_distributed_identity.py:37,39,40,41,42,87,89,90`; `test/test_distributed_identity_bound_gateway.py:29`; `test/test_distributed_identity_durable.py:22,24,26,32,34,36,59,60,62`; `test/test_distributed_peer_knowledge.py:28,38,39,40,41,50,51,52,53,54,66,67,68,69,70,78,79,80,82,90,95,96,97,98,99,101,103,104,109,110,111,112,125,126,128,133,134,136`; `test/test_distributed_reachability.py:28,114,116,119`; `test/test_emotional_behavior_matrix.py:58,76,85,104,140,160,183,198,224,320,329`; `test/test_emotional_clarifications.py:20,33,34,50,67,68,70,72,75,105`; `test/test_emotional_conversation_integration.py:99`; `test/test_emotional_journal.py:18,19,32,34,39,73,85,87,89,91,96`; `test/test_environment_behavior_matrix.py:86`; `test/test_external_integration_verification.py:154`; `test/test_external_knowledge.py:100,109,123,140,154,171,188,220,233,269,275,276,277,289,333,352,372,394`; `test/test_filesystem_observation.py:62`; `test/test_habit_contextual_matrix.py:22`; `test/test_habit_foundation.py:39,67,81`; `test/test_idle_reflection_worker.py:19,178,195`; `test/test_interaction_extended_emotions.py:16,36`; `test/test_machine_inventory_contract.py:214,226,233,246,252,273,274,287`; `test/test_machine_inventory_lifecycle.py:150,178,215,222,236,281,296,304,328,332,359,392,423,427,465,474,527,564,585`; `test/test_machine_inventory_persistence.py:114,137,138,181,182,214,260,261,287,319,340,354,401`; `test/test_machine_location.py:32,37,40,46,51,61,63,92`; `test/test_machine_location_cli.py:63,66,67,68`; `test/test_machine_location_inventory.py:59`; `test/test_ops_activity.py:34,56,58`; `test/test_ops_activity_capability.py:104`; `test/test_personality_journal_thread_safety.py:53,64`; `test/test_reflection_conversation_integration.py:28`; `test/test_system_capability_assembler_integration.py:60,95,123,136,171,207`; `test/test_system_capability_context_integration.py:48,112,127,151,152,162,176`; `test/test_system_capability_integration.py:55,82,93,98,100,121,125,139,152,192,203,222,237,273,304,318,319,362,371,390,399,420,429,463,477,491,511,524,529,530,531,537,546,551,552,553,554`; `test/test_system_capability_integration_hardening.py:127,148,160,161,167,168,179,187,195,200,201,202,203,211,219,228,233,234,235,236,250,255,264,269,270,271,283,291,330,338,346,385,398,403,404,417,446,458,463,464,465,466,469,477,485,493,498,499,500,578,598,621,629,637,645,656,657,670`; `test/test_system_machine_knowledge_integration.py:115,148,160,174,184,189,190,191,198,213,223,228,229,230,237,246,267,276,284,292,303,304,314,323,331,339,344,346,355,364,410,426,436,446`; `test/test_thought_agent.py:19`; `test/test_thought_agent_conversation.py:20`; `test/test_thought_agent_live_ollama.py:33`; `test/test_thought_urgency_evidence.py:18`; `test/test_waves3_5_cross_package_acceptance.py:70,71`; `test/interaction_lab_support.py:157`.
- `EmotionalJournal.record_user_cue` (line 422): `src/sofia/application/emotional_conversation.py:431`; `test/test_affection_cue_phrasings.py:19,20,33`; `test/test_current_emotional_state.py:62,69,73`; `test/test_emotional_journal.py:62,63,64,65,66`.
- `EmotionalJournal.record_return_expectation` (line 453): `test/test_current_emotional_state.py:157,179,300,325,388`.
- `EmotionalJournal.record_return_expectation_from_user_cue` (line 494): `src/sofia/application/emotional_conversation.py:436`; `test/test_current_emotional_state.py:203,228,236,247,258,269,281`.
- `EmotionalJournal.appraise_reunion` (line 541): `test/test_emotional_behavior_matrix.py:289,306`.
- `EmotionalJournal.observe_absence` (line 585): `src/sofia/application/emotional_conversation.py:221`; `test/test_current_emotional_state.py:371,372,394,411,412,430`.
- `EmotionalJournal.observe_contact` (line 686): `src/sofia/application/emotional_conversation.py:440`; `test/test_current_emotional_state.py:29,33,37,51,54,138,143,161,165,184,188,210,213,285,288,305,308,313,330,333,337,369,392,409,448,474,479,484`; `test/test_emotional_conversation_integration.py:71`.
- `EmotionalJournal.revise` (line 769): `src/sofia/personality/observation_bridge.py:136`; `test/test_emotional_behavior_matrix.py:233`; `test/test_emotional_clarifications.py:52`; `test/test_emotional_journal.py:42,55`; `test/test_interaction_extended_emotions.py:21`.
- `EmotionalJournal.recent` (line 788): `src/sofia/application/background.py:290`; `src/sofia/application/emotional_conversation.py:344`; `src/sofia/application/idle_reflection.py:134`; `src/sofia/avatar/wardrobe_planner.py:389,433,438`; `src/sofia/personality/clarification.py:134`; `src/sofia/personality/reflection_query.py:101,108,132,143`; `src/sofia/cognition/matrix/expression_plan.py:289,295,305,306,416,457,494,504`; `src/sofia/verify/interaction/live_behavior_probe.py:287`; `test/test_affection_cue_phrasings.py:21,34`; `test/test_current_emotional_state.py:41,57,66,148,169,192,292,317,341,376,398,419,431`; `test/test_distributed_peer_knowledge.py:97,98,99,104`; `test/test_emotional_behavior_matrix.py:135,240`; `test/test_emotional_clarifications.py:35,39,55,99,100`; `test/test_emotional_conversation_integration.py:39,41,48,78`; `test/test_emotional_conversation_string_path_regression.py:39`; `test/test_emotional_journal.py:21,22,45,57,67,68,77`; `test/test_interaction_extended_emotions.py:15,26`; `test/test_observation_bridge.py:50,66,82,93,125,142`; `test/test_observation_bridge_self_noise.py:38,57,78`; `test/test_personality_journal_thread_safety.py:72`; `test/test_thought_agent.py:22`; `test/test_thought_agent_conversation.py:52`; `test/test_thought_agent_live_ollama.py:41`; `test/test_thought_urgency_evidence.py:21`.
- `EmotionalJournal.current_state` (line 883): `src/sofia/application/emotional_conversation.py:234,358,377,451,478`; `test/test_current_emotional_state.py:19,102,124,125,133,456,490`; `test/test_emotional_behavior_matrix.py:68,97,113,133,149,169,194,209,250,339`; `test/test_environment_behavior_matrix.py:95,131`; `test/test_thought_agent_conversation.py:90,99`.
- `EmotionalJournal.current_state_prompt` (line 960): `src/sofia/application/emotional_conversation.py:521`; `test/test_current_emotional_state.py:81,104,357,510`; `test/test_emotional_behavior_matrix.py:171`.
- `EmotionalJournal.prompt_context` (line 1051): `src/sofia/application/emotional_conversation.py:558,573,583`; `test/test_emotional_clarifications.py:44,45,59`; `test/test_emotional_journal.py:49,76,99`; `test/test_reflection_journal.py:44`.

Module declarations: `EMOTIONS = frozenset({'affection', 'amusement', 'anticipation', 'appreciation', 'bashfulness', 'caution', 'concern', 'contentment', 'curiosity', 'determination', 'disappointment', 'excitement', 'fondness', 'frustration', 'gratitude', 'hope', 'joy', 'longing', 'playfulness', 'reflection', 'relief', 'romance', 'sadness', 'sensuality', 'surprise', 'uncertainty', 'warmth', 'anger', 'fear', 'jealousy', 'embarrassment', 'humiliation', 'sexual-arousal', 'aversion', 'disgust', 'nervousness', 'shame', 'pride', 'tenderness', 'affectionate-uncertainty', 'sexual-attraction', 'sexual-desire'})`; `SOURCES = frozenset({'observed', 'user_reported', 'inferred'})`; `_CUE = re.compile('\\b(?:good girl|head pats?|pat pat|pats? (?:your |her |the )?head)\\b', re.IGNORECASE)`; `_MISSED_CUE = re.compile("\\b(?:i(?:'|’)?ve\\s+missed\\s+you|i\\s+missed\\s+you|missed\\s+you)\\b", re.IGNORECASE)`; `_NEGATED_CUE = re.compile("\\b(?:don't|do not|didn't|did not|haven't|have not|never|not)\\b", re.IGNORECASE)`; `_RETURN_IN_CUE = re.compile("^\\s*(?:i(?:'|’)?ll|i\\s+will|i(?:'|’)?m\\s+going\\s+to|i\\s+am\\s+going\\s+to)\\s+be\\s+(?:back\\s+in|gone\\s+for)\\s+(?P<count>\\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\\s*(?P<unit>minutes?|hours?|days?|weeks?)\\s*[.!]?\\s*$", re.IGNORECASE)`; `_RETURN_COUNT_WORDS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}`; `_RETURN_COARSE_CUE = re.compile("^\\s*(?:i(?:'|’)?ll|i\\s+will|i(?:'|’)?m\\s+going\\s+to|i\\s+am\\s+going\\s+to)\\s+be\\s+back\\s+(?P<when>tonight|later\\s+today|tomorrow)\\s*[.!]?\\s*$", re.IGNORECASE)`; `_RETURN_COARSE_DELTAS = {'tonight': timedelta(hours=24), 'later today': timedelta(hours=24), 'tomorrow': timedelta(hours=48)}`; `_POSITIVE = frozenset({'affection', 'amusement', 'anticipation', 'appreciation', 'contentment', 'excitement', 'fondness', 'gratitude', 'hope', 'joy', 'playfulness', 'relief', 'romance', 'tenderness', 'warmth', 'pride', 'sexual-attraction', 'sexual-desire'})`; `_NEGATIVE = frozenset({'anger', 'aversion', 'concern', 'disappointment', 'disgust', 'fear', 'frustration', 'humiliation', 'jealousy', 'nervousness', 'sadness', 'shame'})`; `_BACKGROUND_RELATIONAL = frozenset({'affection', 'fondness', 'warmth', 'tenderness', 'romance'})`; `_SOURCE_WEIGHT = {'observed': 0.6, 'user_reported': 0.55, 'inferred': 0.48}`; `_HALF_LIFE_HOURS = {'surprise': 0.5, 'bashfulness': 1.5, 'embarrassment': 1.5, 'amusement': 2.0, 'playfulness': 2.5, 'sexual-arousal': 2.0, 'excitement': 3.0, 'relief': 3.0, 'anger': 4.0, 'frustration': 4.0, 'disgust': 4.0, 'aversion': 4.0, 'joy': 5.0, 'caution': 6.0, 'concern': 6.0, 'anticipation': 6.0, 'uncertainty': 6.0, 'sadness': 8.0, 'fear': 8.0, 'curiosity': 8.0, 'determination': 10.0, 'contentment': 12.0, 'longing': 12.0, 'gratitude': 24.0, 'appreciation': 24.0, 'affection': 48.0, 'fondness': 48.0, 'warmth': 48.0, 'tenderness': 48.0, 'romance': 48.0, 'hope': 24.0, 'pride': 24.0, 'jealousy': 8.0, 'humiliation': 8.0, 'shame': 8.0, 'reflection': 12.0, 'sensuality': 4.0, 'affectionate-uncertainty': 8.0, 'sexual-attraction': 24.0, 'sexual-desire': 4.0}`; `_REUNION_MIN_GAP = timedelta(hours=6)`; `_LONGING_GAP = timedelta(hours=18)`; `_SAD_ABSENCE_GAP = timedelta(days=3)`; `_LONG_ABSENCE_GAP = timedelta(days=7)`; `_EXPECTATION_FRUSTRATION_LATE = timedelta(hours=24)`; `_EXPECTATION_ANGER_LATE = timedelta(days=3)`; `_MAX_RETURN_EXPECTATION = timedelta(days=90)`; `_ACTIVE_THRESHOLD = 0.08`; `_LEGACY_AUTO_AFFECTION_DESCRIPTION = 'User initiated an affectionate or playful conversational cue.'`.

### `src/sofia/personality/evaluation.py`

Production/test importers: `src/sofia/personality/review.py`, `test/test_personality_evaluation.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from hashlib import sha256`
- `from time import perf_counter`
- `from sofia.cognition.assembler import CognitiveContextAssembler`
- `from sofia.cognition.context import CognitiveContext`
- `from sofia.cognition.engine import CognitiveEngine`
- `from sofia.cognition.model import CognitiveResponse, CognitiveRole`

Definitions:

- `PersonalityScenario` (line 19): `test/test_personality_evaluation.py:29,57,61,103`.
  Data declarations: `label: str`; `context: CognitiveContext`.
- `PersonalityScenario.__post_init__` (line 23): no external lexical candidates.
- `PersonalityObservation` (line 37): `src/sofia/personality/review.py:18,23`.
  Data declarations: `label: str`; `request_sha256: str`; `response: str | None`; `elapsed_seconds: float`; `error_type: str | None`; `error_message: str | None`.
- `observe_full_context` (line 46): `test/test_personality_evaluation.py:37,49,51,68,77,102`.

### `src/sofia/personality/expression.py`

Production/test importers: `src/sofia/cognition/assembler.py`, `test/test_emotional_journal.py`, `test/test_interaction_avatar_world.py`, `test/test_personality_emotional_gestures.py`, `test/test_personality_expression_boundary.py`, `test/test_personality_expression_g9.py`.

Imports:

- `from __future__ import annotations`
- `from sofia.interaction.avatar_world import avatar_world_guidance`

Definitions:

- `personality_expression_guidance` (line 5): `src/sofia/cognition/assembler.py:287`; `test/test_emotional_journal.py:108`; `test/test_interaction_avatar_world.py:44`; `test/test_personality_emotional_gestures.py:6,17,25,49`; `test/test_personality_expression_boundary.py:42`; `test/test_personality_expression_g9.py:6,13,22`.

### `src/sofia/personality/influence.py`

Production/test importers: `src/sofia/application/act_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/bootstrap.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/avatar/wardrobe_autonomy.py`, `src/sofia/avatar/wardrobe_planner.py`, `src/sofia/cognition/matrix/expression_plan.py`, `src/sofia/cognition/matrix/influence.py`, `src/sofia/memory/promoted_retrieval.py`, `src/sofia/memory/system.py`, `src/sofia/personality/thought_agent.py`, `src/sofia/runtime/response.py`, `src/sofia/runtime/runtime.py`, `src/sofia/voice/prosody_matrix.py`, `test/test_avatar_behavior_matrix.py`, `test/test_avatar_clothing_action.py`, `test/test_contextual_influence_matrix.py`, `test/test_embodied_expression_plan.py`, `test/test_emotional_behavior_matrix.py`, `test/test_environment_acceptance.py`, `test/test_environment_behavior_matrix.py`, `test/test_memory_promoted_retrieval.py`, `test/test_memory_runtime_wiring.py`, `test/test_thought_agent.py`, `test/test_voice_prosody_matrix.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime`
- `from typing import Iterable`
- `from sofia.environment.model import EnvironmentFreshness, EnvironmentSnapshot`
- `from sofia.personality.emotion import CurrentEmotionalState`

Definitions:

- `daypart` (line 16): `src/sofia/habits/continuity.py:149,150,157,178,179,210,212,214,327,328,332`; `src/sofia/memory/promoted_retrieval.py:66`; `src/sofia/personality/thought_agent.py:97`; `src/sofia/voice/prosody_matrix.py:33,34,35,36`; `src/sofia/cognition/matrix/expression_plan.py:436,473`; `src/sofia/cognition/matrix/influence.py:346`; `test/test_embodied_expression_plan.py:17,37`; `test/test_emotional_behavior_matrix.py:122,152`; `test/test_environment_acceptance.py:65`; `test/test_environment_behavior_matrix.py:121,260`.
- `ContinuityInfluence` (line 30): `src/sofia/application/act_service.py:121`; `src/sofia/application/background_runtime.py:78`; `src/sofia/application/bootstrap.py:364,473,538`; `src/sofia/application/emotional_conversation.py:376,477`; `src/sofia/avatar/wardrobe_autonomy.py:46,51`; `src/sofia/avatar/wardrobe_planner.py:458,461`; `src/sofia/memory/promoted_retrieval.py:30,39,86`; `src/sofia/memory/system.py:101,127,197`; `src/sofia/personality/thought_agent.py:56,64`; `src/sofia/runtime/runtime.py:642`; `src/sofia/runtime/response.py:29,55`; `src/sofia/voice/prosody_matrix.py:20,21`; `src/sofia/cognition/matrix/expression_plan.py:386,391,409`; `src/sofia/cognition/matrix/influence.py:239,243,267`; `test/test_avatar_behavior_matrix.py:43`; `test/test_avatar_clothing_action.py:79`; `test/test_contextual_influence_matrix.py:17,18`; `test/test_embodied_expression_plan.py:15,16`; `test/test_emotional_behavior_matrix.py:116,150,340`; `test/test_environment_acceptance.py:127`; `test/test_environment_behavior_matrix.py:116,157,315`; `test/test_memory_promoted_retrieval.py:57`; `test/test_memory_runtime_wiring.py:524,549`; `test/test_thought_agent.py:127,165`; `test/test_voice_prosody_matrix.py:27`.
  Data declarations: `daypart: str`; `season: str | None`; `daylight: str | None`; `weather_condition: str | None`; `temperature_c: float | None`; `weather_freshness: str | None`; `location_freshness: str | None`; `primary_emotion_evidence_refs: tuple[str, ...]`; `emotional_tone: str`; `primary_emotion: str | None`; `primary_intensity: float`; `active_emotions: tuple[str, ...]`; `foreground_emotion_evidence_refs: tuple[str, ...] = ()`; `foreground_emotion: str | None = None`; `foreground_intensity: float = 0.0`; `daypart_evidence_refs: tuple[str, ...] = ()`; `season_evidence_refs: tuple[str, ...] = ()`; `weather_evidence_refs: tuple[str, ...] = ()`.
- `ContinuityInfluence.from_state` (line 53): `src/sofia/application/background_runtime.py:78`; `src/sofia/application/bootstrap.py:364,473,538`; `src/sofia/application/emotional_conversation.py:376,477`; `test/test_avatar_behavior_matrix.py:43`; `test/test_emotional_behavior_matrix.py:116,150,340`; `test/test_environment_behavior_matrix.py:116,157,315`.
- `ContinuityInfluence.prompt` (line 164): `src/sofia/application/conversation_matrix.py:226`; `src/sofia/application/emotional_conversation.py:526,535`; `src/sofia/dev/opencode.py:12,15,56`; `src/sofia/ui/desktop.py:508,509`; `src/sofia/ui/quick_tools.py:16,22`; `src/sofia/verify/dual_cognition.py:83,92`; `test/test_current_emotional_state.py:81,83,84,85,86,87,88,89,104,107,108,357,359,360,361,362,510,512,513`; `test/test_embodied_expression_plan.py:118,132,133,134,135,136,137,138`; `test/test_emotional_behavior_matrix.py:120,128,129,130,131,171,174,175`; `test/test_environment_behavior_matrix.py:127,165,166`; `test/test_environment_prompt.py:44,45,46,47,48,49,50,55,56,57,58,88,89,90,91,107,108,109,110,111,127,128,129,130,131,132,136,137,138,139,140,173,175,176,177,198,200,201,202,203,204`; `test/test_interaction_chat_projection.py:69,70,71,72,73,74,75,76,77,158,159,160,161,162,263,264,265,266,285,290,291,292,293`; `test/test_interaction_consent_followup.py:69,72,73,74,75,76,77,78,79,80,81,106,107,108,109,110,111,112,144,145,146,148,150,151`; `test/test_interaction_contextual_all_regions.py:60,61,62,63,64,65`; `test/test_interaction_live_claims.py:77,78,79,80,81,82`; `test/test_interaction_live_discussion.py:30,32,33,34,35,36,37,38,48,49,50,51`; `test/test_interaction_live_phrase_coverage.py:42,43,44,45,46`; `test/test_interaction_live_stop_repetition.py:127,128,129`; `test/test_ui_quick_tools.py:25`; `test/test_voice_tts.py:139,140,141,144`.
- `outreach_salience` (line 205): `src/sofia/application/act_service.py:149`; `src/sofia/personality/thought_agent.py:187`.

Module declarations: `_BACKGROUND_RELATIONAL = frozenset({'affection', 'fondness', 'warmth', 'tenderness', 'romance'})`.

### `src/sofia/personality/model.py`

Production/test importers: `src/sofia/cognition/context.py`, `src/sofia/personality/probe.py`, `src/sofia/personality/store.py`, `src/sofia/personality/system.py`, `src/sofia/runtime/runtime.py`, `test/test_cognitive_assembler.py`, `test/test_cognitive_context.py`, `test/test_cognitive_context_assembler.py`, `test/test_conversation_workspace_projection.py`, `test/test_conversational_context_projection.py`, `test/test_personality.py`, `test/test_personality_embodiment_contract.py`, `test/test_personality_evaluation.py`, `test/test_personality_expression_boundary.py`, `test/test_personality_probe.py`, `test/test_personality_provider_path.py`, `test/test_personality_store.py`, `test/test_system_capability_integration_hardening.py`.

Imports:

- `from dataclasses import dataclass`

Definitions:

- `PersonalityProfile` (line 5): `src/sofia/cognition/context.py:49,94`; `src/sofia/personality/probe.py:55,66`; `src/sofia/personality/store.py:23,24,52,111`; `src/sofia/personality/system.py:7,11`; `src/sofia/runtime/runtime.py:220,270`; `test/test_cognitive_assembler.py:40,41`; `test/test_cognitive_context.py:97,98`; `test/test_cognitive_context_assembler.py:166`; `test/test_conversation_workspace_projection.py:58`; `test/test_conversational_context_projection.py:31`; `test/test_personality.py:7,15,28,38,48,61,73,88,100,123`; `test/test_personality_embodiment_contract.py:18`; `test/test_personality_evaluation.py:28,63`; `test/test_personality_expression_boundary.py:18,34,51,52`; `test/test_personality_probe.py:28,45,59,71,76,87`; `test/test_personality_provider_path.py:22,49`; `test/test_personality_store.py:12,13,75,96`.
  Data declarations: `name: str`; `traits: tuple[str, ...] = ()`; `communication_style: str = ''`; `embodiment_guidance: str = ''`.

### `src/sofia/personality/observation_bridge.py`

Production/test importers: `src/sofia/application/emotional_conversation.py`, `test/test_observation_bridge.py`, `test/test_observation_bridge_self_noise.py`.

Imports:

- `from __future__ import annotations`
- `from datetime import datetime`
- `from hashlib import sha256`
- `import json`
- `from pathlib import Path`
- `from sofia.filesystem.changes import FilesystemChangeEvent`
- `from sofia.personality.emotion import EmotionalJournal`
- `from sofia.personality.reflection import ReflectionJournal`

Definitions:

- `record_workspace_observation` (line 19): `src/sofia/application/emotional_conversation.py:130`; `test/test_observation_bridge.py:43,47,63`; `test/test_observation_bridge_self_noise.py:34,48,53`.
- `record_workspace_observation.relevant` (line 42): `src/sofia/filesystem/change_filter.py:34,35,36`; `src/sofia/habits/engine.py:307,337,339,342,343,372`; `test/test_memory_promoted_retrieval.py:111,123`.
- `record_verified_test_run` (line 79): `test/test_observation_bridge.py:72,89,101,103,105,107,109`.
- `record_user_reappraisal` (line 118): `test/test_observation_bridge.py:76`.

- Non-Python asset: `src/sofia/personality/personality.json`

### `src/sofia/personality/probe.py`

Production/test importers: `test/test_personality_probe.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from hashlib import sha256`
- `from time import perf_counter`
- `from sofia.cognition.assembler import CognitiveContextAssembler`
- `from sofia.cognition.context import CognitiveContext`
- `from sofia.cognition.engine import CognitiveEngine`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole`
- `from sofia.personality.model import PersonalityProfile`

Definitions:

- `PersonalityProbeCase` (line 27): `test/test_personality_probe.py:30,46,47,60,72,77,88`.
  Data declarations: `label: str`; `user_text: str`.
- `PersonalityProbeCase.__post_init__` (line 31): no external lexical candidates.
- `PersonalityProbeObservation` (line 39): no external lexical candidates.
  Data declarations: `label: str`; `request_sha256: str`; `raw_response: str | None`; `elapsed_seconds: float`; `error_type: str | None`; `error_message: str | None`.
- `PersonalityProbeObservation.succeeded` (line 50): `src/sofia/application/conversation_matrix.py:592`; `src/sofia/cognition/activity.py:153,160`; `src/sofia/cognition/routing.py:40,53`; `src/sofia/integrate/model.py:25`; `src/sofia/integrate/receipts.py:15,38,42`; `src/sofia/machine/capability.py:105,113`; `src/sofia/ops/recovery.py:67,75`; `src/sofia/verify/dual_cognition.py:50,190`; `src/sofia/cognition/matrix/model.py:486,496,530`; `src/sofia/cognition/matrix/trace.py:251`; `test/test_cognitive_routing.py:732,775`; `test/test_dev_know_integrate_ops_cross_package.py:62,86,105`; `test/test_know_integrate_wave1_acceptance.py:28`; `test/test_know_integrate_waves3_5_acceptance.py:62`; `test/test_machine_inventory_refresh.py:109,137,158,162,191,221,240,251,278,279,310,311`; `test/test_ops_backup_restore.py:130`; `test/test_personality_probe.py:32,54`; `test/test_verify_dual_cognition.py:30`; `test/test_waves3_5_cross_package_acceptance.py:24,58,69,71`.
- `observe_personality_cases` (line 54): `test/test_personality_probe.py:29,45,62,64,71,78,80,87`.

### `src/sofia/personality/reflection.py`

Production/test importers: `src/sofia/application/act_service.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/observation_bridge.py`, `src/sofia/personality/reflection_query.py`, `src/sofia/personality/thought_agent.py`, `src/sofia/runtime/response.py`, `test/test_emotional_conversation_string_path_regression.py`, `test/test_idle_reflection_worker.py`, `test/test_observation_bridge.py`, `test/test_observation_bridge_self_noise.py`, `test/test_personality_journal_thread_safety.py`, `test/test_reflection_audit.py`, `test/test_reflection_conversation_integration.py`, `test/test_reflection_journal.py`, `test/test_reflection_query.py`, `test/test_thought_agent.py`, `test/test_thought_agent_conversation.py`, `test/test_thought_agent_live_ollama.py`, `test/test_thought_urgency_evidence.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import contextmanager`
- `from dataclasses import dataclass`
- `from datetime import date, datetime, timedelta, timezone`
- `from hashlib import sha256`
- `import json`
- `import re`
- `from pathlib import Path`
- `import sqlite3`
- `from uuid import uuid4`
- `from sofia.social.model import AudienceKind, ScopeKind, SocialScope`

Definitions:

- `_utc` (line 26): `src/sofia/act/delivery.py:222,223,393,423,580`; `src/sofia/act/outreach.py:77,154,186,204,229,244,246,258,304`; `src/sofia/dev/approval.py:75`; `src/sofia/distributed/durable.py:74,198`; `src/sofia/distributed/inference_control.py:113,210`; `src/sofia/evolve/executor.py:337,441`; `src/sofia/evolve/revision.py:94,108,109,140,268,270,271,336,337,339,440`; `src/sofia/habits/engine.py:102,206,241,274,306`; `src/sofia/habits/expectations.py:211,212,213,275`; `src/sofia/interaction/ledger.py:109,141`; `src/sofia/interaction/world.py:52,58`; `src/sofia/memory/provenance_store.py:117,146`; `src/sofia/personality/clarification.py:89,109`; `src/sofia/run/heartbeat.py:33,82,159`; `src/sofia/run/lease.py:131,251,322,378`; `src/sofia/run/periodic.py:53,106`; `src/sofia/run/supervisor.py:293`; `src/sofia/state/migration_lease.py:44,45,120,190`.
- `_short` (line 32): no external lexical candidates.
- `_refs` (line 39): no external lexical candidates.
- `_scope` (line 48): `src/sofia/authorization/evaluator.py:68,72,152`; `src/sofia/interaction/temporal.py:135,153,162,174,190`; `src/sofia/state/sqlite_plane.py:129,147,247`.
- `_period` (line 56): `test/test_reflection_journal.py:52,53`.
- `RecordedThought` (line 79): `src/sofia/personality/reflection_query.py:80,85`; `test/test_reflection_query.py:10,11`.
  Data declarations: `thought_id: str`; `kind: str`; `created_at: datetime`; `subject: str`; `content: str`; `evidence_refs: tuple[str, ...]`; `emotions: tuple[str, ...]`; `period_key: str | None`; `scope_kind: str = ScopeKind.GLOBAL.value`; `principal_id: str | None = None`; `audience_id: str | None = None`; `audience_kind: str | None = None`.
- `RecordedThought.scope` (line 94): `src/sofia/application/act_service.py:126,128,137,143`; `src/sofia/application/emotional_conversation.py:389,408,450,454,524,561,581,584`; `src/sofia/application/idle_reflection.py:111,114,138`; `src/sofia/authorization/evaluator.py:63,68`; `src/sofia/authorization/model.py:52,85`; `src/sofia/composition/authorization.py:148,174`; `src/sofia/config/model.py:257,258`; `src/sofia/dev/git_workspace.py:21,22`; `src/sofia/evolve/revision.py:63,75,101,199,345,353,368,374,378,400,413,453,459,464`; `src/sofia/evolve/state_plane_adapter.py:28,30,36,41,46,49,60,65,84,85,98,145,156`; `src/sofia/memory/chatgpt_export.py:311,313,315,316`; `src/sofia/personality/emotion.py:141,142,144,382,795,802,890,965,1072`; `src/sofia/personality/thought_agent.py:79,177`; `src/sofia/runtime/runtime.py:692`; `src/sofia/state/sqlite_plane.py:147,157,180,213`; `src/sofia/verify/interaction/avatar_world_probe.py:117,121`; `test/test_authorization.py:44`; `test/test_authorization_evaluator.py:37`; `test/test_evolve_revision.py:29,32,38,44,48,51,74,77,152`; `test/test_interaction_temporal.py:38,39,47,49,51`; `test/test_reflection_conversation_integration.py:27,33,41,44`; `test/test_thought_agent_conversation.py:19,23`.
- `OutboxEntry` (line 111): no external lexical candidates.
  Data declarations: `message_id: str`; `thought_id: str`; `thread_id: str`; `evidence_ref: str`; `content: str`; `urgency: str`; `queued_at: datetime`; `status: str`.
- `ReflectionJournal` (line 122): `src/sofia/application/act_service.py:118,124`; `src/sofia/application/emotional_conversation.py:98,126,149`; `src/sofia/personality/observation_bridge.py:21,30,82,99`; `src/sofia/personality/thought_agent.py:44,48`; `src/sofia/runtime/response.py:142`; `test/test_emotional_conversation_string_path_regression.py:37`; `test/test_idle_reflection_worker.py:18,101,124,152,177`; `test/test_observation_bridge.py:38,55`; `test/test_observation_bridge_self_noise.py:32,46`; `test/test_personality_journal_thread_safety.py:33`; `test/test_reflection_audit.py:33,44,73`; `test/test_reflection_conversation_integration.py:26,44,55`; `test/test_reflection_journal.py:30,39,40,49,58,70,90,94,100`; `test/test_thought_agent.py:23,48,61`; `test/test_thought_agent_conversation.py:39,48`; `test/test_thought_agent_live_ollama.py:31`; `test/test_thought_urgency_evidence.py:21`.
- `ReflectionJournal.__init__` (line 125): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `ReflectionJournal._create_schema` (line 131): no external lexical candidates.
- `ReflectionJournal._initialize` (line 192): `src/sofia/cognition/activity.py:51`; `src/sofia/memory/chatgpt_import_store.py:27`; `src/sofia/social/store.py:16`; `src/sofia/state/sqlite_plane.py:22`; `src/sofia/ui/drafts.py:69`; `src/sofia/cognition/matrix/trace.py:47`.
- `ReflectionJournal._connect` (line 259): `src/sofia/act/delivery.py:130,225,264,394,425,541,591`; `src/sofia/act/system_notice.py:45,172,311,377`; `src/sofia/application/background.py:44,73,148`; `src/sofia/application/idle_reflection.py:42,61,86`; `src/sofia/cognition/activity.py:60,106,169,178`; `src/sofia/config/user_settings.py:322,397,427`; `src/sofia/discord/binding.py:70,128,198,243,316,405,497`; `src/sofia/discord/delivery.py:106,153,240,280,320,354,409,425,437`; `src/sofia/discord/store.py:81,181,242,289,369,458,496,545,604,627,639`; `src/sofia/distributed/durable.py:50,180`; `src/sofia/distributed/inference_control.py:85,115,143,160`; `src/sofia/evolve/executor.py:114,318,381,472`; `src/sofia/evolve/revision.py:234,319,387,467`; `src/sofia/interaction/ledger.py:67,95,110,143,177`; `src/sofia/interaction/world.py:84,117,122,131,137,153`; `src/sofia/memory/chatgpt_export_store.py:61,163,291,325,415,442`; `src/sofia/memory/chatgpt_migration.py:36,114,174,200`; `src/sofia/operational/store.py:41,66,148,195`; `src/sofia/ops/activity.py:73,114,130,160`; `src/sofia/personality/clarification.py:47,91,112`; `src/sofia/personality/emotion.py:244,400,477,598,665,702,780,803,872`; `src/sofia/run/heartbeat.py:49,83,127`; `src/sofia/run/lease.py:60,135,257,323,379,404`; `src/sofia/run/periodic.py:78,130,188,216`; `src/sofia/run/supervisor.py:130,301,321,563`; `src/sofia/safe/audit.py:24,104,198`; `src/sofia/safe/dev_approval.py:24,49,109`; `src/sofia/social/store.py:24,49,108`; `src/sofia/state/component_schema.py:36,73,127,170`; `src/sofia/state/sqlite_plane.py:36,82,120,148,238,269`; `src/sofia/ui/control_center.py:133,157,206`; `src/sofia/ui/remote_transport.py:140,165,190,204`; `src/sofia/verify/semantic_integrity.py:82,429`; `src/sofia/cognition/matrix/trace.py:56,477,527,538,568,596`; `test/test_interaction_i5_i7_batch.py:95`; `test/test_runtime_user_settings.py:189,252,261`.
- `ReflectionJournal.record_thought` (line 271): `src/sofia/personality/observation_bridge.py:70,110`; `src/sofia/personality/thought_agent.py:169`; `test/test_idle_reflection_worker.py:28`; `test/test_personality_journal_thread_safety.py:36`; `test/test_reflection_audit.py:47`; `test/test_reflection_journal.py:71,102,104,109,113`.
- `ReflectionJournal.recent_thoughts` (line 337): `src/sofia/application/emotional_conversation.py:387`; `src/sofia/personality/thought_agent.py:77`; `src/sofia/runtime/response.py:146,159`; `test/test_idle_reflection_worker.py:53,69,109`; `test/test_observation_bridge.py:55,67,86,87,126`; `test/test_observation_bridge_self_noise.py:39,61,79`; `test/test_personality_journal_thread_safety.py:46`; `test/test_reflection_audit.py:34`; `test/test_reflection_conversation_integration.py:41,44,57`; `test/test_reflection_journal.py:40,62`; `test/test_thought_agent.py:46,47,61,71,86,104`; `test/test_thought_agent_conversation.py:49,74`; `test/test_thought_agent_live_ollama.py:65`; `test/test_thought_urgency_evidence.py:35`.
- `ReflectionJournal.reflect_due` (line 360): `src/sofia/application/emotional_conversation.py:581`; `src/sofia/application/idle_reflection.py:112`; `test/test_reflection_journal.py:34,39,51,59,61,63`.
- `ReflectionJournal.enqueue` (line 499): `src/sofia/application/act_service.py:104,158`; `src/sofia/personality/thought_agent.py:195`; `test/test_act_delivery.py:378`; `test/test_act_system_notice.py:45,74,103,118,126,156,212,224,232`; `test/test_reflection_journal.py:76,78,81,85,87`.
- `ReflectionJournal.defer_followup` (line 558): `src/sofia/personality/thought_agent.py:210`.
- `ReflectionJournal.due_followups` (line 606): no external lexical candidates.
- `ReflectionJournal.mark_outbox_bridged` (line 628): `src/sofia/application/act_service.py:175`.
- `ReflectionJournal.pending` (line 639): `src/sofia/application/act_service.py:143,204`; `src/sofia/discord/discordpy.py:249,254`; `src/sofia/discord/operator.py:51,60`; `src/sofia/integrations/discord.py:18,20`; `src/sofia/ops/discovery.py:330,347,358,370,395`; `test/test_avatar_clothing_action.py:575`; `test/test_avatar_presentation_store.py:178`; `test/test_discord_recovery.py:146,151`; `test/test_idle_reflection_worker.py:62`; `test/test_interaction_goal_journal.py:43,45,49`; `test/test_observation_bridge.py:58,88`; `test/test_reflection_journal.py:90,91,92,94`; `test/test_thought_agent.py:48,49,50,52,62,86,96,104`; `test/test_thought_agent_conversation.py:51`; `test/test_thought_agent_live_ollama.py:66,67,68,69,70,71`; `test/test_thought_urgency_evidence.py:36,50,51,62`.
- `ReflectionJournal.confirm_delivery` (line 658): `test/test_reflection_journal.py:93,96`.
- `ReflectionJournal._topic_tokens` (line 670): no external lexical candidates.
- `ReflectionJournal.prompt_context` (line 693): `src/sofia/application/emotional_conversation.py:558,573,583`; `test/test_emotional_clarifications.py:44,45,59`; `test/test_emotional_journal.py:49,76,99`; `test/test_reflection_journal.py:44`.

Module declarations: `_PERIODS = ('daily', 'weekly', 'monthly', 'yearly')`; `_URGENCIES = frozenset({'routine', 'excited', 'urgent'})`.

### `src/sofia/personality/reflection_query.py`

Production/test importers: `src/sofia/runtime/runtime.py`, `test/test_reflection_query.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `import re`
- `from sofia.personality.reflection import RecordedThought`

Definitions:

- `ReflectionQueryAnswer` (line 16): no external lexical candidates.
  Data declarations: `recognized: bool`; `content: str = ''`.
- `ReflectionQueryAnswer.__post_init__` (line 20): no external lexical candidates.
- `_normalize` (line 29): `src/sofia/avatar/clothing_action.py:468,472,510,511`; `src/sofia/avatar/clothing_intent.py:16`; `src/sofia/avatar/self_fact_query.py:119,347`; `src/sofia/environment/query.py:315,321,334,341,377`; `src/sofia/operational/status_queries.py:80`.
- `_conversational_reflection` (line 35): no external lexical candidates.
- `ReflectionQueryResolver` (line 55): `src/sofia/runtime/runtime.py:229`; `test/test_reflection_query.py:24,48,66,78`.
  Data declarations: `_QUERY_RE = re.compile("\\b(?:what(?:'s|\\s+is)\\s+on\\s+your\\s+mind|what\\s+have\\s+you\\s+been\\s+thinking(?:\\s+about)?|what\\s+are\\s+you\\s+thinking(?:\\s+about)?|what\\s+were\\s+you\\s+thinking(?:\\s+about)?|anything\\s+on\\s+your\\s+mind|(?:list|show)\\s+(?:me\\s+)?(?:your\\s+)?recorded\\s+reflections|(?:show|give\\s+me)\\s+(?:your\\s+)?reflection\\s+history)\\b", re.IGNORECASE)`.
- `ReflectionQueryResolver.might_match` (line 70): `src/sofia/runtime/response.py:140,261`; `test/test_environment_query.py:130,316,344,411,461,517`; `test/test_reflection_query.py:78`.
- `ReflectionQueryResolver.resolve` (line 76): `src/sofia/application/bootstrap.py:148`; `src/sofia/application/conversation_matrix.py:487,667`; `src/sofia/authorization/evaluator.py:68`; `src/sofia/avatar/clothing_action.py:223`; `src/sofia/capability/gateway.py:64`; `src/sofia/clean/__main__.py:87`; `src/sofia/clean/recovery.py:49,70,77,78`; `src/sofia/codebase/codebase.py:91`; `src/sofia/codebase/inspector.py:59`; `src/sofia/cognition/tools.py:501`; `src/sofia/composition/authorization.py:114,115,144,148,164,174`; `src/sofia/config/defaults.py:20`; `src/sofia/config/state_store.py:116`; `src/sofia/dev/git_workspace.py:29`; `src/sofia/dev/opencode.py:31`; `src/sofia/dev/workflow.py:22`; `src/sofia/dev/workspace.py:9,16`; `src/sofia/discord/process_lock.py:15`; `src/sofia/distributed/agent_main.py:85,124`; `src/sofia/distributed/pki.py:233`; `src/sofia/distributed/state_paths.py:95`; `src/sofia/distributed/windows_agent_service_admin.py:125,200`; `src/sofia/filesystem/change_capability.py:18`; `src/sofia/filesystem/change_filter.py:28,32`; `src/sofia/filesystem/inspector.py:42,593,613`; `src/sofia/filesystem/observation.py:141,340`; `src/sofia/habits/continuity.py:270,307`; `src/sofia/integrate/capability_adapter.py:24`; `src/sofia/integrations/sqlite.py:10,39`; `src/sofia/integrations/storage.py:10,22`; `src/sofia/interaction/trusted_offer_gate.py:56`; `src/sofia/knowledge/ingest.py:8`; `src/sofia/knowledge/repository_ingest.py:11,12`; `src/sofia/knowledge/service.py:25,57`; `src/sofia/machine/location_cli.py:165`; `src/sofia/ops/windows_bootstrap.py:526`; `src/sofia/ops/windows_rekey_bootstrap.py:185`; `src/sofia/personality/observation_bridge.py:40,43`; `src/sofia/run/active_release.py:46,48,50,105,106,111,164,166`; `src/sofia/run/release.py:347`; `src/sofia/run/runtime_child.py:46`; `src/sofia/run/runtime_service.py:49`; `src/sofia/run/service_admin.py:121,211`; `src/sofia/run/supervisor.py:117`; `src/sofia/runtime/runtime.py:689,692,715`; `src/sofia/runtime/response.py:164,170,191,208,218,271,318`; `src/sofia/safe/capability_policy.py:35`; `src/sofia/ui/process_lock.py:27,30`; `src/sofia/ui/tray_agent.py:408`; `src/sofia/ui/tray_launcher.py:52`; `src/sofia/ui/windows_startup.py:20`; `src/sofia/verify/interaction/live_behavior_probe.py:240,243`; `src/sofia/verify/interaction/disposable_live_offer_probe.py:51,54,62`; `test/test_authorization_evaluator.py:37`; `test/test_avatar_presentation_runtime.py:13`; `test/test_avatar_private_grant.py:26,51`; `test/test_avatar_self_fact_query.py:18,41,122,159,188,226,248,274,302,325,387,439,463`; `test/test_canonical_embodiment.py:11`; `test/test_capability_system.py:40,72`; `test/test_cognition_matrix.py:656,874`; `test/test_dev_wave1_acceptance.py:15`; `test/test_distributed_agent_main.py:40,43,46,49`; `test/test_distributed_pki.py:16,24`; `test/test_distributed_windows_agent_service.py:105,134`; `test/test_embodiment_measurement_cognition.py:47,76,109,137`; `test/test_embodiment_measurement_query.py:69,81,137,160,172,185,199,210,234,250`; `test/test_environment_acceptance.py:90,116`; `test/test_environment_behavior_matrix.py:35`; `test/test_environment_query.py:48,58,90,100,111,151,181,193,211,217,251,318,385,416,420,448,464,501,525,549,565,566,588,604,635,670`; `test/test_filesystem.py:415`; `test/test_filesystem_observation.py:67,77`; `test/test_habit_foundation.py:226,259`; `test/test_interaction_ab_probe.py:15`; `test/test_interaction_avatar_world.py:19`; `test/test_interaction_behavior_matrix.py:23`; `test/test_interaction_chat_projection.py:22`; `test/test_interaction_consent_followup.py:14`; `test/test_interaction_contextual_all_regions.py:14`; `test/test_interaction_decision_expression.py:22`; `test/test_interaction_focused_probe.py:15`; `test/test_interaction_i5_i7_batch.py:17`; `test/test_interaction_i7_compound_regression.py:11`; `test/test_interaction_import_order.py:13`; `test/test_interaction_lab.py:11`; `test/test_interaction_live_boundaries.py:20`; `test/test_interaction_live_claims.py:20`; `test/test_interaction_live_discussion.py:14`; `test/test_interaction_live_phrase_coverage.py:13`; `test/test_interaction_live_stop_repetition.py:19`; `test/test_interaction_region_cue_collision.py:8`; `test/test_interaction_registry.py:14`; `test/test_interaction_shared_engine.py:12`; `test/test_interaction_v2_cross_modal.py:12`; `test/test_interaction_v2_live_grammar.py:14`; `test/test_interaction_world_observation.py:18`; `test/test_interaction_world_text.py:18`; `test/test_operational_status_queries.py:25,46,57,65,85`; `test/test_ops_windows_rekey_bootstrap.py:26,34`; `test/test_personality_pipeline.py:14`; `test/test_proactive_continuity_awareness.py:337,338,339`; `test/test_production_storage_boundary.py:13`; `test/test_reflection_query.py:24,48,66`; `test/test_run_active_release.py:82,96,105,118,132,143`; `test/test_run_service_admin.py:104,142`; `test/test_runtime.py:570`; `test/test_tools_completion_acceptance.py:101,245`; `test/test_voice_matrix.py:16,22`.

### `src/sofia/personality/review.py`

Production/test importers: `test/test_personality_evaluation.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from enum import Enum`
- `from sofia.personality.evaluation import PersonalityObservation`

Definitions:

- `ReviewFinding` (line 10): `src/sofia/dev/change_review.py:45,50,53,54`; `test/test_personality_evaluation.py:79,81,85,89,90`.
  Data declarations: `SUPPORTED = 'supported'`; `NOT_SUPPORTED = 'not_supported'`; `UNCERTAIN = 'uncertain'`.
- `PersonalityReview` (line 17): `test/test_personality_evaluation.py:78,88`.
  Data declarations: `observation: PersonalityObservation`; `reviewer: str`; `findings: tuple[tuple[str, ReviewFinding, str], ...]`.
- `PersonalityReview.__post_init__` (line 22): no external lexical candidates.

### `src/sofia/personality/store.py`

Production/test importers: `src/sofia/composition/root.py`, `src/sofia/runtime/runtime.py`, `src/sofia/verify/interaction/ab_probe.py`, `src/sofia/verify/interaction/architecture_compare.py`, `src/sofia/verify/interaction/boundary_counterfactual_probe.py`, `src/sofia/verify/interaction/decision_expression_probe.py`, `src/sofia/verify/interaction/focused_probe.py`, `src/sofia/verify/interaction/route_boundary_probe.py`, `test/test_composition.py`, `test/test_interaction_ab_probe.py`, `test/test_interaction_decision_expression.py`, `test/test_interaction_focused_probe.py`, `test/test_personality_pipeline.py`, `test/test_personality_store.py`.

Imports:

- `import json`
- `from pathlib import Path`
- `from sofia.personality.model import PersonalityProfile`
- `from sofia.state.atomic_file import atomic_write_text`

Definitions:

- `PersonalityStoreError` (line 8): `test/test_personality_store.py:146,162,178,197,217`.
- `PersonalityStore` (line 12): `src/sofia/composition/root.py:151`; `src/sofia/runtime/runtime.py:101,276`; `src/sofia/verify/interaction/route_boundary_probe.py:99`; `src/sofia/verify/interaction/focused_probe.py:103`; `src/sofia/verify/interaction/architecture_compare.py:99`; `src/sofia/verify/interaction/decision_expression_probe.py:69`; `src/sofia/verify/interaction/ab_probe.py:103`; `src/sofia/verify/interaction/boundary_counterfactual_probe.py:94`; `test/test_composition.py:97`; `test/test_interaction_ab_probe.py:29`; `test/test_interaction_decision_expression.py:33`; `test/test_interaction_focused_probe.py:26`; `test/test_personality_pipeline.py:28,40`; `test/test_personality_store.py:30,61,73,94,126,135,143,159,175,194,214`.
- `PersonalityStore.__init__` (line 20): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `PersonalityStore.save` (line 23): `src/sofia/application/bootstrap.py:912`; `src/sofia/application/conversation_service.py:510,656`; `src/sofia/avatar/presentation_runtime.py:101,156,202`; `src/sofia/avatar/presentation_store.py:110,132`; `src/sofia/config/user_settings.py:413`; `src/sofia/discord/live.py:109`; `src/sofia/environment/settings_cli.py:83,139`; `src/sofia/identity/store.py:76,113`; `src/sofia/interaction/chat.py:468,504`; `src/sofia/interaction/live_offer_service.py:117`; `src/sofia/interaction/question_clarification_service.py:48`; `src/sofia/machine/capability.py:111`; `src/sofia/machine/persistence.py:596`; `src/sofia/memory/import_chatgpt.py:88,116`; `src/sofia/memory/system.py:87`; `src/sofia/ui/control_center.py:192`; `src/sofia/ui/settings_window.py:845,846,881`; `src/sofia/ui/text.py:120`; `src/sofia/ui/tray_agent.py:425`; `src/sofia/verify/interaction/disposable_live_offer_probe.py:145`; `test/test_avatar_clothing_action.py:55`; `test/test_avatar_presentation_routine.py:36`; `test/test_avatar_presentation_runtime.py:146`; `test/test_avatar_presentation_store.py:63,73,97,153,188`; `test/test_chatgpt_export_import.py:196,197`; `test/test_chatgpt_memory_import.py:46,96,97`; `test/test_conversation.py:30,67,68,108,109,152,184,198,229`; `test/test_discord_provisioning.py:108,144,178,194,217`; `test/test_embodiment.py:130,143`; `test/test_environment_factory.py:217`; `test/test_environment_hot_reload.py:47,98`; `test/test_identity.py:60,73,115,129`; `test/test_interaction_live_stop_repetition.py:48`; `test/test_machine_inventory_persistence.py:300,329,343,356,410`; `test/test_machine_regression.py:295,300`; `test/test_memory.py:55,86,87,109,110,142,163,190,191,214`; `test/test_memory_conversation_originals.py:22,29,30,45,46,61,62`; `test/test_memory_reviewed_workflow.py:16`; `test/test_memory_runtime_wiring.py:354,395,433`; `test/test_personality_store.py:34,64,81,102,138`; `test/test_production_dual_cognition.py:19`; `test/test_runtime_user_settings.py:55`; `test/test_runtime_user_settings_defaults.py:57,97,114,146,179,204,228`; `test/test_ui_control_center.py:46,58`; `test/test_ui_drafts.py:14,37,42,47,73,79,112,131`.
- `PersonalityStore.load` (line 52): `src/sofia/application/bootstrap.py:120,391`; `src/sofia/avatar/presentation_runtime.py:149,157,187`; `src/sofia/config/defaults.py:315`; `src/sofia/discord/live.py:103`; `src/sofia/discord/provisioning.py:131`; `src/sofia/distributed/agent_tools.py:90`; `src/sofia/environment/factory.py:43`; `src/sofia/environment/settings_cli.py:68,130,133`; `src/sofia/evolve/executor.py:227,231`; `src/sofia/machine/capability.py:53`; `src/sofia/machine/location_cli.py:45,72`; `src/sofia/machine/persistence.py:592,594,597`; `src/sofia/ops/backup.py:418,429`; `src/sofia/runtime/runtime.py:521,527,528,529`; `src/sofia/ui/control_center.py:184`; `src/sofia/ui/service_control.py:152`; `src/sofia/ui/settings_window.py:111`; `src/sofia/ui/text.py:114`; `src/sofia/ui/tray_agent.py:172,202,422,485`; `src/sofia/verify/interaction/route_boundary_probe.py:96,98,99,100`; `src/sofia/verify/interaction/focused_probe.py:100,102,103,104`; `src/sofia/verify/interaction/architecture_compare.py:96,98,99,100`; `src/sofia/verify/interaction/decision_expression_probe.py:66,68,69,70`; `src/sofia/verify/interaction/ab_probe.py:100,102,103,104`; `src/sofia/verify/interaction/boundary_counterfactual_probe.py:91,93,94,95`; `test/test_avatar_clothing_action.py:60`; `test/test_avatar_presentation_runtime.py:18,60`; `test/test_avatar_presentation_store.py:64,117,143`; `test/test_avatar_self_fact_query.py:22`; `test/test_canonical_embodiment.py:72`; `test/test_constitution_integrity.py:32,105,106,107,117,118`; `test/test_constitution_store.py:17`; `test/test_embodiment.py:132,157,176`; `test/test_environment_behavior_matrix.py:213`; `test/test_environment_hot_reload.py:21`; `test/test_environment_settings_cli.py:21,33,47`; `test/test_evolve_executor.py:163`; `test/test_identity.py:75,86,98,99,117,147,163,179,195,211,226,231,249,265`; `test/test_interaction_ab_probe.py:28,29,30,31,54`; `test/test_interaction_avatar_world.py:25`; `test/test_interaction_behavior_matrix.py:30`; `test/test_interaction_chat_projection.py:46,142`; `test/test_interaction_consent_followup.py:64,103,141`; `test/test_interaction_contextual_all_regions.py:19`; `test/test_interaction_decision_expression.py:32,33,34,35,41`; `test/test_interaction_focused_probe.py:25,26,27,28`; `test/test_interaction_i5_i7_batch.py:22,154`; `test/test_interaction_i7_compound_regression.py:16`; `test/test_interaction_lab.py:17`; `test/test_interaction_live_boundaries.py:38`; `test/test_interaction_live_claims.py:73`; `test/test_interaction_live_discussion.py:26,44`; `test/test_interaction_live_phrase_coverage.py:18`; `test/test_interaction_live_stop_repetition.py:35,123`; `test/test_interaction_region_cue_collision.py:13`; `test/test_interaction_registry.py:19`; `test/test_interaction_shared_engine.py:17`; `test/test_interaction_v2_cross_modal.py:16,27`; `test/test_interaction_v2_live_grammar.py:19`; `test/test_interaction_world_observation.py:92`; `test/test_interaction_world_text.py:92,114`; `test/test_machine_inventory_persistence.py:302,344,359`; `test/test_machine_regression.py:297,302`; `test/test_ollama_unload.py:29`; `test/test_personality_pipeline.py:28,40`; `test/test_personality_store.py:66,83,104,128,149,165,181,200,220`; `test/test_runtime_user_settings.py:57,200,259,299`; `test/test_ui_control_center.py:30,47`; `test/test_ui_desktop_storage_authority.py:82`; `test/test_ui_drafts.py:23,53,57,61,86,100,119,140`.

### `src/sofia/personality/system.py`

Production/test importers: `test/test_personality.py`.

Imports:

- `from types import MappingProxyType`
- `from sofia.personality.model import PersonalityProfile`

Definitions:

- `PersonalitySystem` (line 6): `test/test_personality.py:67,78,94,106,129`.
- `PersonalitySystem.__init__` (line 7): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `PersonalitySystem.profile` (line 11): `src/sofia/application/bootstrap.py:347,368,375`; `src/sofia/machine/capability.py:59,79,80,81,82,83,85,87,88,89,90,91`; `src/sofia/machine/comparison.py:44,45,49,50,54,55,59,60`; `src/sofia/machine/observation.py:47,54,91,95,107,130`; `src/sofia/machine/persistence.py:112,113,116,117,118,119,120,124,126,127,130,131,132,135,139,144,147,149,155,156,158,162,166,170,284`; `src/sofia/machine/refresh.py:182,191`; `src/sofia/ops/machine_bridge.py:10,11`; `src/sofia/personality/probe.py:66,89`; `src/sofia/personality/store.py:24,30,31,32,33`; `src/sofia/voice/prosody_matrix.py:10`; `src/sofia/voice/sapi.py:128,146,147`; `src/sofia/voice/tts.py:136,301,302,329,401`; `test/test_machine_inventory_contract.py:84,142,143,155`; `test/test_machine_inventory_lifecycle.py:81,260,544,549`; `test/test_machine_inventory_persistence.py:242,243`; `test/test_machine_inventory_refresh.py:114,139,286,293,294`; `test/test_machine_location_inventory.py:26,45`; `test/test_machine_model.py:127,145,146,147,151,167`; `test/test_machine_regression.py:125,128,131,153,154,155,174,176,177,226,232,253,266`; `test/test_ops_waves3_5_acceptance.py:38,45`; `test/test_personality.py:61,67,69,73,78,88,94,100,106,123,129`; `test/test_personality_evaluation.py:28,31`; `test/test_personality_expression_boundary.py:18,20,34,35,36`; `test/test_personality_pipeline.py:23,28,29,32,33,34,35,40,41,42`; `test/test_personality_probe.py:28,29,59,62,64,76,78,80`; `test/test_personality_provider_path.py:22,30,49,53`; `test/test_personality_store.py:32,34,63,64,68,75,81,96,102`; `test/test_system_capability_integration_hardening.py:54,75,596,610,613`; `test/test_system_machine_knowledge_integration.py:40,61,182`; `test/test_thought_agent_conversation.py:35,81`; `test/test_voice_prosody_matrix.py:32,34,36,38,40,42`; `test/test_voice_tts.py:48`.
- `PersonalitySystem.traits` (line 15): `src/sofia/cognition/assembler.py:289,291`; `src/sofia/personality/model.py:7`; `src/sofia/personality/store.py:31,73,90,95,113`; `src/sofia/verify/interaction/ab_probe.py:55`; `test/test_cognitive_context.py:204`; `test/test_personality.py:20,34,53,80`; `test/test_personality_pipeline.py:33`; `test/test_personality_store.py:85`.
- `PersonalitySystem.communication_style` (line 19): `src/sofia/cognition/assembler.py:294,297`; `src/sofia/personality/model.py:8`; `src/sofia/personality/store.py:32,74,100,114`; `src/sofia/verify/interaction/ab_probe.py:56`; `test/test_personality.py:44,96`; `test/test_personality_pipeline.py:34`.
- `PersonalitySystem.embodiment_guidance` (line 23): `src/sofia/cognition/assembler.py:300,303`; `src/sofia/personality/model.py:9`; `src/sofia/personality/store.py:33,80,105,115`; `src/sofia/verify/interaction/ab_probe.py:57`; `test/test_personality_pipeline.py:35`; `test/test_personality_store.py:107,130`.
- `PersonalitySystem.context` (line 26): `src/sofia/application/bootstrap.py:544,556`; `src/sofia/application/conversation_matrix.py:217,218,382,384,395`; `src/sofia/avatar/presentation_routine.py:152`; `src/sofia/avatar/wardrobe_autonomy.py:123,128,129`; `src/sofia/avatar/wardrobe_planner.py:366,376,380,381,390,392,396,404,406,408,429,438,444,445,449,450,452`; `src/sofia/cognition/assembler.py:85,105,112,118,119,120,127,141,224,228,232,237,239,245,254,255,256,259,261,264,274,275,279,284,289,291,294,297,300,303,306,311,312,314,319,320,337,354,366,371,392,436,437,504,513,514,552,553,556,560,578,584,585,587,600`; `src/sofia/cognition/conversation_assembler.py:127,128,129,131,132,136,139,142,143,144`; `src/sofia/cognition/operation.py:16,20`; `src/sofia/cognition/system.py:143,149,154,192,253,255`; `src/sofia/distributed/agent.py:345,346,347,348,349,350`; `src/sofia/distributed/https_transport.py:45,46,47,48`; `src/sofia/habits/continuity.py:67,73,75,80,89,131,148,149,167,168,327`; `src/sofia/habits/controls.py:21,55,85,100,103`; `src/sofia/habits/engine.py:32,308,311,328`; `src/sofia/habits/model.py:34,67,69`; `src/sofia/habits/pattern_store.py:43`; `src/sofia/habits/patterns.py:44,63`; `src/sofia/habits/recorder.py:70`; `src/sofia/habits/store.py:46`; `src/sofia/integrate/governed.py:33`; `src/sofia/integrate/policy.py:16,18`; `src/sofia/interaction/evolved_preference.py:16,45,50,54,99`; `src/sofia/interaction/expanded_service.py:80,81,82,175,191,218,221,224,236,237`; `src/sofia/interaction/live_offer_service.py:56,78`; `src/sofia/interaction/preference_context.py:61,98,112`; `src/sofia/interaction/source_link.py:110`; `src/sofia/interaction/temporal.py:41,138,141,148,157,168`; `src/sofia/interaction/trusted_offer_gate.py:71,74,76`; `src/sofia/ops/agent_discovery.py:83,87,88,92`; `src/sofia/personality/evaluation.py:21,26,28,30,31,69`; `src/sofia/ui/remote_transport.py:360,361,362,363,364,368,388,392,393,397`; `src/sofia/cognition/matrix/model.py:543,560,561`; `src/sofia/cognition/matrix/trace.py:124,129,132,134,135,288,291,461,515`; `test/test_avatar_clothing_action.py:309,312,330,336,354,360,378,386,403,410`; `test/test_avatar_lounge_graphic_tee.py:91,97`; `test/test_avatar_presentation_routine.py:46,51,88,93,101,114,134,139`; `test/test_avatar_wardrobe_environment_context.py:71,76,77,78,79,80,81,85,89,90,107,114,115`; `test/test_cognition_matrix.py:544,549,558,560,873,929`; `test/test_cognitive_assembler.py:182,184,192,194,204,206,221,223,236,240,268,272,284,288,300,304,312,316,334,338,346,351,369,374,387,392,403,408,419,423,434,438,455,459,464,480`; `test/test_cognitive_context.py:40,45,49,53,120,124,131,136,143,148,157,162,166,170,171,172,176,181,224,228,234,239`; `test/test_cognitive_context_assembler.py:65,71,86,91,126,131,142,155,177,190,215,228,259,272,344,357,427,440,460,473,483,495,525,530,546,559,587,603,633,649,689,706`; `test/test_cognitive_grounding_contract.py:31,36,165,170,174,179,214,220,241,245,248`; `test/test_cognitive_operation.py:31,35,39,43,47,60`; `test/test_cognitive_operation_system.py:98,203`; `test/test_cognitive_self_state_assembler_contract.py:95,102,248,252`; `test/test_continuity_assembler.py:30,43,67,80`; `test/test_continuity_context.py:48,53,61,65`; `test/test_conversation_provider_live_regressions.py:201,202,266,267,367,368,457,458`; `test/test_conversation_service.py:635,637`; `test/test_conversation_workspace_projection.py:69,70,71,80,81,82,83,87,88,93,97,100,101,102,108,111,117,120,121`; `test/test_conversational_context_projection.py:37,38,39,49,50,55,56,60,65,66,70,75,81,82,86,88,102,103,104,106,113`; `test/test_embodiment_measurement_cognition.py:52,58,59,62,81,89,114,122,127`; `test/test_emotional_journal.py:99,100,101,102,103,104`; `test/test_environment_behavior_matrix.py:142,150,175,179,323,327`; `test/test_habit_contextual_matrix.py:60,61,67,68,73,74,79,80`; `test/test_habit_foundation.py:179,182`; `test/test_interaction_boundary_revocation.py:31,32`; `test/test_interaction_conversation_offer_context.py:80,97,113,118,126,133,141,143,150,162,182`; `test/test_interaction_opt_in_live_offer.py:50`; `test/test_interaction_preference_context.py:43,45,52,54,64,66`; `test/test_ops_agent_discovery.py:42`; `test/test_personality.py:108,110,130,133`; `test/test_personality_evaluation.py:96,97,98,103`; `test/test_system_capability_assembler_integration.py:74,80,104,110,149,155,180,186,223,229,238`; `test/test_system_capability_context_integration.py:59,66,71,142,148,183,189`.

### `src/sofia/personality/thought_agent.py`

Production/test importers: `src/sofia/application/emotional_conversation.py`, `test/test_thought_agent.py`, `test/test_thought_agent_live_ollama.py`, `test/test_thought_urgency_evidence.py`.

Imports:

- `from __future__ import annotations`
- `from collections.abc import Callable`
- `from dataclasses import dataclass`
- `from datetime import datetime, timedelta, timezone`
- `from hashlib import sha256`
- `import json`
- `from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole`
- `from sofia.personality.emotion import EmotionalEvent`
- `from sofia.personality.reflection import ReflectionJournal`
- `from sofia.personality.influence import ContinuityInfluence, outreach_salience`

Definitions:

- `ReflectionOutcome` (line 24): `src/sofia/application/emotional_conversation.py:318,335`.
  Data declarations: `thought_id: str | None`; `queued_message_id: str | None`.
- `ThoughtGenerationError` (line 29): `test/test_thought_agent.py:84,94,101`; `test/test_thought_urgency_evidence.py:33`.
- `ThoughtAgent` (line 33): `src/sofia/application/emotional_conversation.py:354`; `test/test_thought_agent.py:39,57,69,82,95,102,111,142,180`; `test/test_thought_agent_live_ollama.py:58`; `test/test_thought_urgency_evidence.py:34,45,56`.
- `ThoughtAgent.__init__` (line 40): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `ThoughtAgent.reflect` (line 53): `src/sofia/application/emotional_conversation.py:380`; `test/test_idle_reflection_serialization.py:35`; `test/test_idle_reflection_worker.py:38`; `test/test_thought_agent.py:40,51,59,69,85,95,102,113,115,142,180`; `test/test_thought_agent_live_ollama.py:58`; `test/test_thought_urgency_evidence.py:34,45,59,61`.
