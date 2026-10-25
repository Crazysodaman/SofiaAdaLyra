# Sofía 2.0 Batch 10: remaining 13 OPTIONAL module ALPHA reviewers

**Repository:** `Crazysodaman/SofiaAdaLyra` (`main`). **Design inventory:** 55 named entries, 47 optional modules.
**Scope:** This batch supplies review/simulation-only module-owned capability handlers for the remaining 13 optional names, not 13 full product implementations.
**Prior pass:** 34 source-level optional candidates from Batches 1–9. **After this batch:** 47/47 have candidate source code; none thereby earns production certification.

## Reviewed V18 boundaries

- DEV: existing `sofia.platform.dev` controls execution, worktrees, approvals, Git changes, and releases; this module only assesses a supplied patch manifest.
- Vision: `sofia.modules.vision` retains consented capture/interpretation and `desktop_control`; new `vision/projection_review.py` sees metadata only, never pixels.
- Avatar: `sofia.modules.avatar.authoring`, presentation and wardrobe contracts stay authoritative; these 3D/studio analyzers never change identity or assets.
- World: `sofia.modules.interaction.world_model`, world store, and editor retain all persistence and effects.
- Hardware: JMRI/track-power and other adapters, ML training, media, games and physical inputs remain separate, guarded authorities.
- Mentor: external feedback is data only, never a constitutional/personality or release gate override.

## Actual capabilities

| Module | Capability | Profile | Principal implementation |
|---|---|---|---|
| `MOD-DEV` | `dev.review_patch_manifest.v1` | `ADVISORY` | `src/sofia/modules/development/analysis.py` |
| `MOD-CREATIVE` | `creative.review_storyboard.v1` | `SIMULATE` | `src/sofia/modules/creative_studio/analysis.py` |
| `MOD-VISION` | `vision.review_detection_projection.v1` | `OBSERVE` | `src/sofia/modules/vision/projection_review.py` |
| `MOD-DESKTOP-ACT` | `desktop_automation.review_action_plan.v1` | `ADVISORY` | `src/sofia/modules/desktop_automation/analysis.py` |
| `MOD-TRAINS` | `trains.review_route_projection.v1` | `SIMULATE` | `src/sofia/modules/trains/analysis.py` |
| `MOD-GAMES` | `games.review_objective_state.v1` | `ADVISORY` | `src/sofia/modules/games/analysis.py` |
| `MOD-ML` | `ml.review_classification_metrics.v1` | `ADVISORY` | `src/sofia/modules/ml_evaluation/analysis.py` |
| `MOD-GENERALIZATION` | `generalization.review_transfer_trials.v1` | `ADVISORY` | `src/sofia/modules/generalization/analysis.py` |
| `MOD-VWORLD` | `virtual_world.review_placements.v1` | `SIMULATE` | `src/sofia/modules/virtual_world/analysis.py` |
| `MOD-MENTOR` | `mentor.review_rubric_evidence.v1` | `ADVISORY` | `src/sofia/modules/mentor_review/analysis.py` |
| `MOD-MEDIA` | `media.review_timeline.v1` | `SIMULATE` | `src/sofia/modules/media/analysis.py` |
| `MOD-AVATAR3D` | `avatar3d.review_joint_pose.v1` | `SIMULATE` | `src/sofia/modules/avatar3d/analysis.py` |
| `MOD-AVATAR-STUDIO` | `avatar_studio.review_asset_layers.v1` | `ADVISORY` | `src/sofia/modules/avatar_studio/analysis.py` |

## Profiles and host requirements

- **Operation profiles:** `OBSERVE`, `ADVISORY` and `SIMULATE` only, depending on module; no `EXECUTE_SCOPED` or `SUPERVISED` capability is implemented.
- **Provisional resource envelope per module:** CPU 75 millicores, memory 48 MiB, GPU 0 MiB; estimates, not measured caps or admission receipts.
- **Placement:** portable/stateless compute on Python 3.12+, OS-independent; no special device class required for pure projection evaluation.
- **Data:** supplied pre-redacted projection with opaque source and item references; no secrets, no personal/raw images, no real process/video content.
- **Dependencies:** `sofia.sdk.contracts.SDK_PROTOCOL_VERSION`, `sofia.platform.capability.model.Capability` and `CapabilityRequest`; their exact versioned runtime API must be integration-tested in the main repo.
- **Authority:** Platform authenticates provenance, principal, audience, authorization scope and source receipt before a capability can be admitted; a user-supplied string is not a grant.
- **Trust:** inputs are marked `supplied_unverified`. The result always carries `effect=none`, `action_authorized=False`, `data_persisted=False`.
- **Staleness:** timestamps must be timezone-aware; default validity 3600s, tunable 1–86400s. Stale/future inputs yield UNKNOWN and empty output results.
- **Source bounds:** each item has an exact schema, max 128 items, bounded IDs and domain-specific ranges. Duplicate item IDs are rejected.

## Module maintenance profiles (proposed, not signed)

| Field | Candidate policy |
|---|---|
| Support/version | `0.1.0` ALPHA; SDK protocol 1.0 |
| Health probe | Register-and-invoke deterministic valid/invalid/stale fixtures for each capability |
| Runtime retry | 0 automatic retries; return explicit UNKNOWN, not fabricated success |
| Quarantine | Platform-selected after repeated invalid contract/worker faults; never self-restart Core |
| Maintenance window | Owner approved service window only; do not interrupt conversation or gaming |
| Update | Platform verifies signed artifact/digest and profile compatibility in a staged slot first |
| Rollback | Platform atomically restores prior admitted artifact; no canonical data migration in this batch |
| Diagnostics | Schema violation counts, parser fault counts, stale-rate (do not log raw input) |
| Resource forecasts | Benchmark real peak RSS/CPU on each target host before allocation |
| Escalation | Trust failure, schema drift, unreviewed source, missing dependency and any attempted privileged effect |

## Interoperability and missing release requirements

- **Code reuse:** existing V18 owners were statically inspected before adding capabilities; they were not modified or replaced.
- **Interoperation:** deterministic data-only projections; no cross-module action triggers. A separate Platform caller must supply authenticated snapshots.
- **Missing:** signed `ModulePackageManifest` and `ModuleMaintenanceProfile`, trusted factory/registration, scoped grants, process isolation, capabilities collision audit, resource admission, effect receipts, full repo CI, host trials, security/privacy review and rollback.
- **Limits:** Vision does not interpret pixels; Desktop Automation does not click/type; 3D Avatar does not render; Media does not transcode; Creative does not create assets; DEV does not execute Git or OpenCode; Generalization does not prove general intelligence.
- **Claim boundary:** no Gate 4, BETA, RELEASE CANDIDATE or PRODUCTION READY claims. These are **ALPHA source implementations** only.

## Evidence

- Focused test: `PYTHONPATH=src python -m pytest -q test/test_module_batch10_all_remaining.py` in local isolated Python test fixture.
- Local SDK/Platform stand-ins exercise the real expected `CapabilityRequest` fields; this is **not** full runtime SDK/Platform integration.
- Combined regression: run prior isolated suite plus these tests with documented local stand-ins. CI and live acceptance remain pending.
- Source-only audit checks all new analysis files contain no direct database, filesystem, subprocess, socket, HTTP or OS-effect imports.
- Hardware/camera/renderer and developer execution requires fresh separate grants and host-specific trials; no implicit authority.
