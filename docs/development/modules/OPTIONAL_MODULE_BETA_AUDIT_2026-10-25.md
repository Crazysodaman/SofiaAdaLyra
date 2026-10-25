# Sofía 2.0: 47 optional module BETA readiness, evidence-led source audit

**Inspected remote `main`:** `6d4687595fd0c648db18b1727b608e42ab4a82d8` (2026-10-25); **primary evidence:** actual optional source implementations plus Platform `package.py`, `adapters.py`, `lifecycle.py`, `operations.py`, `readiness.py`, `application/bootstrap.py`.

**Important:** This document is a developer source preflight, **not a Platform BETA certification or operator approval**. GitHub, local simulations and module-produced strings cannot promote a runtime module.

## Summary

- **47 / 47 catalog identities accounted for** (45 offline AST source files, 2 separate GitHub source inspections).
- **45 / 45 offline AST files** have valid source identity, declared version, capability ID, operation-profile metadata and bounded resources, without a flagged direct execution dependency. The two GitHub-only files have observed metadata but were not parsed locally by this tool.
- Source-level operation profiles (including the two GitHub inspections): **9 OBSERVE**, **27 ADVISORY**, **11 SIMULATE**. **Zero privileged execution profiles** were declared by these optional review candidates.
- **No capability ID collisions** observed across the locally parsed 45.
- Prior module-focused isolated regression: **613 passed** (from Batch 10 checkpoint); current preflight tests are recorded separately. These are not full integrated Platform tests.
- **BETA-verified: 0 / 47.** For all 47 the audit lacks authenticated staged/installed lifecycle evidence and a signed release package with its exact digest.

## Authoritative Platform BETA gate, checked in source

`sofia.platform.modules.readiness.evaluate_module_readiness` requires a `SignedModuleManifest` whose package identity matches a `ModuleLifecycleRecord`. Without release-candidate evidence, it returns BETA only for authoritative lifecycle states `STAGED`, `INSTALLED_DISABLED`, `PAUSED`, or `ACTIVE`. Any current failing/revoked evidence or quarantine may instead return BLOCKED. An ALPHA handler import alone cannot satisfy that gate.

`sofia.platform.modules.package.verify_module_package` cryptographically verifies exact artifact digests and Ed25519 signatures. The accepted package IDs use **lowercase dotted/dashed tokens**, while design IDs use uppercase `MOD-...`. The alias suggestions below are **not yet approved IDs**, and cannot be used to bypass package identity validation.

`sofia.platform.modules.adapters.AdapterFactoryRegistry` requires reviewed, digest-pinned factories; `ModuleOperationCoordinator` reconstructs only through this registry, evaluates compatibility, and requires RUN/SAFE authorization before activation. The optional source handlers have `capability_registrations()` but **do not thereby have registered factories**.

## 47-module contract inventory

| Module catalog ID | Platform ID proposal | Source capability | Profile | Source observation | BETA |
|---|---|---|---|---|---|
| `MOD-3D-PRINT` | `mod.3d.print` | `printing3d.estimate_material.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-AVATAR-STUDIO` | `mod.avatar.studio` | `avatar_studio.review_asset_layers.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-AVATAR3D` | `mod.avatar3d` | `avatar3d.review_joint_pose.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-BROWSER` | `mod.browser` | `browser.review_navigation_candidates.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-CAD` | `mod.cad` | `cad.simulate_plate.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-CALENDAR` | `mod.calendar` | `calendar.review_schedule_conflicts.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-COMMUNICATIONS` | `mod.communications` | `communications.review_delivery_receipts.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-CREATIVE` | `mod.creative` | `creative.review_storyboard.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-DATA-ANALYTICS` | `mod.data.analytics` | `data_analytics.summarize_numeric.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-DESKTOP-ACT` | `mod.desktop.act` | `desktop_automation.review_action_plan.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-DEV` | `mod.dev` | `dev.review_patch_manifest.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-DIGITAL-TWIN` | `mod.digital.twin` | `digital_twin.compare_scenarios.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-DOCUMENTS` | `mod.documents` | `documents.render_safe_markdown.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-ELECTRONICS` | `mod.electronics` | `electronics.analyze_adc_divider.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-ENERGY` | `mod.energy` | `energy.assess_ups.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-ENGINEERING` | `mod.engineering` | `engineering.simulate_resistive_dc.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-FILE-WATCH` | `mod.file.watch` | `file_watch.summarize_changes.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-FINANCE` | `mod.finance` | `finance.review_budget_aggregates.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-GAMES` | `mod.games` | `games.review_objective_state.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-GENERALIZATION` | `mod.generalization` | `generalization.review_transfer_trials.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-HOMELAB` | `mod.homelab` | `homelab.assess_services.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-HOUSEHOLD` | `mod.household` | `household.review_inventory.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-IT-BACKUP-DR` | `mod.it.backup.dr` | `it.backup_dr.assess_recovery.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-IT-CONTAINERS` | `mod.it.containers` | `it.containers.interpret_inventory.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-IT-DATABASE` | `mod.it.database` | `it.database.analyze_status.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-IT-DEVOPS` | `mod.it.devops` | `it.devops.assess_pipeline.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-IT-HELPDESK` | `mod.it.helpdesk` | `it.helpdesk.triage_evidence.v1` | ADVISORY | GitHub source observed; AST recheck pending | **Not verified** |
| `MOD-IT-NETWORK` | `mod.it.network` | `it.network.interpret_snapshot.v1` | OBSERVE | GitHub source observed; AST recheck pending | **Not verified** |
| `MOD-IT-OBSERVABILITY` | `mod.it.observability` | `it.observability.correlate.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-IT-SECURITY` | `mod.it.security` | `it.security.triage_findings.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-IT-STORAGE` | `mod.it.storage` | `it.storage.analyze_volumes.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-IT-SYSTEMS` | `mod.it.systems` | `it.systems.analyze_snapshot.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-KNOWLEDGE-LIBRARY` | `mod.knowledge.library` | `knowledge_library.plan_revision_index.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-MEDIA` | `mod.media` | `media.review_timeline.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-MENTOR` | `mod.mentor` | `mentor.review_rubric_evidence.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-ML` | `mod.ml` | `ml.review_classification_metrics.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-PRODUCTIVITY` | `mod.productivity` | `productivity.review_task_dependencies.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-PROJECT-FORGE` | `mod.project.forge` | `project_forge.review_artifact_manifest.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-REMOTE-ACCESS` | `mod.remote.access` | `remote_access.review_session.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-RESEARCH` | `mod.research` | `research.compare_claim_sources.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |
| `MOD-ROBOTICS-GAIA` | `mod.robotics.gaia` | `gaia.simulate_leg_ik.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-SENSORS` | `mod.sensors` | `sensors.interpret_readings.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-SMART-HOME` | `mod.smart.home` | `smart_home.review_entities.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-TRAINS` | `mod.trains` | `trains.review_route_projection.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-VISION` | `mod.vision` | `vision.review_detection_projection.v1` | OBSERVE | Parsed; source contract OK | **Not verified** |
| `MOD-VWORLD` | `mod.vworld` | `virtual_world.review_placements.v1` | SIMULATE | Parsed; source contract OK | **Not verified** |
| `MOD-WORKSHOP` | `mod.workshop` | `workshop.review_experiment_plan.v1` | ADVISORY | Parsed; source contract OK | **Not verified** |

## Blocking work, in required order

1. **Review package identity mapping** for all 47 approved catalog IDs. Do not quietly normalize the signed identity within an existing lifecycle record.
2. **Build real self-contained signed artifacts** with reviewed `SignedModuleManifest` and `ModuleMaintenanceProfile`, including exact capability schemas, immutable hashes, installation/upgrade/rollback and platform/resource constraints. Owner/trust-root approval is required; never fabricate signatures.
3. **Review adapter factories per package digest.** Implement the `ReviewedModuleAdapter`/`ReviewedAdapterFactory` contract with isolation and bounded health probes. No scanning source directories, dynamic loading of unknown packages, or bypassing RUN.
4. **Wire Platform lifecycle and permission checks** through Codex-owned bootstrap/composition paths in the coordinated Platform workstream. This audit will not alter those shared files or self-register production handlers.
5. **Stage authenticated packages on a consenting test host**; record canonical Platform lifecycle and compatibility. Preserve canonical `sofia.db` single-writer and STOP behavior.
6. **Run integration and fault-injection tests**: invalid manifest, revoked permission, stale source, wrong digest, missing factory, incompatible host, module crash, restart recovery, resource denial, package rollback, and Core continuation with optional modules absent.
7. **Re-evaluate each package using `evaluate_module_readiness`** with source SHA, package digest and real lifecycle. Promote only states the canonical evaluator reports as BETA; do not turn this Markdown into a certificate.

## Extra work by module family

| Family | Additional acceptance boundary |
|---|---|
| Finance, Calendar, Communications, Household, Knowledge | Distinct source authentication, privacy grants, retention and revocation; never transfer records between domains automatically |
| Vision, Smart Home, Remote Access, Desktop Automation | Target consent, owner-presence/game mode, source provenance; approved effects remain with existing privileged OS/IoT adapters |
| IT, Homelab, Digital Twin, Sensors, Energy | Fresh Fleet/environment evidence and failure isolation; never confuse synthesized/stale telemetry with real host status |
| Gaia Robotics, Model Trains, 3D Printing, Electronics, Engineering | Safety limits, interlocks and supervised physical-host tests before real effects; current reviewers do not actuate hardware |
| Development, Browser, Workshop, Project Forge | Existing reviewed executor/trust boundaries, prompt-injection resistance, run receipts and artifact provenance |
| Vision, Avatar3D, Avatar Studio, Virtual World, Games, Media | Reuse existing V18 subsystem ownership, asset provenance, renderer boundary and actual user-facing integration |
| Machine Learning, Generalization, Mentor, Creative Studio, Research, Data Analytics | Ground truth, evaluation holdouts, evidence provenance, no autonomous identity rewrite and no unreviewed training |

## Evidence limits and how to reproduce

- Machine-readable exact source preflight: `docs/development/modules/OPTIONAL_MODULE_BETA_PREFLIGHT_2026-10-25.json`.
- `src/sofia/modules/optional_release_audit.py` runs static AST analysis without importing modules or writing state.
- Run `PYTHONPATH=src python -m pytest -q test/test_optional_module_beta_source_preflight.py`.
- In a full checkout: `audit_optional_source_tree(Path.cwd())` returns all 47 source files as locally parsed; source visibility alone never turns on BETA.
- Remote first-batch files inspected by GitHub: `it_helpdesk/triage.py` Git blob `862c99990d743b9a9eea2868e1f1b23633aaef21`, `it_network/diagnostics.py` Git blob `d298f3b41ce56288006902ff001421d1f787f2b1`.
- Local source snippets for five widely spaced batches matched their observed GitHub blob hashes. Other local files were copied from the previous verified development snapshots; no assertion is made about uninspected concurrent commits.

**Verdict:** Existing functionality preserved; this audit prepares BETA integration, but **0/47 optional modules have evidenced BETA state**. Marking them BETA without signed packages and canonical lifecycle receipts would violate the approved readiness contract.
