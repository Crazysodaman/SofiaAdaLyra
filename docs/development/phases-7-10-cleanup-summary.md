# Phases 7–10 cleanup completion

Final verified source checkpoint: `2d82152d74bdc39d57f6517cb4e5ad4403f712b5`. Documentation-only completion checkpoint follows it; final main merge can be identified with `git log --first-parent --format="%H %s" -5 main`.

Completed all 25 requested folders in dependency order on `work`, with folder checkpoints pushed. Related imports, exports, fixtures and documentation were repaired across owning packages. Final merge into main is authorized by the user.

The Phase 6 merge was completed and pushed at `db50ec27`; main was pulled. The initial wardrobe re-audit was checkpointed at `6d2a5867`. A later fetch found 13 further wardrobe commits through `ec2b646a`; they were merged into work at `e647f3a1`, with resolved canonical type/prebuild ownership and a separate JSON decoder. See [latest wardrobe merge report](avatar-latest-wardrobe-merge-report.md) for each resource and reproduced/fixed incoming defects.

Compile and pip dependency checks passed. Final full-suite result: 3224 passed, 5 unavailable-Ollama failures, 2 existing skips (73.66s). No tests were skipped or weakened to conceal unavailable Ollama. Existing two skips remain distinct from failures. Five local Ollama failures are listed below; the Windows storage fixture and filesystem outside-scope fixture were repaired while retaining their policy assertions. No live Windows service, desktop renderer, Discord account or remote deployment was claimed.

| Phase | Folder | Checkpoint(s) | Targeted gate |
| --- | --- | --- | --- |
| 7 | [ui](ui-cleanup-report.md) | `1b97accb` | 353 passed |
| 7 | [voice](voice-cleanup-report.md) | `d3f5c409` | 148 passed |
| 7 | [discord](discord-cleanup-report.md) | `bd0812f6` | 240 passed; shared lock follow-up 5 passed |
| 8 | [run](run-cleanup-report.md) | `ea358c52; e448ac20` | 237 passed; final sweep 154 passed |
| 8 | [ops](ops-cleanup-report.md) | `dd3bddfb` | 274 passed |
| 8 | [verify](verify-cleanup-report.md) | `4020f754` | 132 passed |
| 8 | [safe](safe-cleanup-report.md) | `b755190e; 2d82152d` | 194 passed, 1 skipped; final sweep 171 passed, 1 skipped |
| 8 | [authority](authority-cleanup-report.md) | `b26f2450` | 154 passed |
| 8 | [authorization](authorization-cleanup-report.md) | `6921ec4d` | 49 passed |
| 8 | [capability](capability-cleanup-report.md) | `cda9aa76` | 123 passed |
| 8 | [action](action-cleanup-report.md) | `1658f95a` | 98 passed |
| 8 | [act](act-cleanup-report.md) | `d06d00ff` | 253 passed |
| 9 | [distributed](distributed-cleanup-report.md) | `ae5266ee; d268ed61` | 338 passed; durable-owner sweep 302 passed |
| 9 | [integrations](integrations-cleanup-report.md) | `074ab66a` | 52 passed |
| 9 | [net](net-cleanup-report.md) | `3f308dfd` | 137 passed |
| 9 | [external](external-cleanup-report.md) | `c3bce69c` | 123 passed |
| 9 | [filesystem](filesystem-cleanup-report.md) | `1c23724f` | 148 passed |
| 10 | [config](config-cleanup-report.md) | `0ad19356` | 97 passed |
| 10 | [constitution](constitution-cleanup-report.md) | `0351827b` | 228 passed |
| 10 | [evolve](evolve-cleanup-report.md) | `1a14f04a` | 88 passed, 1 skipped |
| 10 | [integrate](integrate-cleanup-report.md) | `0a82bd81` | 405 passed |
| 10 | [dev](dev-cleanup-report.md) | `71161488` | 175 passed, 1 skipped; exports follow-up 7 passed |
| 10 | [codebase](codebase-cleanup-report.md) | `38009853` | 253 passed; ownership follow-up 2 passed |
| 10 | [clean](clean-cleanup-report.md) | `8a1fbe94` | 111 passed |
| 10 | [operational](operational-cleanup-report.md) | `71bec0a1` | 250 passed |

Each report contains original file contents, every class/function/method and constant inventory, incoming/outgoing imports, candidate callers/tests, concrete production paths, canonical state ownership, changes and remaining limits. Lexical reference inventories are candidly labeled; framework callbacks, local helpers and operator CLI entry points were inspected rather than declared dead from text search alone. Tests exclusive to retired prototypes were removed; mixed knowledge, authority, Fleet and runtime assertions were retained against live owners.

Remaining service-dependent checks:

- `test_embodiment_prompt_regression.py::test_embodiment_prompt_regression_variants`
- `test_embodiment_prompt_regression.py::test_embodiment_repeated_generation_determinism_probe`
- `test_ollama_integration.py::test_real_ollama_cognitive_path`
- `test_ollama_integration.py::test_real_ollama_receives_sofia_identity_context`
- `test_ollama_integration.py::test_real_ollama_receives_sofia_instance_identity`

Final dependency sweep retired the remaining in-memory remote grant implementation (tests now use the durable production owner), uncalled RUN heartbeat/release helpers and unused SAFE/filesystem exceptions. The only single-text-reference methods retained in audited Python source are framework-dispatched Discord/HTTP handlers and Python callable/string hooks. No retired import/name remains in production source, tests or tools. Historical inventories document pre-cleanup definitions; they are not current import instructions. Protected identity and constitution assets and all seven incoming wardrobe JSON files are byte-for-byte unchanged.

New canonical files introduced by these phases:

| File | Decision | Responsibility |
| --- | --- | --- |
| `run/process_lock.py` | MERGE | One shared process lock implementation; UI and Discord preserve their owner-specific wrappers and error/path contracts. |
| `act/history.py` | MERGE | One delivery-history projection shared by both live queues, using the caller transaction. |
| `avatar/wardrobe_types.py` | SPLIT | Canonical type catalog with incoming main type expansion preserved. |
| `avatar/wardrobe_prebuild.py` | SPLIT | Validated blueprint/prebuild metadata and creator handoff, including incoming content fields. |
| `avatar/wardrobe_loader.py` | SPLIT | Packaged JSON schema and typed profile decoder; catalog supplies canonical blueprint construction. |
| `codebase/capability.py` | RENAME | Canonical read-only structural capability adapter, formerly codebase.py. |
| `test/action_support.py` | MOVE | Test-only action executor removed from production package. |
| `test/distributed_support.py` | KEEP | Test fixture uses and closes the real durable remote authorization owner. |

Per-file decisions below reproduce the final folder report tables. New files are listed above; seven new wardrobe resources and incoming main files appear in the wardrobe follow-up table.

## Phase 7

| File | Decision | Evidence / reason |
| --- | --- | --- |
| `ui/__init__.py` | KEEP | PKG-UI text-first and workbench primitives. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ui/__main__.py` | KEEP | Launch the local PKG-UI desktop workbench. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ui/assets/sofia_fox.ico` | KEEP | Native Windows tray icon resource loaded by windows_tray; packaged through setuptools asset configuration. |
| `ui/control_center.py` | KEEP | Tray/master-settings control contracts for the Sofía desktop client. Imported by `ui/desktop_application.py`, `ui/fleet_service_control.py`, `ui/remote_client.py`, `ui/service_control.py`, `ui/settings_window.py`, `ui/tray_agent.py`, `ui/windows_tray.py`. |
| `ui/delivery.py` | DELETE | Caller-reported renderer acknowledgments have no runtime, desktop, voice or avatar consumer; only package exports and own tests. |
| `ui/desktop.py` | KEEP | Low-resource Windows desktop shell for Sofía. Imported by `__main__.py`, `ui/__main__.py`. |
| `ui/desktop_application.py` | KEEP | Canonical desktop application composition. Imported by `ui/desktop_worker.py`. |
| `ui/desktop_controller.py` | KEEP | Application-facing controller for the Windows text workbench. Imported by `ui/desktop_worker.py`. |
| `ui/desktop_worker.py` | KEEP | Single-owner worker thread for the desktop Sofía client. Imported by `ui/desktop.py`. |
| `ui/drafts.py` | KEEP | Persistent unsent draft state for PKG-UI text clients. Imported by `application/bootstrap.py`, `ui/text.py`. |
| `ui/fleet_service_control.py` | DELETE | Unconstructed bridge has no callers or tests; live tray local controls still fail closed on remote requests. |
| `ui/process_lock.py` | KEEP | Cross-platform lifetime lock for one Sofía tray agent per state database. Imported by `ui/tray_agent.py`, `ui/tray_launcher.py`. |
| `ui/quick_tools.py` | KEEP | Curated desktop quick-tool prompts. Imported by `ui/desktop.py`. |
| `ui/remote_client.py` | DELETE | Explicitly deferred endpoint selector has no production caller; desktop already normalizes old remote settings to local mode. |
| `ui/remote_transport.py` | DELETE | Deferred remote chat server/client and its independent request ledger are unwired. Preserve actual Fleet mTLS and Discord transport in their owners. |
| `ui/runtime_authority.py` | DELETE | No publisher or consumer exists for this competing runtime-chat authority record. |
| `ui/service_control.py` | KEEP | Typed service/model controls used by the tray client. Imported by `ui/fleet_service_control.py`, `ui/tray_agent.py`. |
| `ui/settings_window.py` | KEEP | Tkinter master settings window for the Sofía desktop/tray client. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ui/terminal.py` | KEEP | Tracked asset. Imported by `__main__.py`. |
| `ui/text.py` | KEEP | Text-first PKG-UI adapter over Sofía's canonical conversation service. Imported by `application/bootstrap.py`, `ui/desktop_controller.py`. |
| `ui/theme.py` | KEEP | Bounded adaptive desktop theming from trusted Sofía state. Imported by `ui/desktop.py`, `ui/desktop_controller.py`, `ui/desktop_worker.py`. |
| `ui/tray_agent.py` | KEEP | Standalone Windows tray control process for Sofía. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ui/tray_launcher.py` | KEEP | Production launcher for the singleton Windows tray agent. Imported by `__main__.py`. |
| `ui/windows_startup.py` | KEEP | Settings window invokes registration; tray startup command builds package bootstrap. Test now simulates python.exe explicitly and separately verifies pythonw preference. |
| `ui/windows_tray.py` | KEEP | Native Windows notification-area renderer for Sofía. Imported by `ui/tray_agent.py`. |
| `ui/workbench.py` | DELETE | Headless page/notebook/binder store is never constructed by the desktop controller; only exported and tested. Desktop chat uses canonical text UI and drafts. |
| `voice/__init__.py` | KEEP, repair exports | Expose live TTS/prosody/evaluator APIs; remove retired readiness names. |
| `voice/__main__.py` | KEEP | Explicit python -m sofia.voice operator playback/probe entry point; no listener is started on import. |
| `voice/factory.py` | KEEP | Production TTS composition from environment configuration. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `voice/matrix.py` | KEEP | VOICE contribution to the message matrix. Imported by `cognition/matrix/defaults.py`. |
| `voice/model.py` | MERGE + DELETE | Move live VoiceUrgency and VoiceProsodyProfile into prosody_matrix.py; retire unused input-mode/runtime readiness contracts. |
| `voice/prosody_matrix.py` | MERGE | Canonical bounded prosody types and planner now share one cohesive module consumed by application/TTS/SAPI. |
| `voice/runtime_matrix.py` | DELETE | VoiceRuntimeMatrix has no production caller; listening/STT readiness exists only in its own tests and exports. |
| `voice/sapi.py` | KEEP | Windows SAPI text-to-speech backend. Imported by `voice/__main__.py`, `voice/factory.py`. |
| `voice/tts.py` | KEEP | Asynchronous text-to-speech service and engine-neutral contracts. Imported by `application/conversation_matrix.py`, `voice/factory.py`, `voice/sapi.py`. |
| `discord/__init__.py` | KEEP | Discord channel boundaries. Importing this package starts no live client. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `discord/__main__.py` | KEEP | Explicit Discord process and local operator entry point. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `discord/access.py` | KEEP | Fail-closed inbound Discord DM policy for the initial single-user rollout. Imported by `discord/binding.py`, `discord/delivery.py`, `discord/discordpy.py`, `discord/inbound.py`, `discord/ingress.py`, `discord/outbound.py`, `discord/provisioning.py`. |
| `discord/binding.py` | KEEP | Canonical durable owner/channel/session bindings and revocation consumed before ingress/outbound work. |
| `discord/bridge.py` | KEEP | Offline bridge from durable Discord inbox rows to Sofía conversation output. Imported by `discord/discordpy.py`, `discord/live.py`. |
| `discord/delivery.py` | KEEP | Actual bounded message splitting, receipt storage and authenticated outbound sender; no synthetic renderer acknowledgment model. |
| `discord/discordpy.py` | KEEP | Thin discord.py 2.7.1 adapter behind Sofía's transport-neutral gates. Imported by `discord/live.py`. |
| `discord/inbound.py` | KEEP | Offline Discord DM ingress screening. Imported by `discord/discordpy.py`, `discord/ingress.py`, `discord/store.py`. |
| `discord/ingress.py` | KEEP | Trusted-adapter ingress boundary for owner Discord DMs. Imported by `discord/discordpy.py`, `discord/live.py`. |
| `discord/live.py` | KEEP | Production composition for Sofía's live Discord DM channel. Imported by `discord/__main__.py`, `ui/desktop_worker.py`. |
| `discord/operator.py` | KEEP | Host-side controls for the supervised single-owner Discord channel. Imported by `discord/__main__.py`. |
| `discord/outbound.py` | KEEP | Final offline authorization gate for a future Discord send adapter. Imported by `discord/delivery.py`, `discord/discordpy.py`, `discord/live.py`. |
| `discord/process_lock.py` | MERGE + MOVE | Merge duplicated OS lifetime-lock mechanics into run/process_lock.py; retain Discord resource path and error message specialization. The shared process registry closes Windows same-process byte-range reentry. |
| `discord/provisioning.py` | KEEP | Explicit environment provisioning for the single-owner Discord transport. Imported by `discord/live.py`, `discord/operator.py`, `integrations/capabilities.py`, `integrations/discord.py`, `ui/desktop_worker.py`. |
| `discord/store.py` | KEEP | Canonical SQLite inbound claim/outbox state used by ingress/bridge/live restart recovery; distinct from actual delivery receipts. |

## Phase 8

| File | Decision | Evidence / reason |
| --- | --- | --- |
| `run/__init__.py` | KEEP | PKG-RUN: local lifecycle, singleton fencing, and bounded background opportunities. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `run/active_release.py` | KEEP | Resolve and prepare the release selected by authoritative Sofía state. Imported by `run/release_process.py`, `run/runtime_service.py`. |
| `run/heartbeat.py` | KEEP | Production runtime records ready/lifecycle heartbeats; supervisor consumes current evidence. Removed uncalled is_fresh_ready; actual supervisor freshness logic remains canonical. |
| `run/host.py` | KEEP | Tracked asset. Imported by `run/watchdog_service.py`. |
| `run/lease.py` | KEEP | LocalRunLeaseStore is the production SQLite local-runtime fence owner; not distributed consensus or the retired OPS lease prototype. |
| `run/periodic.py` | KEEP | Durable, opt-in periodic opportunities while Sofía is actually running. Imported by `application/background.py`. |
| `run/process_lock.py` | KEEP | Shared OS process lock now called by both live tray and Discord policies; preserves channel resource identity. |
| `run/release.py` | KEEP | Live release compatibility/activation/rollback and callable supervisor recovery hook. Removed uncalled candidate_path; actual validated candidate staging remains. |
| `run/release_process.py` | KEEP | Stable host process controller for an active Sofía release. Imported by `run/runtime_service.py`. |
| `run/runtime_child.py` | KEEP | ReleaseChildProcess launches python -m sofia.run.runtime_child; lack of a Python import is not dead code. |
| `run/runtime_service.py` | KEEP | Windows service class loaded through service_admin's configured class string; starts verified release child process. |
| `run/service_admin.py` | KEEP | Install, update, validate and remove PKG-RUN Windows services. Imported by `run/windows_acceptance.py`. |
| `run/supervisor.py` | KEEP | Host-neutral local runtime supervisor with bounded restart/backoff. Imported by `run/host.py`. |
| `run/watchdog_service.py` | KEEP | Windows watchdog service class delegates to RunSupervisorHost; loaded through service packaging. |
| `run/windows_acceptance.py` | KEEP | Explicit python -m operator readiness/SCM acceptance tool; distinct from the runtime host. |
| `run/windows_service_spec.py` | KEEP | Typed Windows service identities for PKG-RUN. Imported by `run/runtime_service.py`, `run/service_admin.py`, `run/watchdog_service.py`, `run/windows_acceptance.py`. |
| `ops/__init__.py` | KEEP | PKG-OPS fleet telemetry, lifecycle, orchestration and failover primitives. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ops/activity.py` | KEEP | Host foreground-activity evidence and durable operator overrides. Imported by `application/background_runtime.py`, `ops/capability.py`, `ops/placement.py`, `ui/settings_window.py`, `ui/tray_agent.py`. |
| `ops/agent_discovery.py` | KEEP | mTLS Fleet-agent discovery against explicitly approved candidate endpoints. Imported by `application/bootstrap.py`, `ops/discovery_canary.py`. |
| `ops/approval.py` | MERGE | Exact Fleet removal approval lives with FleetRegistry, its only authority consumer; state_registry imports that canonical type. |
| `ops/backup.py` | KEEP | Encrypted backup/restore engine for canonical Sofía production state. Imported by `ops/backup_cli.py`. |
| `ops/backup_cli.py` | KEEP | Operator CLI for encrypted Sofía backup, verification and restore rehearsal. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ops/bootstrap.py` | KEEP | Bounded Fleet agent bootstrap planning and execution. Imported by `application/fleet_runtime.py`, `ops/discovery.py`, `ops/windows_bootstrap.py`, `ops/windows_rekey_bootstrap.py`. |
| `ops/capability.py` | KEEP | Read-only cognitive surface for OPS fleet state, telemetry and planning. Imported by `application/fleet_runtime.py`, `cognition/fleet_engine.py`, `composition/engines.py`, `composition/root.py`, `runtime/runtime.py`, `ui/tray_agent.py`. |
| `ops/desired.py` | KEEP | Desired-state and drift reporting for fleet reconciliation. Imported by `ops/capability.py`, `ops/desired_store.py`, `ops/repair_plan.py`. |
| `ops/desired_store.py` | KEEP | Durable desired Fleet state for reconciliation. Imported by `ops/capability.py`. |
| `ops/discovery.py` | KEEP | Bounded Fleet discovery evidence and candidate registration. Imported by `application/background_runtime.py`, `application/fleet_runtime.py`, `ops/agent_discovery.py`, `ops/discovery_canary.py`. |
| `ops/discovery_canary.py` | KEEP | Read-only supervised mTLS discovery canary for one approved Fleet target. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ops/durable_lease.py` | DELETE | JSON lease writer is used only by acceptance fossils, not composed production fencing. |
| `ops/enrollment.py` | KEEP | Authenticated-evidence bridge from NET enrollment into OPS fleet trust. Imported by `ops/capability.py`, `ops/discovery.py`. |
| `ops/failover.py` | DELETE | Synthetic promotion guard/coordinator have no runtime caller; no production cross-host consensus claim is preserved. |
| `ops/failure_matrix.py` | DELETE | Synthetic recovery disposition matrix has no registered or operator consumer and duplicates host/workload states; only own tests and exports. |
| `ops/fleet.py` | KEEP | Tracked asset. Imported by `ops/desired.py`, `ops/discovery_canary.py`, `ops/enrollment.py`, `ops/failover.py`, `ops/maintenance.py`, `ops/persistence.py`, `ops/state_registry.py`. |
| `ops/history.py` | KEEP, delete old writer | SQLiteTelemetryHistory is the sole durable history owner; old JSONL is parsed only by its verified migration. |
| `ops/lease.py` | DELETE | In-memory workload fence prototype has no production consumer; live local runtime lease owner is RUN. |
| `ops/local_telemetry.py` | KEEP | Local normalized telemetry collection for Fleet agents. Imported by `distributed/agent_tools.py`. |
| `ops/machine_bridge.py` | DELETE | Unused observation/telemetry bridge is replaced by production authenticated discovery and local agent telemetry. |
| `ops/maintenance.py` | KEEP | Typed fleet maintenance requests. No arbitrary shell or argv surface exists here. Imported by `ops/reconcile.py`, `ops/remote.py`. |
| `ops/matrix.py` | KEEP | OPS contribution to the message matrix. Imported by `cognition/matrix/defaults.py`. |
| `ops/migration.py` | MERGE + DELETE | Live read-only MigrationPlan/Stage move into workload.py; test-only MigrationCoordinator.advance execution-state prototype is retired. |
| `ops/model.py` | KEEP, delete duplicate enum | Live host/telemetry/workload contracts remain; unused WorkloadState duplicated WorkloadPhase without a consumer. |
| `ops/orchestrator.py` | DELETE | Test-backend migration executor is never composed; live migration capability returns a read-only plan. |
| `ops/persistence.py` | DELETE | Retire JsonFleetRegistry writer and SMB replace helper; migration decodes old JSON directly into canonical host models. |
| `ops/placement.py` | KEEP | Tracked asset. Imported by `ops/capability.py`. |
| `ops/reconcile.py` | KEEP | Durable, verified Fleet maintenance reconciliation. Imported by `ops/capability.py`. |
| `ops/reconciliation_journal.py` | KEEP | Durable dedupe journal for Fleet reconciliation observations. Imported by `application/fleet_runtime.py`, `ops/capability.py`. |
| `ops/recovery.py` | KEEP, delete prototype classes | Keep production backup evidence/objectives/recovery guard; unused UpdatePlanner/UpdateRing/HostUpdateAssignment have no CLI/runtime caller. |
| `ops/remote.py` | DELETE | Maintenance-to-remote-operation adapter has no production caller; typed distributed remote control remains live. |
| `ops/repair_plan.py` | KEEP | Conservative repair proposals from reviewed Fleet drift. Imported by `ops/capability.py`, `ops/reconciliation_journal.py`. |
| `ops/state_registry.py` | KEEP, repair migration | Canonical Fleet host owner resumes partial imports, preserves later canonical rows, detects conflicting partial imports, verifies and retires legacy input. |
| `ops/telemetry.py` | DELETE | Snapshot normalizer has no production caller; local telemetry/discovery supply real observations. |
| `ops/windows_bootstrap.py` | KEEP | Operator-approved Windows Fleet bootstrap for one explicitly named host. Imported by `ops/windows_rekey_bootstrap.py`. |
| `ops/windows_rekey_bootstrap.py` | KEEP | Strict-X.509 Windows Fleet rekey/bootstrap canary. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `ops/workload.py` | MERGE | Cohesive workload instance/placement/migration-plan value contracts; no synthetic execution coordinator remains. |
| `ops/workload_store.py` | KEEP | Durable observed Fleet workload-instance state. Imported by `ops/capability.py`. |
| `verify/__init__.py` | KEEP, repair exports | Inert package marker; remove dead ReleaseEvidence export. |
| `verify/compatibility_matrix.py` | DELETE | ReleaseCompatibilityMatrix is exercised only by its own tests; production ReleaseManager compatibility and SAFE activation do not call it. |
| `verify/dual_cognition.py` | KEEP | Explicit canary exercises composed role/model paths without normal conversation messages. |
| `verify/gate.py` | KEEP | Explicit python -m gate runs subprocess checks, captures status/revision/duration and reports actual evidence. |
| `verify/interaction/__init__.py` | KEEP | Explicit interaction verification commands and disposable model probes. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/ab_probe.py` | KEEP | Supervised, synthetic A/B probe; does not open or modify Sofía's SQLite state. Imported by `verify/interaction/architecture_compare.py`, `verify/interaction/boundary_counterfactual_probe.py`, `verify/interaction/decision_expression_probe.py`, `verify/interaction/focused_probe.py`, `verify/interaction/route_boundary_probe.py`. |
| `verify/interaction/architecture_compare.py` | KEEP | State-free, choice-only A/B experiment for one reviewed avatar hug offer. Imported by `verify/interaction/boundary_counterfactual_probe.py`, `verify/interaction/route_boundary_probe.py`. |
| `verify/interaction/avatar_world_probe.py` | KEEP | Review avatar-world conversation with Ollama in disposable application state. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/boundary_counterfactual_probe.py` | KEEP | State-free paired counterfactual for ONE exact reviewed avatar hug offer. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/decision_expression_probe.py` | KEEP | Diagnostic ONLY: two-stage synthetic interaction experiment with Ollama. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/disposable.py` | KEEP | Application-owned cleanup for disposable interaction probes. Imported by `verify/interaction/disposable_live_offer_probe.py`, `verify/interaction/live_behavior_probe.py`. |
| `verify/interaction/disposable_live_offer_probe.py` | KEEP | Supervised real-model offer probe using a TEMPORARY application database only. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/focused_probe.py` | KEEP | Synthetic, state-free probe of per-turn action instruction verbosity. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/live_behavior_probe.py` | KEEP | Supervised real-model probe for PKG-INTERACT conversational behavior. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `verify/interaction/prototype.py` | KEEP | Synthetic experiment fixture used only by explicit interaction verification probes; intentionally outside production INTERACT. |
| `verify/interaction/route_boundary_probe.py` | KEEP | State-free challenge cases for the avatar-social decision route. Imported by `verify/interaction/boundary_counterfactual_probe.py`. |
| `verify/reflection_audit.py` | KEEP | Explicit read-only content-free audit tool; no writes or model replies treated as evidence. |
| `verify/release.py` | DELETE | ReleaseEvidence is only re-exported; no caller constructs or consumes it. Canonical release/SAFE verification computes its own evidence. |
| `verify/semantic.py` | KEEP | Explicit CLI invokes SemanticIntegrityVerifier against configured canonical state. |
| `verify/semantic_integrity.py` | KEEP | Tracked asset. Imported by `verify/semantic.py`. |
| `safe/__init__.py` | KEEP | PKG-SAFE public surface. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `safe/approve_execution.py` | KEEP | Explicit operator CLI entry point. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `safe/audit.py` | KEEP | Production hash-chained audit owner used by application/release runtime, RUN and SAFE. Removed AuditChainError, which was never raised, caught, imported or tested. |
| `safe/capability_policy.py` | KEEP | Defines normalize_capabilities, protected_capability_extras, set_protected_capability_extras. Imported by `composition/root.py`, `safe/capability_policy_cli.py`. |
| `safe/capability_policy_cli.py` | KEEP | Explicit operator CLI entry point. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `safe/dev_approval.py` | KEEP | Defines DevApprovalVerifier. Imported by `composition/root.py`, `dev/capability.py`, `safe/dev_approve.py`. |
| `safe/dev_approve.py` | KEEP | Explicit operator CLI entry point. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `safe/evolve_approval.py` | KEEP | Defines DurableEvolutionApprovalVerifier. Imported by `application/evolution.py`, `safe/evolve_approve.py`. |
| `safe/evolve_approve.py` | KEEP | Explicit operator CLI entry point. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `safe/execution_approval.py` | KEEP | Defines execution_fingerprint, ExecutionApproval, ExecutionApprovalVerifier. Imported by `composition/root.py`, `integrations/capabilities.py`, `knowledge/capability.py`, `safe/approve_execution.py`, `ui/service_control.py`, `ui/tray_agent.py`. |
| `safe/operator_stop.py` | KEEP | Defines OperatorStopState, OperatorStopStore. Imported by `avatar/clothing_action.py`, `avatar/private_grant.py`, `composition/authorization.py`, `composition/root.py`, `distributed/capability.py`, `distributed/inference_client.py`, `safe/operator_stop_cli.py`, `ui/tray_agent.py`. |
| `safe/operator_stop_cli.py` | KEEP | Explicit operator CLI entry point. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `safe/release.py` | KEEP | Defines ReleaseVerificationError, ReleaseSignatureVerifier, ReleaseActivationEvidence, ReleaseActivationGuard. Imported by `application/release_runtime.py`, `dev/release_store.py`, `run/release.py`, `safe/release_ed25519.py`. |
| `safe/release_ed25519.py` | KEEP | Defines Ed25519ReleaseSignatureVerifier. Imported by `application/release_runtime.py`. |
| `safe/secret_store.py` | KEEP | Defines SecretStoreUnavailable, _DATA_BLOB, _protect_windows, _unprotect_windows, ProtectedSecretStore. Imported by `discord/provisioning.py`, `environment/factory.py`, `ui/settings_window.py`. |
| `authority/__init__.py` | KEEP | Exports the canonical model/evaluator without another state owner. |
| `authority/matrix.py` | KEEP | Default matrix registry invokes the Authority evaluator before routing. |
| `authority/model.py` | KEEP | Authority used by runtime/operation/tool filtering; can_use_capability is a live exposure check, not execution permission. |
| `authorization/__init__.py` | KEEP | Exports the canonical grant/evaluator contracts; no alternate mutable authority store. |
| `authorization/evaluator.py` | KEEP | Live local-principal/channel evaluator rejects untrusted, remote or mismatched audience evidence before grant creation. |
| `authorization/model.py` | KEEP | Typed scope/domain/operation/decision grant consumed by conversation, composition and runtime. |
| `capability/__init__.py` | KEEP, repair exports | Public proposal export now targets canonical model; no shim module remains. |
| `capability/catalog.py` | KEEP | Production tool catalog registration exposes configured capabilities and bindings. |
| `capability/gateway.py` | KEEP | Resolves canonical registration and builds request; execution authorization stays in CapabilitySystem. |
| `capability/model.py` | MERGE | Canonical capability value vocabulary, including proposal with no authorization powers. |
| `capability/proposal.py` | MERGE | CapabilityProposal moves into model.py beside request/result contracts; exact definition AST preserved, old module retired. |
| `capability/system.py` | KEEP | Live registry/authorizer/handler execution boundary used throughout composition and cognition. |
| `action/__init__.py` | KEEP, repair exports | Remove synthetic executor from production exports; live types/execution boundary remain. |
| `action/executor.py` | MOVE + KEEP | Move TestActionExecutor to test/action_support.py; preserve abstract boundary and live FailClosedActionExecutor. |
| `action/model.py` | KEEP | Canonical action/proposal/result types consumed by cognition, system and executor. |
| `action/system.py` | KEEP, delete uncalled validator | Production propose/approve/execute and single-use ownership remain; validate_self_improvement_proposal was called only by three own tests, while governed self-changes use DEV/EVOLVE. |
| `act/__init__.py` | KEEP | Exports actual outreach/queue contracts; no duplicate mutable state model. |
| `act/delivery.py` | SPLIT + MERGE | Keep canonical conversation-bound outbox and delivery runner; duplicated history/quota read projection moves into history.py. |
| `act/outreach.py` | KEEP | Canonical immutable eligibility/history/policy vocabulary and evaluate function consumed by both live queues. |
| `act/system_notice.py` | MERGE + KEEP | Use the same delivery_history projection as outbox rather than maintaining an independent cross-queue quota calculation; keep operational queue and receipts. |

## Phase 9

| File | Decision | Evidence / reason |
| --- | --- | --- |
| `distributed/__init__.py` | KEEP | Distributed-node evidence contracts; no network operations or authority. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `distributed/agent.py` | KEEP | Pinned mutual-TLS remote fleet agent with typed operations only. Imported by `distributed/agent_main.py`, `distributed/agent_tools.py`, `distributed/windows_agent_service.py`. |
| `distributed/agent_main.py` | KEEP | Explicit foreground entry point for Sofía's pinned mTLS fleet agent. Imported by `distributed/windows_agent_service.py`, `distributed/windows_agent_service_admin.py`. |
| `distributed/agent_tools.py` | KEEP | Default typed operations exposed by the fleet agent. Imported by `distributed/agent_main.py`. |
| `distributed/authorization.py` | KEEP | Immutable RemoteGrant and abstract RemoteAuthorization are consumed by live gateway/durable admission. Retired the test-only in-memory grant implementation; security tests now use DurableRemoteAuthorization. |
| `distributed/capabilities.py` | KEEP | Engineering 22E: remote capability claims and evidence freshness. Imported by `distributed/agent.py`, `distributed/authorization.py`, `distributed/durable.py`, `distributed/https_transport.py`, `distributed/inference_control.py`, `distributed/operations.py`. |
| `distributed/capability.py` | KEEP | Cognitive tools for authenticated, exact-grant remote fleet operations. Imported by `composition/root.py`. |
| `distributed/durable.py` | KEEP | Production exact-scope grants and replay ledger; removed allocation of unused in-memory grant dictionary in durable subclass. |
| `distributed/endpoint_bound_gateway.py` | KEEP | Owns both live identity and exact endpoint admission wrappers before durable authorization/replay checks. |
| `distributed/endpoint_policy.py` | MERGE | ApprovedEndpoint moved unchanged to model.py; obsolete in-memory EndpointPolicy retired in favor of durable endpoint approvals. |
| `distributed/endpoint_policy_durable.py` | KEEP | Durable exact endpoint approvals for PKG-NET. Imported by `application/background_runtime.py`, `distributed/capability.py`, `distributed/endpoint_bound_gateway.py`, `distributed/fleet_probe.py`, `distributed/inference_client.py`, `distributed/inference_control.py`, `distributed/operator.py`, `distributed/remote_control.py`, `distributed/retirement.py`, `distributed/state_paths.py`, `ops/discovery.py`, `ops/windows_rekey_bootstrap.py`. |
| `distributed/fleet_probe.py` | KEEP | Operator-facing authenticated probe for one enrolled Fleet node. Imported by `ops/windows_rekey_bootstrap.py`. |
| `distributed/https_transport.py` | KEEP | Mutual-TLS HTTPS transport for bounded remote fleet operations. Imported by `distributed/capability.py`, `distributed/fleet_probe.py`, `distributed/inference_client.py`. |
| `distributed/identity.py` | MERGE | NodeEnrollment moved unchanged to model.py. Unused NodeIdentityRegistry and hash-only helper retired; TLS certificate fingerprints remain canonical. |
| `distributed/identity_bound_gateway.py` | MERGE | Live IdentityBoundGateway moved unchanged into endpoint_bound_gateway.py; remote_control imports repaired. |
| `distributed/identity_durable.py` | KEEP | Durable node enrollment for PKG-NET. Imported by `application/background_runtime.py`, `distributed/fleet_probe.py`, `distributed/identity_bound_gateway.py`, `distributed/inference_control.py`, `distributed/operator.py`, `distributed/remote_control.py`, `distributed/retirement.py`, `distributed/state_paths.py`, `ops/discovery.py`, `ops/windows_rekey_bootstrap.py`. |
| `distributed/inference.py` | KEEP | Bounded wire contracts for remote cognitive inference over trusted Fleet links. Imported by `distributed/agent.py`, `distributed/https_transport.py`, `distributed/inference_control.py`, `distributed/inference_service.py`. |
| `distributed/inference_client.py` | KEEP | Configured production client for authenticated Fleet cognitive inference. Imported by `composition/root.py`. |
| `distributed/inference_control.py` | KEEP | Durable admission and audit boundary for remote Fleet inference. Imported by `distributed/inference_client.py`, `distributed/state_paths.py`. |
| `distributed/inference_service.py` | KEEP | Agent-side cognitive worker for explicitly allowed local Ollama models. Imported by `distributed/agent_main.py`. |
| `distributed/knowledge.py` | DELETE | PeerKnowledge owned an in-memory enrollment/observation graph with no production caller; OPS discovery owns live peer observations. |
| `distributed/model.py` | KEEP | Canonical immutable node, endpoint, enrollment and endpoint-approval contracts; obsolete reachability/observation models removed. |
| `distributed/operations.py` | KEEP | Engineering 22G: default-deny, bounded remote operations via injected transport. Imported by `distributed/agent.py`, `distributed/capability.py`, `distributed/durable.py`, `distributed/endpoint_bound_gateway.py`, `distributed/fleet_probe.py`, `distributed/https_transport.py`, `distributed/identity_bound_gateway.py`, `distributed/inference_client.py`, `distributed/remote_control.py`. |
| `distributed/operator.py` | KEEP | Host-side operator commands for secure fleet enrollment, endpoints and grants. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `distributed/pki.py` | KEEP | Operator-only PKI provisioning for pinned mutual-TLS Fleet links. Imported by `ops/windows_rekey_bootstrap.py`. |
| `distributed/reachability.py` | DELETE | Offline reachability prototype was referenced only by its own tests; live discovery uses authenticated Fleet probes. |
| `distributed/remote_control.py` | KEEP | Production admission composition for distributed operations. Imported by `distributed/capability.py`, `distributed/fleet_probe.py`, `distributed/inference_client.py`. |
| `distributed/retirement.py` | DELETE | Unwired NodeRetirementCoordinator duplicated operator.retire_node. Retirement regression now invokes the real operator against canonical SQLite. |
| `distributed/state_paths.py` | KEEP | Canonical Fleet state-path policy and legacy sidecar migration. Imported by `application/bootstrap.py`, `distributed/capability.py`, `distributed/fleet_probe.py`, `distributed/inference_client.py`, `distributed/operator.py`, `ops/windows_rekey_bootstrap.py`. |
| `distributed/systemd_agent_service.py` | KEEP | systemd service packaging for Sofía's Fleet agent on Linux. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `distributed/tls.py` | KEEP | Pinned public-key helpers for authenticated fleet TLS. Imported by `distributed/agent.py`, `distributed/https_transport.py`, `distributed/operator.py`, `distributed/pki.py`, `ops/agent_discovery.py`, `ops/windows_rekey_bootstrap.py`. |
| `distributed/version.py` | KEEP | Defines FleetProtocolVersion. Imported by `application/release_runtime.py`, `config/model.py`, `dev/release_cli.py`, `distributed/agent.py`, `distributed/capabilities.py`, `distributed/https_transport.py`, `ops/agent_discovery.py`, `ops/bootstrap.py`, `run/release.py`. |
| `distributed/windows_agent_service.py` | KEEP | Windows SCM host for Sofía's pinned mTLS Fleet agent. Imported by `distributed/windows_agent_service_admin.py`. |
| `distributed/windows_agent_service_admin.py` | KEEP | Install/update/remove/validate the Windows Fleet-agent service. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `integrations/__init__.py` | KEEP | Concrete adapters are exposed to environment factory and production composition. |
| `integrations/capabilities.py` | KEEP | Composition registers concrete capability handlers/cognitive bindings here. Exact-payload execution approvals wrap mutating operations; availability is not authority. |
| `integrations/discord.py` | KEEP | Local Discord control-state adapter. No Discord token or network I/O. Imported by `integrations/capabilities.py`. |
| `integrations/github.py` | KEEP | GitHub REST adapter for repository inspection and bounded issue creation. Imported by `integrations/capabilities.py`. |
| `integrations/home_assistant.py` | KEEP | Home Assistant REST adapter. Imported by `application/act_service.py`, `environment/factory.py`, `environment/home_assistant.py`, `integrations/capabilities.py`. |
| `integrations/http.py` | KEEP | Shared JSON transport used by service-specific adapters; timeout and failure normalization are live integration behavior. |
| `integrations/hyperv.py` | KEEP | Typed local Hyper-V adapter for Windows hosts. Imported by `distributed/agent_tools.py`, `integrations/capabilities.py`. |
| `integrations/jmri.py` | KEEP | JMRI Web Server JSON adapter. Imported by `integrations/capabilities.py`. |
| `integrations/local_maintenance.py` | KEEP | Typed local maintenance executor. Imported by `distributed/agent_tools.py`, `integrations/capabilities.py`, `run/host.py`, `ui/service_control.py`. |
| `integrations/nws.py` | KEEP | Environment factory constructs the weather adapter; URL and redirect validation enforce the official HTTPS host. |
| `integrations/ollama.py` | KEEP | Ollama local-service inspection and model-lifecycle adapter. Imported by `composition/engines.py`, `distributed/agent_tools.py`, `integrations/capabilities.py`, `ui/service_control.py`, `ui/tray_agent.py`. |
| `integrations/portainer.py` | KEEP | Portainer/Docker adapter using Portainer's Docker proxy. Imported by `distributed/agent_tools.py`, `integrations/capabilities.py`. |
| `integrations/sqlite.py` | KEEP | SQLite inspection and explicitly approved maintenance are registered in integrations.capabilities. Queries/checkpoints now close every short-lived connection on success and failure. |
| `integrations/storage.py` | KEEP | Bounded local/NAS storage inspection and management. Imported by `integrations/capabilities.py`. |
| `net/discord_routes.py` | DELETE | No production import or call path; only test_net_discord_routes exercised the classifier. Live Discord transport and distributed TLS own actual connections. |
| `external/__init__.py` | DELETE | Unwired generic external-system prototype; no production consumer outside external. Actual configured service integration uses integrations and canonical CapabilitySystem. |
| `external/adapter.py` | DELETE | Unwired generic external-system prototype; no production consumer outside external. Actual configured service integration uses integrations and canonical CapabilitySystem. |
| `external/authentication.py` | DELETE | Unwired generic external-system prototype; no production consumer outside external. Actual configured service integration uses integrations and canonical CapabilitySystem. |
| `external/capability.py` | DELETE | Unwired generic external-system prototype; no production consumer outside external. Actual configured service integration uses integrations and canonical CapabilitySystem. |
| `external/knowledge.py` | DELETE | Unwired generic external-system prototype; no production consumer outside external. Actual configured service integration uses integrations and canonical CapabilitySystem. |
| `external/model.py` | DELETE | Unwired generic external-system prototype; no production consumer outside external. Actual configured service integration uses integrations and canonical CapabilitySystem. |
| `filesystem/__init__.py` | KEEP | Live package exports retained; orphan exception export removed. |
| `filesystem/capability.py` | KEEP | Composition registers bounded filesystem inspection; capability availability does not authorize paths. |
| `filesystem/change_capability.py` | KEEP | Composition registers filesystem change inspection through canonical capability bindings. |
| `filesystem/change_filter.py` | KEEP | Production observer/capability filters bounded change evidence. |
| `filesystem/changes.py` | KEEP | Typed evidence/deltas consumed by observation and filesystem change capability. |
| `filesystem/inspector.py` | KEEP | Composition constructs the bounded read-only inspector. Authorized root checks precede observation; path normalization, symlink handling and limits belong to this one inspection responsibility. |
| `filesystem/model.py` | KEEP | Canonical operation/result contracts used by inspector, orchestrator and capability. Removed unused FilesystemInspectionError; actual outcomes are typed FilesystemResult values. |
| `filesystem/observation.py` | KEEP | Production filesystem change observation stores SQLite baselines; file hashing is a module-local live helper. |
| `filesystem/orchestrator.py` | KEEP | Conversation/application path translates bounded filesystem requests into canonical authorization and inspection. |

## Phase 10

| File | Decision | Evidence / reason |
| --- | --- | --- |
| `config/__init__.py` | KEEP | Live configuration factory, layout and authority exports. |
| `config/authority.py` | KEEP | State-plane configuration resolution ranks protected policy, process, host and shared values; equal-authority conflicts fail closed. |
| `config/cognitive_models.py` | KEEP | Resolve effective cognitive model roles from runtime configuration. Imported by `cognition/model_lifecycle.py`, `composition/engines.py`, `operational/status_queries.py`, `runtime/response.py`, `runtime/runtime.py`, `ui/tray_agent.py`, `verify/dual_cognition.py`. |
| `config/defaults.py` | KEEP | Production factory calls the common configuration builder with production mode; module-local environment parsing helpers are live. |
| `config/layout.py` | KEEP | Central runtime storage/environment interpretation; production defaults and protected-source layout are live bootstrap policy. |
| `config/model.py` | KEEP | Configuration value contracts consumed by factories/composition; provider selection does not define Sofia identity. |
| `config/model_catalog.py` | KEEP | Local model presets and known names consumed by settings; preset class constructs the module-local canonical catalog. |
| `config/reviewed_projection.py` | KEEP | Application evolution applies only validated reviewed configuration projections; distinct from user settings. |
| `config/state_store.py` | KEEP | SAFE capability policy reads canonical state-plane configuration through this store. |
| `config/user_settings.py` | KEEP | Runtime/application/environment/UI/Discord consume canonical user preferences; their ownership differs from protected execution policy. |
| `constitution/__init__.py` | KEEP | Package marker retained; consumers import the canonical store explicitly. |
| `constitution/constitution.md` | KEEP | Protected canonical constitution source; bytes unchanged. |
| `constitution/constitution.sha256` | KEEP | Trusted integrity pin; bytes unchanged. |
| `constitution/integrity.py` | MERGE | Integrity verifier and error moved unchanged into store.py; repaired composition/runtime/EVOLVE/VERIFY imports. |
| `constitution/model.py` | MERGE | Immutable Constitution moved unchanged into store.py beside its loader; repaired cognition/runtime/self-model/test imports. |
| `constitution/store.py` | KEEP | One compact canonical loader/model/integrity module; newline normalization, SHA-256 and expected trusted-pin validation remain unchanged. |
| `evolve/__init__.py` | KEEP | PKG-EVOLVE: governed proposals and independently authorized revisions. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `evolve/amendment.py` | KEEP | Immutable EVOLVE protected-state proposals. Imported by `application/evolution.py`, `evolve/approval.py`, `evolve/executor.py`, `safe/evolve_approval.py`, `safe/evolve_approve.py`. |
| `evolve/approval.py` | KEEP | Independent approval boundary for EVOLVE protected changes. Imported by `application/evolution.py`, `evolve/executor.py`, `evolve/revision.py`, `safe/evolve_approval.py`, `safe/evolve_approve.py`. |
| `evolve/executor.py` | KEEP | Privileged protected-state amendment executor with verified rollback. Imported by `application/evolution.py`. |
| `evolve/revision.py` | KEEP | Reviewed, reversible non-protected preference/config evolution. Imported by `application/evolution.py`, `evolve/state_plane_adapter.py`, `safe/evolve_approval.py`, `safe/evolve_approve.py`. |
| `evolve/state_plane_adapter.py` | KEEP | Defines StatePlaneRevisionAdapter. Imported by `application/evolution.py`. |
| `integrate/__init__.py` | KEEP | Inert package marker for the live INTEGRATE Matrix evaluator; retired generic registry exports removed. |
| `integrate/activation.py` | DELETE | Unwired JSON activation state duplicated a prototype registry; no production composition consumer. |
| `integrate/capability_adapter.py` | DELETE | Unwired wrapper over canonical CapabilitySystem; mixed acceptance tests now use the actual capability boundary. |
| `integrate/governed.py` | DELETE | Generic adapter registry had no production registration or entry point; concrete integrations enforce real approvals. |
| `integrate/matrix.py` | KEEP | Registered in cognition.matrix.defaults and used by production routing. |
| `integrate/model.py` | MOVE | Live SideEffectClass moved unchanged into integrations.capabilities, its actual production owner. Unused AdapterManifest/ToolInvocation/ToolReceipt retired. |
| `integrate/policy.py` | DELETE | Prototype InvocationContext/Policy only governed the unused registry. |
| `integrate/receipts.py` | DELETE | JSONL receipt ledger belonged solely to the unwired registry; actual SAFE/ACT/runtime audit owners remain. |
| `integrate/registry.py` | DELETE | Test-only generic registry duplicated concrete capability registration. |
| `integrate/schema.py` | DELETE | Schema wrapper was used only by retired registry and exclusive tests. |
| `dev/__init__.py` | KEEP | Retired proposal exports removed; actual DEV capability lazy exports retained to avoid SAFE import cycles. |
| `dev/approval.py` | KEEP | Exact DEV operation/payload approval contracts consumed by SAFE and DEV capability. |
| `dev/capability.py` | KEEP | Composition registers DEV status/build/apply/commit/push/rollback capabilities with independent approvals. |
| `dev/change_review.py` | DELETE | ChangeProposal/ReviewState/inspect were exported but never consumed by production DEV workflow; their two exclusive cross-package cases retired with the prototype. |
| `dev/dependency_lock.py` | KEEP | Explicit operator CLI builds hashed dependency locks; internal hash/wheel helpers are live CLI calls. |
| `dev/git_workspace.py` | KEEP | Canonical scoped Git lifecycle implementation consumed by actual workflow. |
| `dev/matrix.py` | KEEP | Registered production Matrix contribution. |
| `dev/opencode.py` | KEEP | Live bounded engineering executor now owns its exact approved-path guard. Base SHA, scope, symlink and explicit authority checks remain. |
| `dev/release.py` | KEEP | Canonical release manifest validation consumed by RUN and SAFE. |
| `dev/release_cli.py` | KEEP | Explicit operator CLI constructs/verifies/signs release evidence; not invoked automatically by chat. |
| `dev/release_signing.py` | KEEP | CLI/supply-chain signing uses verified Ed25519 key loading and manifest signature generation. |
| `dev/release_store.py` | KEEP | Application release runtime and RUN activation own release state via this store. |
| `dev/supply_chain.py` | KEEP | Actual release construction/verification pipeline owns lock, artifact hash, SBOM and provenance checks. |
| `dev/workflow.py` | KEEP | DevToolService uses EngineeringWorkflow for reviewed candidates and guarded Git operations. |
| `dev/workspace.py` | MERGE | WorkspaceGuard and WorkspaceViolation moved unchanged into opencode.py, their sole production caller. Package exports and test imports repaired. |
| `codebase/__init__.py` | KEEP | Exports repaired to canonical capability module; analyzer/inspection contracts remain. |
| `codebase/analyzers.py` | KEEP | Actual registry and analyzer protocol remain; removed python_module_from_analysis and file_from_path, which had no callers anywhere. Inspector directly builds canonical metadata. |
| `codebase/codebase.py` | RENAME | Renamed to capability.py: this module defines CodebaseCapability and CODEBASE_INSPECT_CAPABILITY, not the entire codebase subsystem. Composition/package/test imports repaired. |
| `codebase/evidence.py` | KEEP | Cognitive tool formatting consumes bounded structural evidence. |
| `codebase/inspector.py` | KEEP | Composition constructs bounded read-only structural inspection; file discovery and module-name helpers are live local calls. |
| `codebase/model.py` | KEEP | Canonical language-neutral files, Python evidence and module-relationship contracts. |
| `codebase/python.py` | KEEP | Default registry constructs PythonAnalyzer, which consumes PythonInspector; local references are live despite no outside lexical caller for every helper. |
| `codebase/relationships.py` | KEEP | Inspector derives import relationships using the canonical observed module model. |
| `clean/__init__.py` | KEEP | Canonical cleanup/recovery API exports retained. |
| `clean/__main__.py` | KEEP | Explicit operator snapshot/plan/apply CLI; apply requires confirmation and a verified matching recovery manifest. |
| `clean/planner.py` | KEEP | CLI consumes bounded cleanup plans protecting active/previous releases; apply revalidates protected paths and recovery evidence. |
| `clean/recovery.py` | KEEP | CLI creates/verifies SQLite recovery snapshots and manifests; short-lived integrity-check connections now explicitly close. |
| `operational/__init__.py` | KEEP | Canonical operational model/store exports consumed by production. |
| `operational/model.py` | KEEP | Immutable runtime instance and continuity evidence contracts consumed by runtime/self-model/cognition; runtime ID is not persistent identity. |
| `operational/status_queries.py` | KEEP | Runtime constructs OperationalStatusQueryResolver; configured models, registered DEV capabilities and unknown network health are reported with explicit evidence limits. |
| `operational/store.py` | KEEP | Application/runtime persists start/stop/lifecycle history in canonical SQLite and derives bounded continuity evidence. |

## Latest wardrobe follow-up

| File | Decision | Evidence / reason |
| --- | --- | --- |
| `avatar/__init__.py` | KEEP | Headless AVATAR state, wardrobe, presentation, and authoring subsystem. Bounded package API or module entry point; local definitions and package exports do not by themselves establish production execution. |
| `avatar/authoring.py` | KEEP | Latest content-rating/exposure fields are passed into authored designs; earlier retirement of redundant type cache remains. |
| `avatar/clothing_action.py` | KEEP | Authoritative state-changing service for AVATAR clothing actions. Imported by `application/bootstrap.py`. |
| `avatar/clothing_intent.py` | KEEP | Natural-language clothing intent parsing for AVATAR wardrobe actions. Imported by `avatar/wardrobe_autonomy.py`, `avatar/clothing_action.py`. |
| `avatar/fit.py` | KEEP | Body-region mappings and validated fit anchors for wardrobe blueprints. Imported by `avatar/wardrobe_catalog.py`. |
| `avatar/matrix.py` | KEEP | AVATAR contribution to the message matrix. Imported by `cognition/matrix/defaults.py`. |
| `avatar/presentation.py` | KEEP | Headless authoritative AVATAR presentation state. Imported by `ui/theme.py`, `runtime/runtime.py`, `cognition/context.py`, `cognition/assembler.py`, `avatar/self_fact_query.py`, `avatar/private_grant.py`, `avatar/presentation_store.py`, `avatar/presentation_runtime.py`, `avatar/presentation_routine.py`, `avatar/clothing_action.py`, `avatar/authoring.py`. |
| `avatar/presentation_routine.py` | KEEP | Headless daily AVATAR presentation routine. Imported by `application/bootstrap.py`. |
| `avatar/presentation_runtime.py` | KEEP | Runtime bootstrap and migration for headless AVATAR presentation. Imported by `avatar/clothing_action.py`, `application/bootstrap.py`. |
| `avatar/presentation_store.py` | KEEP | Durable SQLite persistence for headless AVATAR presentation state. Imported by `avatar/presentation_runtime.py`, `avatar/presentation_routine.py`, `avatar/authoring.py`, `application/bootstrap.py`. |
| `avatar/private_grant.py` | KEEP | Trusted host resolution for private AVATAR presentation access. Imported by `runtime/runtime.py`, `avatar/clothing_action.py`. |
| `avatar/self_fact_query.py` | KEEP | Deterministic answers for direct authoritative AVATAR self-fact queries. Imported by `runtime/runtime.py`. |
| `avatar/wardrobe.py` | KEEP | Offline wardrobe metadata, layering and covered-default policy. Imported by `avatar/wardrobe_planner.py`, `avatar/wardrobe_matrix.py`, `avatar/wardrobe_design.py`, `avatar/wardrobe_catalog.py`, `avatar/presentation_store.py`, `avatar/presentation.py`, `avatar/clothing_action.py`, `avatar/authoring.py`. |
| `avatar/wardrobe_autonomy.py` | KEEP | Contextual autonomy policy for requested AVATAR wardrobe changes. Imported by `avatar/clothing_action.py`, `application/bootstrap.py`. |
| `avatar/wardrobe_catalog.py` | SPLIT | Retained starter/default assembly. Latest prebuild contracts live in wardrobe_prebuild.py; JSON schema/profile decoding moved to wardrobe_loader.py with injected canonical blueprint construction. |
| `avatar/wardrobe_data/bottoms.json` | KEEP | Packaged canonical bottoms metadata: 20 records, 10 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_data/footwear.json` | KEEP | Packaged canonical footwear metadata: 20 records, 9 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_data/one_pieces.json` | KEEP | Packaged canonical dresses_and_one_pieces metadata: 20 records, 8 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_data/outerwear.json` | KEEP | Packaged canonical outerwear metadata: 20 records, 8 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_data/tops.json` | KEEP | Packaged canonical tops metadata: 20 records, 10 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_data/underlayers_lower.json` | KEEP | Packaged canonical underlayers_lower metadata: 24 records, 8 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_data/underlayers_upper.json` | KEEP | Packaged canonical underlayers_upper metadata: 24 records, 8 profile templates. Loader validates referenced profiles; exact incoming bytes retained. |
| `avatar/wardrobe_design.py` | SPLIT | Preserved latest content-rating/exposure validation and positional GarmentDesign compatibility. Expanded type definitions live in wardrobe_types.py. |
| `avatar/wardrobe_matrix.py` | KEEP | Latest rating/exposure cell projections retained; canonical presentation runtime consumes the matrix. |
| `avatar/wardrobe_planner.py` | KEEP | Fixed double counting of the same grounded emotion across garment profiles and outfit tags; combined contribution obeys the existing three-point cap. |
