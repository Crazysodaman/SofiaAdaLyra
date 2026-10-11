# Workstream 3 Phase 10: 27-task production source audit

- **Audit date:** 2026-10-11
- **GitHub `main` HEAD at inspection:** `db20afcabec455feaee95b81be64653736deba7e`.
- **Master:** `docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md` original Phase 10, 27 stable CA IDs.
- **Source ledger:** `docs/development/v18-task-evidence.json`; this file is **not** overwritten by Workstream 3.
- **Method:** static original requirement against production files, source caller and canonical state/SAFE evidence previously inspected in this workstream. Where an actual full caller or acceptance matrix has not been traced, record the gap rather than claiming implementation. Existing file/class is **not** coding completeness. Original task descriptions reproduced without changing their wording. Some entries are deliberately a first-pass source hypothesis, not a completed per-function audit.
- **No execution:** Python tests, CI, models, services, live hosts, transport, physical devices, databases and environment were NOT invoked.
- **Result:** 27/27 Phase 10 original ID entries inventoried, with particular confirmed gaps in CA-1403 (semantic matching), CA-1404/2606 (exact host/tool suitability), CA-1405 (governed skill revisions), and CA-2601/2602 (source registry and real event integration). None declared fully accepted or fully coded. Original 700-task ledger classifications reproduced as of inspected HEAD.

## Item-specific evidence inventory

| CA ID | Existing ledger classification | Key source pointer | Primary unresolved clause |
|---|---|---|---|
|---|---|---|---|
| **CA-1001** | unassessed | src/sofia/application/conversation_learning.py | end-to-end event adapter missing or unproven |
| **CA-1002** | unassessed | src/sofia/application/background_runtime.py | requires full router trace and deferred tests |
| **CA-1003** | unassessed | src/sofia/environment/service.py | cross-caller context proof outstanding |
| **CA-1004** | partial_wiring | src/sofia/environment/home_assistant.py | read-only event bridge and write permission matrix open |
| **CA-1005** | unassessed | src/sofia/ops/placement.py | source identity, freshness and admission integration open |
| **CA-1006** | partial_wiring | src/sofia/integrations/capabilities.py | source-to-user/project wiring pending |
| **CA-1007** | unassessed | src/sofia/application/background_runtime.py | active production route, remaining delivery/channel proof |
| **CA-1008** | unassessed | src/sofia/neuro/sensory.py | safety/observation wiring missing or unproven |
| **CA-1009** | unassessed | src/sofia/integrations/jmri.py | read-only source bridge and separate motion/power classification needed |
| **CA-1010** | unassessed | src/sofia/creative/world_bridge.py | simulated receipts and personal creative loop open |
| **CA-1011** | unassessed | src/sofia/application/expression_runtime.py | render proof and offline fallback tests outstanding |
| **CA-1012** | unassessed | src/sofia/integrations/capabilities.py | optional per-provider design/activation not assumed |
| **CA-1401** | partial_wiring | src/sofia/life/procedures.py | catalog source connected, complete clauses pending |
| **CA-1402** | unassessed | src/sofia/life/procedures.py | reproducible source proof code present, verification deferred |
| **CA-1403** | unassessed | src/sofia/life/coordinator.py | safe typed lookup wired; semantic matching remaining |
| **CA-1404** | unassessed | src/sofia/life/procedures.py | confirmed missing host/tool-version attempt compatibility |
| **CA-1405** | unassessed | src/sofia/life/procedures.py | quarantine wired; revision/rollback policy missing |
| **CA-1406** | unassessed | test/test_life_procedure_catalog.py | deferred restart and original-replay proof |
| **CA-1407** | unassessed | src/sofia/life/draft_agent.py | no-bypass verification gate remains |
| **CA-2601** | unassessed | src/sofia/integrations/capabilities.py | source registry incomplete |
| **CA-2602** | unassessed | src/sofia/application/presence.py | one-at-a-time opt-in original event bridge pending |
| **CA-2603** | unassessed | src/sofia/ops/fleet.py | Venus/Artemis matrix deferred |
| **CA-2604** | unassessed | src/sofia/neuro/sensory.py | optional, owner activation and virtual proof first |
| **CA-2605** | unassessed | src/sofia/integrations/jmri.py | optional observation-only adapter integration |
| **CA-2606** | unassessed | src/sofia/ops/placement.py | confirmed eligibility integration gap |
| **CA-2607** | unassessed | src/sofia/integrations/capabilities.py | optional provider-by-provider gate |
| **CA-2608** | unassessed | src/sofia/integrations/capabilities.py | source boundary present, full permission acceptance deferred |

## Original wording and source checks

<details><summary>CA-1001 original requirement and observed source evidence</summary>

**CA-1001 [GAP]** Add one typed eligible-event adapter from COGNITION v2 and its evidence ledger to LIFE/NEURO; preserve exact principal, audience, subject and evidence identity rather than copying arbitrary transcript summaries.

**Evidence inspected:** `src/sofia/application/conversation_learning.py`, `src/sofia/neuro/adapters.py`.

**Observed:** ConversationLearningCoordinator persists exact-source proposed MEM candidates, and NEURO has pure adapters. A common typed COGNITION evidence event consumed by LIFE and NEURO was not traced.

**Not concluded:** end-to-end event adapter missing or unproven. No tests were run.

</details>

<details><summary>CA-1002 original requirement and observed source evidence</summary>

**CA-1002 [EXISTS → VERIFY]** Bridge the existing dual local Ollama roles to LIFE ideation/critique/VERIFY through cognition's canonical router and role-local locks; no new direct model clients or guaranteed extra wakeups.

**Evidence inspected:** `src/sofia/application/background_runtime.py`, `src/sofia/application/bootstrap.py`, `src/sofia/life/idea_agent.py`.

**Observed:** LIFE background invokes model generation via application-owned callbacks. Exact dual-model role-local lock and critique routing across all callers was not confirmed.

**Not concluded:** requires full router trace and deferred tests. No tests were run.

</details>

<details><summary>CA-1003 original requirement and observed source evidence</summary>

**CA-1003 [EXISTS → VERIFY]** Use ENVIRONMENT/NWS and local time (America/Chicago) as context for scheduled interests, wardrobe, outdoor plans and attention, never as evidence of unobserved real-world events.

**Evidence inspected:** `src/sofia/environment/service.py`, `src/sofia/environment/nws.py`, `src/sofia/neuro/adapters.py`.

**Observed:** Environment/NWS local data flows to snapshot and NEURO adapters. No verified source evidence for every schedule/wardrobe/interest decision is established by these reads.

**Not concluded:** cross-caller context proof outstanding. No tests were run.

</details>

<details><summary>CA-1004 original requirement and observed source evidence</summary>

**CA-1004 [EXISTS → GAP]** Integrate Hestia/Home Assistant **read-only**, exposing approved status and events to Presence/LIFE/NEURO; every write to lights, climate or automations requires the existing permission classification.

**Evidence inspected:** `src/sofia/environment/home_assistant.py`, `src/sofia/integrations/capabilities.py`.

**Observed:** An explicitly configured read-only Home Assistant environment provider and separate typed integration tools exist. Full authenticated status/event path into LIFE/Presence/NEURO not established.

**Not concluded:** read-only event bridge and write permission matrix open. No tests were run.

</details>

<details><summary>CA-1005 original requirement and observed source evidence</summary>

**CA-1005 [EXISTS → GAP]** Integrate Venus/Artemis/Terra/Fleet telemetry for workload scheduling and optional project ideas, without automatically enrolling machines or using remote commands outside grants.

**Evidence inspected:** `src/sofia/ops/placement.py`, `src/sofia/ops/model.py`, `src/sofia/application/fleet_runtime.py`.

**Observed:** PlacementEngine and Fleet runtime paths exist. No proven independent LIFE ideation decision consuming real scoped Venus/Artemis/Terra telemetry.

**Not concluded:** source identity, freshness and admission integration open. No tests were run.

</details>

<details><summary>CA-1006 original requirement and observed source evidence</summary>

**CA-1006 [EXISTS → GAP]** Connect Eos Docker/Portainer health and service logs to evidence-backed diagnostics, personal project proposals and DEV review. Do not restart or edit containers solely because the companion wants to experiment.

**Evidence inspected:** `src/sofia/integrations/capabilities.py`, `src/sofia/ops/capability.py`.

**Observed:** Configured homelab diagnostic integrations and permission gateway exist. No confirmed Docker Eos source→Presence/LIFE→DEV review chain.

**Not concluded:** source-to-user/project wiring pending. No tests were run.

</details>

<details><summary>CA-1007 original requirement and observed source evidence</summary>

**CA-1007 [EXISTS → GAP]** Let Discord/Desktop presence surface thoughtful ACT follow-ups and real project sharing, deduplicated across channels with recipient acknowledgement.

**Evidence inspected:** `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed:** Verified LIFE milestone→Presence→ACT private owner route exists; newest exact-event last-send guards and truthful traces committed. Cross-channel dedupe, authenticated Discord/desktop receipts and live tests are not fully evidenced.

**Not concluded:** active production route, remaining delivery/channel proof. No tests were run.

</details>

<details><summary>CA-1008 original requirement and observed source evidence</summary>

**CA-1008 [EXISTS → GAP]** Route Gaia 2.0 robot observations or simulator results to NEURO/MEM/LIFE as evidence for suggestions; retain hard hardware safety, dry-run and explicit authorization before servo actuation.

**Evidence inspected:** `src/sofia/neuro/sensory.py`, `src/sofia/ops/capability.py`.

**Observed:** NEURO has typed sensory adapters and SAFE capability gating. A real Gaia 2.0 scoped original simulator/sensor receipt entering LIFE/NEURO was not traced.

**Not concluded:** safety/observation wiring missing or unproven. No tests were run.

</details>

<details><summary>CA-1009 original requirement and observed source evidence</summary>

**CA-1009 [EXISTS → GAP]** Connect Athena/JMRI *read-only* roster/power/occupancy evidence to shared railroad interests, troubleshooting follow-ups and projects. Locomotive motion and layout power remain separate safety-gated actions.

**Evidence inspected:** `src/sofia/integrations/jmri.py`, `src/sofia/integrations/capabilities.py`.

**Observed:** JMRI typed roster/power read methods and a separately named mutation exist. Original observation→hobby interest/project/ACT admission not demonstrated.

**Not concluded:** read-only source bridge and separate motion/power classification needed. No tests were run.

</details>

<details><summary>CA-1010 original requirement and observed source evidence</summary>

**CA-1010 [EXISTS → GAP]** Connect her virtual lab/world to verifiable creative work, object interactions and avatar renderer receipts; separate simulated contact from physical actions.

**Evidence inspected:** `src/sofia/creative/world_bridge.py`, `src/sofia/interaction/world_editor.py`.

**Observed:** World bridge can place creative artifacts; WorldEditor symbolic world actions are separate. Verified interaction ack→LIFE next-choice bridge not traced.

**Not concluded:** simulated receipts and personal creative loop open. No tests were run.

</details>

<details><summary>CA-1011 original requirement and observed source evidence</summary>

**CA-1011 [EXISTS → GAP]** Bridge local voice pipeline and avatar pose/ears/tail/expression to the same `ExpressionIntent`, with speech/animation acknowledgement and muted/no-device paths.

**Evidence inspected:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/bootstrap.py`.

**Observed:** Canonical ExpressionIntent/Decision/Receipt models exist and are composed. End-to-end actual voice and avatar playback/render acknowledgements require channel-specific audit.

**Not concluded:** render proof and offline fallback tests outstanding. No tests were run.

</details>

<details><summary>CA-1012 original requirement and observed source evidence</summary>

**CA-1012 [OPTIONAL]** Evaluate opt-in personal resources (calendar/tasks, GitHub issues, documentation knowledge, Grocy/Mealie/Homebox, local media metadata) through existing providers and scoped permissions; include per-source retention, availability, and privacy policy **before** adding a connector.

**Evidence inspected:** `src/sofia/integrations/capabilities.py`, `src/sofia/application/bootstrap.py`.

**Observed:** Connector framework present, but each optional external provider requires distinct per-source consent, availability, retention and read/write scope.

**Not concluded:** optional per-provider design/activation not assumed. No tests were run.

</details>

<details><summary>CA-1401 original requirement and observed source evidence</summary>

**CA-1401 [GAP]** Add a **governed procedure catalog** inside the canonical state: purpose, typed inputs, expected outputs, preconditions, exact capabilities, environment requirements, verification tests, version, provenance, and owner.

**Evidence inspected:** `src/sofia/life/procedures.py`, `src/sofia/life/coordinator.py`.

**Observed:** LifeProcedureCatalog stores purpose, source typed goals, version, environment, tools, provenance and status in canonical state. Original requirements around verification test descriptors and lifecycle are broader.

**Not concluded:** catalog source connected, complete clauses pending. No tests were run.

</details>

<details><summary>CA-1402 original requirement and observed source evidence</summary>

**CA-1402 [GAP]** Promote a procedure only after a real successful receipt plus a reproducibility check; unverified model suggestions remain candidate descriptions, not executable skills.

**Evidence inspected:** `src/sofia/life/procedures.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/explorer.py`.

**Observed:** Record writer independently rechecks original RUN job, evidence, exact creative bytes and typed objective PASS. Two distinct successful projects required for VERIFIED; long-horizon/restart proof unexecuted.

**Not concluded:** reproducible source proof code present, verification deferred. No tests were run.

</details>

<details><summary>CA-1403 original requirement and observed source evidence</summary>

**CA-1403 [GAP]** Let LIFE retrieve relevant procedures when starting a similar project, using semantic relevance plus typed safety/compatibility checks; never bypass DEV/RUN/SAFE.

**Evidence inspected:** `src/sofia/life/coordinator.py`, `src/sofia/life/draft_agent.py`, `src/sofia/life/procedures.py`.

**Observed:** Real LIFE model drafting/revision receives up to two source-verified exact capability/objective/environment precedents. Semantic relevance beyond strict match was not demonstrated.

**Not concluded:** safe typed lookup wired; semantic matching remaining. No tests were run.

</details>

<details><summary>CA-1404 original requirement and observed source evidence</summary>

**CA-1404 [GAP]** Track attempt outcomes and procedure compatibility by host, OS, Python, tool versions, and Fleet capabilities; prevent Venus instructions from silently assuming Artemis has identical software.

**Evidence inspected:** `src/sofia/life/procedures.py`, `src/sofia/ops/placement.py`.

**Observed:** Catalog environment key covers current OS, architecture, Python major/minor only. No versioned tool/Fleet/remote capability evidence stored for attempts; failures not source-attributed in procedure history.

**Not concluded:** confirmed missing host/tool-version attempt compatibility. No tests were run.

</details>

<details><summary>CA-1405 original requirement and observed source evidence</summary>

**CA-1405 [GAP]** Reconcile stale or failed procedures through quarantine, rollback, revision and re-verification. Never run a previously successful remote mutation merely because it is in the library.

**Evidence inspected:** `src/sofia/life/procedures.py`, `src/sofia/life/coordinator.py`.

**Observed:** Original proof freshness is rechecked, bounded rotating background audit quarantines invalid skill and exact proof references are enforced. Rollback, revision, independently re-verified promotion after quarantine are not proven.

**Not concluded:** quarantine wired; revision/rollback policy missing. No tests were run.

</details>

<details><summary>CA-1406 original requirement and observed source evidence</summary>

**CA-1406 [VERIFY]** Demonstrate a safe repeatable virtual-world or creative workflow succeeding twice after a full restart, with the second run using validated prior steps.

**Evidence inspected:** `test/test_life_procedure_catalog.py`, `src/sofia/life/coordinator.py`.

**Observed:** Deferred regression fixtures for independently successful creative attempts exist. No test executed, no actual full restart acceptance verified.

**Not concluded:** deferred restart and original-replay proof. No tests were run.

</details>

<details><summary>CA-1407 original requirement and observed source evidence</summary>

**CA-1407 [VERIFY]** Prove no procedure can execute an unapproved command, reuse expired grants, cross user audiences, or elevate its own tool scope.

**Evidence inspected:** `src/sofia/life/draft_agent.py`, `src/sofia/life/procedures.py`, `src/sofia/life/coordinator.py`, `src/sofia/safe/permissions.py`.

**Observed:** Precedents are metadata without executable grants and stored exact owner/audience checks exist. End-to-end expired grant, cross audience and actual SAFE refusal matrix not yet verified.

**Not concluded:** no-bypass verification gate remains. No tests were run.

</details>

<details><summary>CA-2601 original requirement and observed source evidence</summary>

**CA-2601 P2 [VERIFY]** For every approved read-only Fleet/Home Assistant/Docker/JMRI source, record a **trusted source registry** with owner, authenticated host/node, endpoint, freshness TTL, possible failures, unit/schema normalization and allowed data audience.

**Evidence inspected:** `src/sofia/integrations/capabilities.py`, `src/sofia/ops/agent_discovery.py`.

**Observed:** Typed integration and authenticated Fleet discovery components exist. One shared audited registry with host identity, source TTL, units, possible errors and mutation classification for all four named sources not established.

**Not concluded:** source registry incomplete. No tests were run.

</details>

<details><summary>CA-2602 original requirement and observed source evidence</summary>

**CA-2602 P2 [GAP]** Build **one opt-in event source at a time** into Presence and then LIFE/NEURO, starting with non-mutating, high-value events (e.g., a verified service recovery or project-related JMRI observation); test removal/disable independently.

**Evidence inspected:** `src/sofia/application/presence.py`, `src/sofia/neuro/adapters.py`.

**Observed:** Presence accepts source-grounded observations and NEURO has adapters, but a real configured external event source simultaneously linked to optional LIFE interest is not proven.

**Not concluded:** one-at-a-time opt-in original event bridge pending. No tests were run.

</details>

<details><summary>CA-2603 original requirement and observed source evidence</summary>

**CA-2603 P2 [VERIFY]** Create a **Venus ↔ Artemis cross-host identity matrix**: same subject names with different node IDs, stale data, host offline, TLS failure and contradictory telemetry must never be merged into a single false statement.

**Evidence inspected:** `src/sofia/ops/fleet.py`, `src/sofia/ops/agent_discovery.py`, `test/test_ops_fleet_discovery_permissions.py`.

**Observed:** Fleet identities and authenticated discovery exist. Cross-host contradictory telemetry freshness and identity acceptance matrix not verified.

**Not concluded:** Venus/Artemis matrix deferred. No tests were run.

</details>

<details><summary>CA-2604 original requirement and observed source evidence</summary>

**CA-2604 P2 [OPTIONAL]** For Gaia, build a **simulation-first observation-to-experiment pathway** using BODY and real servo constraints; test sensor disconnect, stop commands and permission denial before exposing any actual movement.

**Evidence inspected:** `src/sofia/neuro/sensory.py`, `src/sofia/ops/capability.py`.

**Observed:** Optional Gaia simulation-first experiment has no confirmed original simulator receipt→LIFE integration in source traces. Do not activate physical servos by preference.

**Not concluded:** optional, owner activation and virtual proof first. No tests were run.

</details>

<details><summary>CA-2605 original requirement and observed source evidence</summary>

**CA-2605 P2 [OPTIONAL]** For Athena/JMRI, limit the initial companion experiment to **read-only** roster/power/occupancy observation and hobby planning; leave locomotive movement and layout power behind separate exact approvals.

**Evidence inspected:** `src/sofia/integrations/jmri.py`, `src/sofia/integrations/capabilities.py`.

**Observed:** Read-only JMRI typed methods exist. No audited hobby experiment importing original JMRI observations into LIFE selection; layout power/movement must remain separately granted.

**Not concluded:** optional observation-only adapter integration. No tests were run.

</details>

<details><summary>CA-2606 original requirement and observed source evidence</summary>

**CA-2606 P2 [GAP]** Add a **resource/environment suitability check** to creative skills: avoid GPU-heavy experiments when gaming, avoid impossible Blender/GUI requirements on headless Eos, and report uninstalled tool dependencies truthfully.

**Evidence inspected:** `src/sofia/ops/placement.py`, `src/sofia/life/procedures.py`, `src/sofia/life/coordinator.py`.

**Observed:** Placement has workload suitability and LIFE knows project resource budgets, but repeatable creative skill suitability does not incorporate verified per-host tool version or headless/GUI capability.

**Not concluded:** confirmed eligibility integration gap. No tests were run.

</details>

<details><summary>CA-2607 original requirement and observed source evidence</summary>

**CA-2607 P2 [VERIFY]** Evaluate a small set of **user-owned read-only tools** (Grocy, Mealie, Homebox, Plex metadata, optional calendar) only after confirming a real provider/connector, authorization model and retention setting; do not add an implicit network crawler.

**Evidence inspected:** `src/sofia/integrations/capabilities.py`, `src/sofia/application/bootstrap.py`.

**Observed:** Optional read-only applications cannot count as evaluated without an actually configured authorized provider and per-source retention. No live proof executed.

**Not concluded:** optional provider-by-provider gate. No tests were run.

</details>

<details><summary>CA-2608 original requirement and observed source evidence</summary>

**CA-2608 P2 [VERIFY]** Reconfirm **Gaia/JMRI/Hestia real-world action classification** after any new attention, motivation or skill system is connected. Demonstrate that NEURO/connectome preference can never authorize device control.

**Evidence inspected:** `src/sofia/integrations/capabilities.py`, `src/sofia/safe/permissions.py`, `src/sofia/neuro/adapters.py`.

**Observed:** Tools and attention-only NEURO adapters are separated; physical action classification must be rerun after each new skill/motivation bridge. No actual host or device acceptance executed.

**Not concluded:** source boundary present, full permission acceptance deferred. No tests were run.

</details>

## Follow-up scope

- Prioritize trust-preserving real source bridge, exact tool/host compatibility, source receipt robustness and guarded revision path.
- Do not add remote model clients, independent schedulers, permanent grants or device actuation.
- Full proof still requires source semantics, exact-SHA regression tests, CI, and supervised relevant host tests in the owner's final campaign.


## Audit follow-up: operator view exact-source correction (2026-10-11)

Previously a stale global `verified_proof_projects(limit=64)` page limited `goal_dependency_view` even after drafting was corrected to use exact scoped proof. Production changed to exact per-project lookup with request-local bounded memoization, preserving source receipt and typed objective revalidation before displaying a verified skill. Regression authored, unexecuted. CA-1403 and CA-1405 remain partial full requirements.


## Continued implementation evidence: exact native creative toolchain (2026-10-11)

Production `LifeProcedureCatalog.record_verified_attempt` now requires a current `NativeCreativeAdapter.probe` plus exact original creative `tool_id` and `tool_version` agreement in the durable `ArtifactRevision` and RUN evidence. `SelfDirectedLifeCoordinator._verified_procedure_origins_current` enforces the identical read-only predicate for real draft reuse and rotating source audit. Stale native version/ID fails closed and can be quarantined. This **narrows** the original CA-1404/2606 gap, but does not record independently authenticated historical Fleet node identity, remote tool versions, or every host capability. It must not be described as cross-host portable skills, nor as passing tests. Production commits `fcd7cdfa`, `1f77114b`; deferred regression source `e7fdba91`.


## 2026-10-11 production follow-up: first-writer-only skill quarantine

The existing `LifeProcedureCatalog.quarantine` now atomically transitions VERIFIED→QUARANTINED exactly once, preserving the first reason and timestamp. Repeated audits or competing coordinators cannot rewrite that evidence or report a second invalidation, and never-verified candidates are rejected. `SelfDirectedLifeCoordinator._audit_procedure_sources` counts only actually changed rows. Partial original IDs CA-1405/1407/2408; production `d47f868f`, `f41b2774`; tests authored `b909eb65`, unexecuted. There is **no new reinstatement authority**: owner approval/new revision semantics remain a separate design issue rather than a silent automatic recovery.

## 2026-10-11 follow-up: locked original RUN/evaluation skill proof fence

- **CA-1402/1405/1407/2407/2408, partial.** `LifeProcedureCatalog.record_verified_attempt` originally verified canonical RUN/GOALS/evaluation/creative bytes prior to its SQLite lock, allowing source state to be revised between validation and catalog proof insertion.
- **Production `4006ce3`:** bounded final source check within existing `BEGIN IMMEDIATE` validates original LIFE identity/completion, RUN job and result, original operation receipt/source chronology, link and independent typed evaluation *before* catalog/proof writes. This is descriptive knowledge only; no new skill privileges or automatic reinstatement. Validation of external asset bytes remains a separate source check.
- **Deferred regression `6601863`:** after the already valid creative bytes pass verification, a fixture revokes original receipt or downgrades RUN job; no procedure catalog/proof row may be written. Authored only, no tests or CI run.
