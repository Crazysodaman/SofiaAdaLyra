# Sofía 2.0, independent module Batch 4

**Repository:** `Crazysodaman/SofiaAdaLyra`, `main`. **Inspected remote baseline:** `5881c82b9cd11dd8bdecedd3b72cee53c9d6ffb5`. This document is **development evidence**, not an independent readiness certificate.

**Module implementations in batch:**

| Module | Version | Capability | Operation profile | Source | Resource request (provisional, unmeasured) |
|---|---|---|---|---|---|
| MOD-IT-DEVOPS | 0.1.0 | `it.devops.assess_pipeline.v1` | ADVISORY | `src/sofia/modules/it_devops/analysis.py` | 50 millicores, 32 MiB RAM, 0 GPU |
| MOD-HOMELAB | 0.1.0 | `homelab.assess_services.v1` | ADVISORY | `src/sofia/modules/homelab/analysis.py` | 80 millicores, 48 MiB RAM, 0 GPU |
| MOD-REMOTE-ACCESS | 0.1.0 | `remote_access.review_session.v1` | ADVISORY | `src/sofia/modules/remote_access/analysis.py` | 50 millicores, 32 MiB RAM, 0 GPU |
| MOD-ENERGY | 0.1.0 | `energy.assess_ups.v1` | OBSERVE | `src/sofia/modules/energy/analysis.py` | 50 millicores, 32 MiB RAM, 0 GPU |

All capabilities have deterministic exact-field input validation and fixed-version structured output. Every output declares `evidence_class=supplied_unverified` and `effect=none`. They consume **existing** `sofia.sdk.contracts.SDK_PROTOCOL_VERSION` (1.0) and `sofia.platform.capability.model.Capability/CapabilityRequest`. None authenticates producers or callers. Actual request envelope authentication, generation fencing, STOP, profile/permission intersection, immutable package admission and resource leases **belong to the existing Platform and are not wired by this checkpoint**.

## Reuse rather than duplication

- Existing `modules/integrations/github.py`, `platform` DEV/EVOLVE facilities and authorized GitHub repository bridge stay the only actual Git operations. MOD-IT-DEVOPS consumes supplied CI/CD status; no source checkout, execution, deployment, or automatic receipt acceptance.
- Existing `modules/integrations/hyperv.py`, `modules/integrations/portainer.py`, `platform/ops/digital_twin.py`, and fleet resource/safety controllers are unchanged. MOD-HOMELAB reviews an explicitly supplied service graph, never invents Fleet trust, host placement or VM actions.
- Existing Platform SAFE identity/revocation and transport facilities remain sole owners of remote sessions. MOD-REMOTE-ACCESS accepts sanitized status evidence without connection, credential, token, personal principal ID or approval parsing.
- Existing Platform device/host authority owns hardware power, shutdown, driver and UPS admission. MOD-ENERGY accepts readings; it does not poll UPS hardware, predict guaranteed endurance or issue control signals.

## Operating and configuration contracts

- **Allowed hosts:** Windows/Linux MODULE_HOST or CORE_HOST; portable Python >= 3.12; no GUI, GPU, Core implementation, local SQLite state or internet required for these pure analyzers. CORE_LINK+MODULE_HOST hosting requires Platform connection and module pairing gates, not implemented here.
- **Configuration v1 (per-host, non-secret):** All analyzers accept `max_age_seconds`, integer 1–86400. Defaults: 300 for DevOps/Homelab/Remote Access, 120 for Energy. Remote Access also accepts `max_idle_seconds` default 900 (1–86400). Energy accepts `reserve_seconds` default 600 (1–86400). Validation rejects bool-as-int and out-of-range inputs. Live Settings reload is **not wired**. Platform must apply typed configuration atomically; no second central Settings service exists.
- **State:** None persisted. The module does not open `sofia.db`, logs, provider credentials or process handles. Caller owns snapshots and privacy retention. No module-owned migrations or recovery writes are required.
- **Permissions:** Caller must possess a suitable Platform-issued scoped, audience-correct observation/advisory grant. The module itself cannot grant scope. Host/device observation provenance must be verified externally; parsed booleans and statuses are merely *reported claims*.
- **Cancellation/timeouts:** Computation is synchronous over max 1 pipeline record, max 64 homelab services, max 1 remote session, or max 1 UPS record, with no external waits. Platform's cooperative cancellation and dispatch deadlines have not been exercised here; no effect can have occurred.
- **Retry/idempotency:** Inert, pure re-execution with same inputs and same `now` yields same result. External effect receipts are not emitted.

## Versioned maintenance profiles (specification pending signed artifact)

The target canonical shape is `sofia.module.maintenance.v1` from `platform/modules/package.py`. Each module's final immutable artifact digest, trusted publisher signature and full `ModuleMaintenanceProfile` linkage must be created by Platform PLAT-05 and are **deliberately not forged here**. Proposed immutable settings for later signed packaging:

| Module | Inert health probe | Failure classes | Automatic restart budget (proposal) | Quarantine | Owner attention | Rollback |
|---|---|---|---|---|---|---|
| DevOps | `it.devops.fixture_schema.v1` | Stale/mismatched CI digest, broken schema, dependency unavailable | 0 within handler | Platform policy, 3 repeated worker crashes | Missing artifact evidence or mismatch between runner and trusted source | Last signed package after Platform verification |
| Homelab | `homelab.fixture_graph.v1` | Cycles, duplicate IDs, unknown peer, cross-source topology, stale service | 0 within handler | Platform policy, 3 repeated worker crashes | Disconnected or inconsistent service inventory | Last signed package after Platform verification |
| Remote Access | `remote_access.fixture_review.v1` | Credential-bearing payload, revoked-session claim, missing MFA, stale session | 0 within handler | Platform policy, 1 secret-leak alert or 3 crashes | Sensitive input attempting access or remote session uncertain | Last signed package after Platform verification |
| Energy | `energy.fixture_ups.v1` | Missing/stale measurements, self-test failure, low battery, overload | 0 within handler | Platform policy, 3 repeated worker crashes | Battery/UPS unsafe or evidence source unstable | Last signed package after Platform verification |

- **No self-repair.** Diagnosis cannot restart host services, disconnect users, flip breakers or grant an approval. On crash, the existing Platform supervisor must isolate/quarantine the module. Thresholds above are proposals until Platform adopts them, not live policy.
- **Privacy:** output excludes arbitrary free-text, credentials and secrets; input schemas reject unknown fields. Module diagnostic telemetry must be scoped and redact source associations according to Platform policy.
- **Update/rollback:** No in-place module-controlled updates. Compatible API and schema 1.0 must be reassessed against exact signed artifacts; rollback across changed schemas needs separate Platform review. No declared module-owned persisted state to migrate.
- **Diagnostics:** only structured finding codes and observation refs; confidence limited to source-reported values. No self-signed release/evidence claims.

## Tests and readiness

- Local command: `PYTHONPATH=src python -m pytest -q test/test_module_batch4.py` (in isolated workspace) => **70 passed**.
- Covers input bounds, stale/future time, explicit malformed fields, release-gate evidence nuance, mixed-source topologies/cycles, peer outage vs reported service health, remote session revocation/MFA/privacy, UPS low battery/load/runtime, inert handlers and capability identity mismatch.
- Python 3.13 test runner with **test-only SDK/Platform stand-in classes**, not full project install; GitHub CI, real-host integration, API signature review, SF-15 cross-host interoperability, shutdown/isolation and signed package validation are **not tested**.
- **Readiness:** ALPHA (source implemented, not production-wired). No CA/GA/ML task gate upgrade inferred. Pending review by Codex shared SDK/Platform owner and independent release verifier.

## Integration request for Codex (shared code not changed)

Use existing `ReviewedAdapterFactory` and Platform capability registrations to accept signed, digest-verified and profile-scoped module bundles. Expose read-only, source-authenticated observation projections to these capability handlers only after principal/audience scoping, STOP check, latest component generation and deadline, API/schema version matching, and resource admission. Publish immutable `ModuleMaintenanceProfile` only with true source/package digests, and issue external results/receipts through Platform. Register module adapters in shared composition only after competing Codex work is stable. Do not make module instances choose host placement, authenticate themselves or claim an actual sensor/device identity.
