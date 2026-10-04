# Phase 4: rel cleanup

## What was there, what it does, and classification

| File | Decision | Responsibility |
| --- | --- | --- |
| `__init__.py` | KEEP | Exposes RelationshipContact and RelationshipStore. |
| `model.py` | KEEP | Immutable validated principal/audience contact, with timezone-aware evidence timestamp. |
| `store.py` | KEEP | Append-only contact evidence and latest-contact projection; principal-scoped retrieval. |
| `matrix.py` | KEEP | Required REL evidence for relationship questions; contextual contribution on social check-ins. |

## Production trace and state ownership

Bootstrap constructs ConversationService, which constructs RelationshipStore with
the production state plane. User-message handling calls observe. ConversationMatrix
reads history and excludes the current contact before projecting prior-contact
context. The default cognition matrix registry invokes RelationshipMatrixEvaluator.
RelationshipContact is both the write validation value and read projection.

Every store method is on this path: observe calls _append_history and _history_value;
history decodes state-plane records and uses get in the supported no-state-plane
mode. Constructors and validation hooks are reached implicitly. The state-plane
REL_CONTACT_OBSERVATION namespace owns append-only evidence; rel_contact SQLite
is its latest-contact projection, not an independently competing relationship model.
History creation is idempotent only for matching evidence, with conflicts rejected.
Scope ownership remains in social; this folder stores contacts rather than principals.

## What was wrong, merged, deleted, moved, renamed, and fixed

No independently justified structural change was found in these four modules.
The latest-contact cache and evidence history must not be collapsed into one table
or confused with session binding. All files are KEEP. No aliases, compatibility
bridges, duplicate models, or unused public methods were found after following
internal calls and the supported store mode. No source or test contract changed.

## What remains and verification

The current contact store and matrix remain canonical. Compile and diff checks
passed. Targeted production conversation, scoped relationship/habit projection,
and cognition matrix gate: **138 passed** (18.54 s). The full suite from the identical
source/test snapshot at social checkpoint was **3,571 passed, 8 known failures,
2 skipped**; only this report is added by the rel checkpoint.

Commit: `git log -1 --format=%H -- docs/development/rel-cleanup-report.md`.


## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/rel/__init__.py`

Production/test importers: none in direct absolute imports.

Imports:

- `from sofia.rel.model import RelationshipContact`
- `from sofia.rel.store import RelationshipStore`

Definitions:


Module declarations: `__all__ = ['RelationshipContact', 'RelationshipStore']`.

### `src/sofia/rel/matrix.py`

Production/test importers: `src/sofia/cognition/matrix/defaults.py`.

Imports:

- `from __future__ import annotations`
- `import re`
- `from sofia.cognition.matrix.model import DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance`

Definitions:

- `RelationshipMatrixEvaluator` (line 23): `src/sofia/cognition/matrix/defaults.py:69`.
  Data declarations: `domain = MatrixDomain.REL`.
- `RelationshipMatrixEvaluator.evaluate` (line 26): `src/sofia/act/delivery.py:508`; `src/sofia/act/system_notice.py:425`; `src/sofia/application/bootstrap.py:555`; `src/sofia/application/conversation_matrix.py:461`; `src/sofia/application/conversation_service.py:559`; `src/sofia/cognition/matrix/coordinator.py:65`; `test/test_act_outreach.py:36`; `test/test_authority.py:197,214`; `test/test_authorization_evaluator.py:27,48,71,91,114,119,137,142,156,174,187,193,199,228,243,266`; `test/test_avatar_presentation_routine.py:51,93,114,139,167`; `test/test_capability_composition_scope.py:107`; `test/test_cognition_matrix.py:219,238,251,269,323,349,390,404,415,455,495,509,519,529,543,602,617,636,668,687,720,758,795,828,839,858,870,959,989,1025,1036,1049,1102,1111,1121,1147,1184,1261,1277,1301,1330,1392,1406,1419,1431`; `test/test_conversation_service.py:1148,1158`; `test/test_filesystem_orchestrator.py:108`; `test/test_ops_failure_recovery_matrix.py:23,32,37,46,54,63,70,80,87,97,109,132,143,152,161,169,178,192,212`; `test/test_rel_habit_matrix.py:85,107,120`; `test/test_release_compatibility_matrix.py:82,91,100,109,118,127,138,150,159,168,181,192,212`; `test/test_semantic_domain_matrix.py:30,49,69,83,101,117,128`; `test/test_voice_matrix.py:10,12,14,16,21`; `test/test_voice_runtime_matrix.py:5,7,9,11,13,15`.

Module declarations: `_RELATIONSHIP = re.compile("\\b(?:relationship|how\\s+long\\s+(?:have\\s+)?i\\s+been\\s+(?:gone|away)|how\\s+long\\s+was\\s+i\\s+(?:gone|away)|when\\s+(?:did\\s+)?we\\s+last\\s+(?:talk|speak|chat)|last\\s+(?:talked|spoke|chatted)|did\\s+you\\s+miss\\s+me|missed\\s+me|i(?:'|’)m\\s+back)\\b", re.IGNORECASE)`.

### `src/sofia/rel/model.py`

Production/test importers: `src/sofia/rel/__init__.py`, `src/sofia/rel/store.py`, `test/test_rel_habit_matrix.py`.

Imports:

- `from __future__ import annotations`
- `from dataclasses import dataclass`
- `from datetime import datetime`

Definitions:

- `RelationshipContact` (line 8): `src/sofia/rel/store.py:97,100,144,154,165,172,176`; `test/test_rel_habit_matrix.py:151,158,165,172`.
  Data declarations: `principal_id: str`; `audience_id: str`; `evidence_ref: str`; `occurred_at: datetime`; `display_name: str | None = None`.
- `RelationshipContact.__post_init__` (line 15): no external lexical candidates.

### `src/sofia/rel/store.py`

Production/test importers: `src/sofia/application/conversation_service.py`, `src/sofia/rel/__init__.py`.

Imports:

- `from __future__ import annotations`
- `from contextlib import closing`
- `from datetime import datetime`
- `from pathlib import Path`
- `import sqlite3`
- `from sofia.rel.model import RelationshipContact`
- `from sofia.social.model import PrincipalContext`
- `from sofia.state.json_repository import JsonStateRepository`
- `from sofia.state.namespaces import REL_CONTACT_OBSERVATION`
- `from sofia.state.plane import StatePlane, StatePlaneConflictError`

Definitions:

- `RelationshipStore` (line 15): `src/sofia/application/conversation_service.py:126`.
- `RelationshipStore.__init__` (line 18): `src/sofia/application/emotional_conversation.py:96`; `src/sofia/discord/discordpy.py:210`; `src/sofia/distributed/durable.py:49`; `src/sofia/distributed/windows_agent_service.py:32`; `src/sofia/knowledge/persistence.py:13,44`; `src/sofia/ops/durable_lease.py:14`; `src/sofia/ops/persistence.py:59`; `src/sofia/ops/state_registry.py:28`; `src/sofia/run/runtime_service.py:30`; `src/sofia/run/watchdog_service.py:25`; `src/sofia/ui/remote_transport.py:51`; `test/test_ops_agent_discovery.py:464,499`; `test/test_ui_text_client.py:191`.
- `RelationshipStore._history_value` (line 44): no external lexical candidates.
- `RelationshipStore._append_history` (line 59): no external lexical candidates.
- `RelationshipStore.observe` (line 91): `src/sofia/application/conversation_service.py:420`; `src/sofia/body/controller.py:84`; `src/sofia/environment/service.py:48,52,113`; `src/sofia/external/capability.py:235`; `src/sofia/filesystem/change_capability.py:23`; `src/sofia/ops/capability.py:162`; `src/sofia/run/supervisor.py:294`; `src/sofia/runtime/runtime.py:544`; `test/test_environment_home_assistant.py:57,95,126,152,174,197`; `test/test_environment_nws.py:139,194,207,248`; `test/test_external_adapter.py:59,110,138`; `test/test_external_integration_verification.py:149`; `test/test_filesystem_observation.py:30,56`; `test/test_ops_activity_capability.py:178`; `test/test_ops_reconciliation_journal.py:26,27,44,46`; `test/test_ops_workload_store.py:20,32,39`.
- `RelationshipStore.get` (line 144): `src/sofia/action/system.py:85,117,159`; `src/sofia/application/__init__.py:23`; `src/sofia/application/act_service.py:227,251,252,296,299,304,311,324`; `src/sofia/application/background.py:371`; `src/sofia/application/bootstrap.py:88,98`; `src/sofia/application/conversation_matrix.py:312,416`; `src/sofia/application/conversation_service.py:360`; `src/sofia/application/emotional_conversation.py:170`; `src/sofia/application/release_runtime.py:27,31,44`; `src/sofia/avatar/clothing_action.py:490,506,562,579,610`; `src/sofia/avatar/presentation.py:495,497,498,499,502,510,511,524,534,555,649,653,654,655,660,665,669,671,673,674,675`; `src/sofia/avatar/presentation_runtime.py:40,41,42,77,78,79,80`; `src/sofia/avatar/self_fact_query.py:55,81,87,594,619`; `src/sofia/avatar/wardrobe.py:63`; `src/sofia/avatar/wardrobe_matrix.py:71`; `src/sofia/avatar/wardrobe_planner.py:441`; `src/sofia/cognition/conversation_assembler.py:73,76,81,82`; `src/sofia/cognition/model_lifecycle.py:58,66,169,172,190,225,241,345,385,388`; `src/sofia/cognition/performance.py:14`; `src/sofia/cognition/routing.py:426`; `src/sofia/cognition/tools.py:264,300`; `src/sofia/composition/root.py:79,84,245,265`; `src/sofia/composition/authorization.py:179,198`; `src/sofia/config/defaults.py:24,36,49,65,105,109,113,122,126,130,136,179,183,187,228,321`; `src/sofia/config/layout.py:38,50,58,68,78`; `src/sofia/config/state_store.py:64,67`; `src/sofia/config/user_settings.py:355,367,368,371,375,380,385,388,390,409`; `src/sofia/dev/capability.py:60,162,163,190,191,206,256,262`; `src/sofia/dev/release.py:160`; `src/sofia/dev/release_cli.py:84`; `src/sofia/dev/release_store.py:187,191,213`; `src/sofia/dev/workflow.py:91,92`; `src/sofia/discord/binding.py:338,346,353`; `src/sofia/discord/bridge.py:110,123`; `src/sofia/discord/discordpy.py:128,170,290`; `src/sofia/discord/live.py:74,383`; `src/sofia/discord/operator.py:40,79`; `src/sofia/discord/outbound.py:82`; `src/sofia/discord/provisioning.py:32,45,100,105,148`; `src/sofia/distributed/agent.py:257,321`; `src/sofia/distributed/agent_main.py:73,94,96,104,108,111,116,159,160,172,175,178,180`; `src/sofia/distributed/agent_tools.py:92,114,116,117,118,124`; `src/sofia/distributed/authorization.py:58`; `src/sofia/distributed/capability.py:53,78,111,117,120,204,205,206,215`; `src/sofia/distributed/endpoint_policy.py:52`; `src/sofia/distributed/fleet_probe.py:84,85`; `src/sofia/distributed/https_transport.py:90,101,118,170`; `src/sofia/distributed/identity.py:78,82`; `src/sofia/distributed/identity_bound_gateway.py:22`; `src/sofia/distributed/inference_client.py:67,73,88,91,136,143,166,221,250,251,252,261`; `src/sofia/distributed/inference_control.py:215,220`; `src/sofia/distributed/knowledge.py:58,60,77,80`; `src/sofia/distributed/reachability.py:86`; `src/sofia/distributed/windows_agent_service_admin.py:181`; `src/sofia/embodiment/store.py:164,170,181,192,201,202,203,282,297`; `src/sofia/environment/config.py:215,229,244,245,246,247,248,284,288,292,296,326,332,351,362`; `src/sofia/environment/factory.py:47,53,59`; `src/sofia/environment/home_assistant.py:85,96,100,107,111,169,177,182,189,196,197,200,209,213,216,218,222,225,253,257,258,262,263,270,271,274,313,316,317,321,322,323,328,338,351,352`; `src/sofia/environment/nws.py:62,63,142,150,158,161,163,164,170,171,173,177,182,205,212,221,224,246,252,259,263,267,282,287,290,309,317,321,326,332,342`; `src/sofia/environment/service.py:100,116,123`; `src/sofia/evolve/executor.py:189,190,353,425,448,489`; `src/sofia/evolve/revision.py:355,426,447,485`; `src/sofia/evolve/state_plane_adapter.py:156,158`; `src/sofia/external/knowledge.py:123,144,168,186,203,212,276,289`; `src/sofia/filesystem/capability.py:67,86,96,109`; `src/sofia/habits/continuity.py:148,149,167,168,327`; `src/sofia/habits/controls.py:71,100`; `src/sofia/habits/engine.py:121,308,328`; `src/sofia/habits/expectations.py:113,131,141,239`; `src/sofia/habits/pattern_store.py:62,70,80,143,166,200,224`; `src/sofia/habits/store.py:78,82,84,116,141`; `src/sofia/integrate/activation.py:13`; `src/sofia/integrate/governed.py:31`; `src/sofia/integrate/receipts.py:32,34`; `src/sofia/integrate/registry.py:19,25,32`; `src/sofia/integrate/schema.py:13,18,21,22,32`; `src/sofia/integrations/capabilities.py:86,104,108,110,139,140,143,160,175,178,179,180,193,196,207,210,212,217,220,223,226,229,232,236,247,248,249,290,295,305,308,311,317,320,323,332,338`; `src/sofia/integrations/discord.py:14,25`; `src/sofia/integrations/github.py:29`; `src/sofia/interaction/action_grammar.py:80`; `src/sofia/interaction/atomic_offer_release.py:101`; `src/sofia/interaction/body_discussion.py:36`; `src/sofia/interaction/context_hygiene.py:49,50`; `src/sofia/interaction/core.py:129,135,147,172`; `src/sofia/interaction/goal_journal.py:123`; `src/sofia/interaction/grammar.py:80`; `src/sofia/interaction/live_offer_service.py:36`; `src/sofia/interaction/registry.py:283,311,321`; `src/sofia/knowledge/access.py:95`; `src/sofia/knowledge/capability.py:59,67,71,74`; `src/sofia/knowledge/lifecycle.py:25,34,36,47,88,120,123,157,166`; `src/sofia/knowledge/persistence.py:18,21,22`; `src/sofia/knowledge/service.py:39`; `src/sofia/knowledge/store.py:8,13,18,19,21`; `src/sofia/machine/capability.py:60,96,99,134,136`; `src/sofia/machine/discovery.py:307,308`; `src/sofia/machine/inventory.py:35,66,81,102,157,174`; `src/sofia/machine/location.py:147,150,152,176,195`; `src/sofia/machine/location_cli.py:48,79`; `src/sofia/machine/location_state.py:61`; `src/sofia/machine/persistence.py:75,77,99,103,156,158,162,166,170,174,175,176,200,204,208,212,221,225,231,235,298,330,375,378,382,387`; `src/sofia/memory/chatgpt_export.py:42,45,47,55,122,123,131,140,144,156,157,167,171,185,188,193,199,200,203,204,214,227,233,237,238,240,241,242,245,307,311`; `src/sofia/memory/chatgpt_export_store.py:379,401`; `src/sofia/memory/chatgpt_import.py:111,116,148,156,162`; `src/sofia/memory/chatgpt_migration.py:106`; `src/sofia/memory/cognition_projection.py:36`; `src/sofia/memory/promoted_retrieval.py:107`; `src/sofia/memory/promoted_view.py:21,38`; `src/sofia/memory/provenance.py:77,91`; `src/sofia/memory/retrieval_projection.py:85`; `src/sofia/memory/reviewed_workflow.py:43`; `src/sofia/memory/store.py:92`; `src/sofia/memory/system.py:93,234`; `src/sofia/ops/activity.py:59`; `src/sofia/ops/agent_discovery.py:162,164,182,492,493,494`; `src/sofia/ops/capability.py:91,92,93,94,95,96,97,98,114,118,123,125,229,249,250,251`; `src/sofia/ops/desired.py:28`; `src/sofia/ops/discovery.py:191,350`; `src/sofia/ops/discovery_canary.py:70,73,77`; `src/sofia/ops/durable_lease.py:18,19,20`; `src/sofia/ops/failover.py:29`; `src/sofia/ops/fleet.py:26`; `src/sofia/ops/lease.py:20,25,28,33`; `src/sofia/ops/local_telemetry.py:92,93,168,169,170,171`; `src/sofia/ops/machine_bridge.py:16,41`; `src/sofia/ops/persistence.py:66,72,75`; `src/sofia/ops/placement.py:30`; `src/sofia/ops/reconcile.py:230`; `src/sofia/ops/reconciliation_journal.py:192`; `src/sofia/ops/state_registry.py:64,77,80,133`; `src/sofia/ops/telemetry.py:9,10,11,12`; `src/sofia/ops/windows_bootstrap.py:455,456,457`; `src/sofia/ops/windows_rekey_bootstrap.py:42`; `src/sofia/personality/emotion.py:921,925`; `src/sofia/personality/store.py:80`; `src/sofia/run/active_release.py:71,72,98,100,108`; `src/sofia/run/release.py:169,246,250,320,321,348,349,394,395`; `src/sofia/run/service_admin.py:181`; `src/sofia/safe/dev_approve.py:52`; `src/sofia/safe/release_ed25519.py:53`; `src/sofia/state/migration_lease.py:106,122,191`; `src/sofia/system/knowledge.py:195,236,244,265`; `src/sofia/system/linux.py:127,188,189,399,423,424,428,429,572,573,638,680,687,698,793,794,795,863,872,873,874,875`; `src/sofia/system/machine_knowledge.py:93,166`; `src/sofia/system/windows.py:96,154,155,205,221,224,233,236,293,294,295,313,338,341,345,346,350,353,382,383,437,440,443,446,449,460,461,485,494,497,510,520,529,532,535,537,540,557,569,572,585,636,637,638,700,717,730,734,737,811,815,819,823,847,868,869,870,871`; `src/sofia/ui/desktop.py:492,498,539,549,581,601,647,805,884`; `src/sofia/ui/desktop_worker.py:185`; `src/sofia/ui/fleet_service_control.py:39,53,54`; `src/sofia/ui/remote_transport.py:254,427,441,450,479`; `src/sofia/ui/service_control.py:84,173`; `src/sofia/ui/settings_window.py:661,664,668,669,672,675,680,685,688,693,699,702,705,709,713,727,729,733,736,739,742,745,749,753,756,759,762,766,768,770,774,778,781,782,784,787,790,793,797,799,802,804,809,811,813,817,821,825,830,835`; `src/sofia/ui/theme.py:148`; `src/sofia/ui/tray_agent.py:120,163,186,228,233,278,281,619`; `src/sofia/ui/windows_tray.py:550`; `src/sofia/verify/compatibility_matrix.py:326`; `src/sofia/verify/semantic_integrity.py:393,413,455,456`; `src/sofia/voice/factory.py:11,23,31`; `src/sofia/voice/prosody_matrix.py:26`; `src/sofia/voice/tts.py:393`; `src/sofia/cognition/matrix/coordinator.py:72`; `src/sofia/cognition/matrix/evidence.py:201`; `src/sofia/cognition/matrix/expression_plan.py:198,204,297,429,436,468,473`; `src/sofia/cognition/matrix/trace.py:318,333,339,345,348,351,354,355,356,374,378,383,400,409,416,424,425,428,431,434`; `src/sofia/verify/interaction/avatar_world_probe.py:64,65,66,67`; `src/sofia/verify/interaction/focused_probe.py:79,80,81,84,85,86`; `test/conftest.py:115`; `test/test_application.py:298,299`; `test/test_chatgpt_memory_import.py:119`; `test/test_cognition_matrix.py:364,556,942`; `test/test_cognitive_activity.py:32,38,47,72,121,122`; `test/test_conversation_service.py:1122,1273`; `test/test_discord_binding.py:25`; `test/test_discord_bridge.py:178`; `test/test_discord_durable_inbox.py:39,85`; `test/test_discord_live.py:85,314`; `test/test_discord_recovery.py:63`; `test/test_distributed_identity.py:40,54,55,95`; `test/test_distributed_identity_durable.py:26,36`; `test/test_distributed_pki.py:21`; `test/test_distributed_retirement.py:18`; `test/test_distributed_windows_agent_service.py:47`; `test/test_embodiment_prompt_regression.py:399,405,417`; `test/test_habit_contextual_matrix.py:60,61,67,68,73,74,79,80`; `test/test_habit_foundation.py:236`; `test/test_know_integrate_waves3_5_acceptance.py:63`; `test/test_machine_inventory_contract.py:217,239,256`; `test/test_machine_inventory_lifecycle.py:161,189,229,252,313,342,367,406,500,503,539,594`; `test/test_machine_inventory_persistence.py:198,199,220,273,278,305,306,346,364`; `test/test_machine_inventory_refresh.py:116,168,224,253,286,314`; `test/test_machine_location.py:49,82,83`; `test/test_machine_location_cli.py:63`; `test/test_machine_location_inventory.py:72`; `test/test_machine_regression.py:121,150,170,192,223`; `test/test_memory.py:57,65,89,90,112,128,167`; `test/test_memory_promoted_view.py:22,24,33,44,55,56`; `test/test_memory_provenance_store.py:30,75`; `test/test_memory_reviewed_workflow.py:36`; `test/test_ops_maintenance_reconcile.py:113,129,140,150,167`; `test/test_ops_reconciliation_journal.py:53`; `test/test_ops_windows_rekey_bootstrap.py:31,133,134`; `test/test_run_service_admin.py:48`; `test/test_safe_secret_store.py:28,41,53`; `test/test_system_capability_integration.py:93,246,279,287,440,445,501,524,546`; `test/test_system_capability_integration_hardening.py:395,396,398,596,610,678`; `test/test_system_machine_knowledge_integration.py:179,184,218,223,375`; `test/test_thought_agent_live_ollama.py:24`; `test/test_ui_desktop_worker.py:68,75,80,86,91,106,160,167,172,180`; `test/test_ui_windows_tray.py:44`; `test/test_waves3_5_cross_package_acceptance.py:70`; `test/interaction_lab_support.py:140`.
- `RelationshipStore.history` (line 162): `src/sofia/act/delivery.py:494,508`; `src/sofia/act/outreach.py:224,242,257,258,265,266,272,273,276,278,281,283,298,299,311`; `src/sofia/act/system_notice.py:418,428`; `src/sofia/application/conversation_matrix.py:241,243,257,261,324,326,335,336`; `src/sofia/application/conversation_service.py:523,529`; `src/sofia/dev/release_store.py:98,109,121`; `src/sofia/machine/persistence.py:386,404`; `src/sofia/ops/capability.py:41,77`; `src/sofia/ui/desktop.py:574,577,594,597`; `src/sofia/ui/desktop_controller.py:66,139,209,263,266`; `src/sofia/ui/desktop_worker.py:114,161,197,207`; `test/test_act_delivery.py:172,178,179`; `test/test_act_outreach.py:181,188,206,215`; `test/test_cognition_matrix.py:129,498`; `test/test_conversation_service.py:524,529,530,563,568,571,581,602,605,698,723,913,914,969,970,1031,1032,1033,1067,1120`; `test/test_external_knowledge.py:116,145,165,211,356,377`; `test/test_interaction_clarify_quality_regression.py:48,50,56`; `test/test_machine_inventory_contract.py:218,238,257`; `test/test_machine_inventory_lifecycle.py:166,168,195,254,256,257,260,318,320,321,347,351,352,376,410,414,415,549`; `test/test_machine_inventory_persistence.py:203,204,310,311,347`; `test/test_machine_inventory_refresh.py:120,173,175,176,177,290,292,293,294,313`; `test/test_machine_regression.py:171,175,176,177,193,200,229,231,232`; `test/test_ollama_repetition_guard.py:113,117`; `test/test_ops_sqlite_telemetry.py:23,24,38,43`; `test/test_ops_waves3_5_acceptance.py:74,76,77`; `test/test_run_periodic_thought.py:42,75,153,178,188`; `test/test_system_capability_integration_hardening.py:576,586`; `test/test_system_machine_knowledge_integration.py:357,372`; `test/test_ui_application.py:66,67,71,73`; `test/test_ui_desktop_application.py:64,65,67,70`; `test/test_ui_desktop_controller.py:77,84,191`; `test/test_ui_desktop_worker.py:70,71,93,94,95,98,162,163`; `test/test_ui_text_client.py:80,82,83,84,85,86,87,99,115`.
