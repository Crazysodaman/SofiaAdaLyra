# Module release-preparation handoff

**Branch:** `codex/module-documents`  
**Baseline:** `9384535bc9108acc7ef9f6c1cfbc0d46503fae07`  
**Scope:** module-owned source and local verification only

## Classification rules

- **MODULE CODE COMPLETE** means the existing bounded module contract has its
  required module-owned behavior, failure handling and local tests. It does not
  imply packaging, admission, certification or activation.
- **MODULE CODE PARTIAL** means a named design behavior is absent from the
  module implementation. A working advisory subset is still partial.
- **SHARED PLATFORM BLOCKED** means completion requires a Platform-owned
  interface or composition change. This is independent of module source status.
- **EXTERNAL CREDENTIAL BLOCKED** and **HARDWARE/G8 PENDING** identify
  acceptance that cannot be manufactured by a local test.
- **RELEASE CERTIFIED** requires the canonical exact-identity evidence chain.

## Per-module coding disposition

All optional handlers fail closed on bounded inputs and expose truthful
no-effect receipts. The missing-behavior column names the next production
behavior rather than repeating release evidence.

| # | Module | Coding status | Specific missing production behavior | Other blockers |
|---:|---|---|---|---|
| 1 | `RM-DESKTOP` | MODULE CODE COMPLETE | None identified in the current desktop/Core Link contract | Shared package/factory admission; Windows G8 |
| 2 | `RM-DISCORD` | MODULE CODE COMPLETE | None identified in binding, durable delivery and recovery contract | Shared package admission; Discord credential/live acceptance |
| 3 | `RM-AVATAR2D` | MODULE CODE COMPLETE | None identified in renderer, assets, wardrobe, hit-test and render-receipt contract | Shared package admission; visible-render G8 |
| 4 | `RM-VOICE` | MODULE CODE COMPLETE | None identified in TTS/STT, interruption and playback-receipt contract | Shared package admission; selected engine/device G8 |
| 5 | `RM-MOBILE` | MODULE CODE COMPLETE | None identified in pairing, revocation, scoped history, delivery and sensor contract | Shared package admission; Android credential/device G8 |
| 6 | `MOD-DEV` | MODULE CODE PARTIAL | Bounded patch-manifest review exists; authorized workspace execution, isolated test run and patch-bundle production are absent | Platform executor/cancellation/effect receipt |
| 7 | `MOD-RESEARCH` | MODULE CODE PARTIAL | Supplied-source comparison exists; authorized collection, ingestion, citation retrieval and network budgeting are absent | Provider/network grant; only optional module with reviewed process-factory implementation |
| 8 | `MOD-CREATIVE` | MODULE CODE PARTIAL | Storyboard review exists; generation-job lifecycle, managed assets, cancellation and truthful artifact completion are absent | Provider credentials; Platform effect/cancellation receipt |
| 9 | `MOD-VISION` | MODULE CODE PARTIAL | Detection-projection review exists; approved capture, redaction and raw-media retention lifecycle are outside this package | Platform capture grant; camera/display G8 |
| 10 | `MOD-DESKTOP-ACT` | MODULE CODE PARTIAL | Action-plan review exists; scoped target execution, pause/cancel and uncertain-effect reconciliation are absent | Platform RUN/STOP and host adapter; Windows G8 |
| 11 | `MOD-HOMELAB` | MODULE CODE PARTIAL | Service snapshot assessment exists; authenticated telemetry adapters and approved reversible actions are absent | Fleet identity, provider credentials, host G8 |
| 12 | `MOD-ROBOTICS-GAIA` | MODULE CODE PARTIAL | Leg IK simulation exists; gait controller, calibration, interlocks and motor receipt adapter are absent | Platform supervised effect; robot G8 |
| 13 | `MOD-TRAINS` | MODULE CODE PARTIAL | Route projection review exists; authenticated JMRI roster/power observation and interlocked commands are absent | JMRI credential/layout G8 |
| 14 | `MOD-GAMES` | MODULE CODE PARTIAL | Objective-state review exists; game detection, per-game adapters and resource scheduling are absent | Provider/game adapter and host G8 |
| 15 | `MOD-PRODUCTIVITY` | MODULE CODE PARTIAL | Task-dependency review exists; reminder/project/calendar artifact lifecycle and delivery receipts are absent | Platform durable effects; provider credentials |
| 16 | `MOD-ML` | MODULE CODE PARTIAL | Metric review exists; dataset lineage, training-job cancellation, held-out execution and candidate artifact lifecycle are absent | Compute admission and artifact/effect interfaces |
| 17 | `MOD-GENERALIZATION` | MODULE CODE PARTIAL | Transfer-trial review exists; versioned procedure execution and held-out cross-host trials are absent | RUN procedure interface and host G8 |
| 18 | `MOD-VWORLD` | MODULE CODE PARTIAL | Placement review exists; replayable scene persistence and deterministic simulation lifecycle are absent | Reviewed state namespace/interface |
| 19 | `MOD-MENTOR` | MODULE CODE PARTIAL | Rubric-evidence review exists; blind challenge-set runner and sanitized review exchange are absent | Evaluation-provider interface |
| 20 | `MOD-BROWSER` | MODULE CODE PARTIAL | Navigation-candidate review exists; authenticated browsing session, injection isolation, cancellation and download receipts are absent | Browser executor/network grant |
| 21 | `MOD-MEDIA` | MODULE CODE PARTIAL | Timeline review exists; media-job execution, managed outputs, cancellation and artifact receipts are absent | Media provider/tool interface |
| 22 | `MOD-DOCUMENTS` | MODULE CODE PARTIAL | Safe Markdown rendering exists; authorized file ingest/export, format adapters and durable artifact receipts are absent | Filesystem grant and artifact interface |
| 23 | `MOD-COMMUNICATIONS` | MODULE CODE PARTIAL | Delivery-receipt review exists; provider dispatch, cancellation and uncertain delivery reconciliation are absent | Provider credentials and RUN receipt interface |
| 24 | `MOD-SMART-HOME` | MODULE CODE PARTIAL | Supplied entity review exists; authenticated Home Assistant observation and approved service-call receipts are absent | Home Assistant credentials/hardware G8 |
| 25 | `MOD-CAD` | MODULE CODE PARTIAL | Plate simulation exists; general model import/export, constraint validation and artifact production are absent | CAD tool/artifact interface |
| 26 | `MOD-SENSORS` | MODULE CODE PARTIAL | Supplied-reading interpretation exists; enrolled-device acquisition, calibration and revocation handling are absent | Fleet/device identity; sensor G8 |
| 27 | `MOD-REMOTE-ACCESS` | MODULE CODE PARTIAL | Session review exists; credentialed session establishment, revoke/cancel and uncertain connection receipts are absent | Credential vault/RUN; host G8 |
| 28 | `MOD-IT-HELPDESK` | MODULE CODE PARTIAL | Evidence triage exists; ticket-provider lifecycle and approved remediation handoff are absent | Provider credential/effect interface |
| 29 | `MOD-IT-NETWORK` | MODULE CODE PARTIAL | Snapshot interpretation exists; authenticated collection and scoped diagnostic execution are absent | Host telemetry/RUN; network G8 |
| 30 | `MOD-IT-SYSTEMS` | MODULE CODE PARTIAL | System snapshot analysis exists; authenticated collector and approved remediation lifecycle are absent | Host telemetry/RUN; host G8 |
| 31 | `MOD-IT-CONTAINERS` | MODULE CODE PARTIAL | Inventory interpretation exists; authenticated runtime adapter and approved lifecycle actions are absent | Container credential/RUN; host G8 |
| 32 | `MOD-IT-STORAGE` | MODULE CODE PARTIAL | Volume analysis exists; authenticated collection and reversible storage action lifecycle are absent | Host identity/RUN; storage G8 |
| 33 | `MOD-IT-DATABASE` | MODULE CODE PARTIAL | Status analysis exists; credentialed probes, secret isolation and approved maintenance receipts are absent | Database credentials/RUN; host G8 |
| 34 | `MOD-IT-BACKUP-DR` | MODULE CODE PARTIAL | Recovery-evidence assessment exists; backup execution, immutable inventory and restore-verification lifecycle are absent | Backup credentials/RUN; restore G8 |
| 35 | `MOD-IT-SECURITY` | MODULE CODE PARTIAL | Finding triage exists; authenticated scanners, sensitive-evidence retention and remediation lifecycle are absent | Scanner credential/RUN; host G8 |
| 36 | `MOD-IT-OBSERVABILITY` | MODULE CODE PARTIAL | Supplied-event correlation exists; authenticated collectors, alert delivery and retention lifecycle are absent | Monitoring credential/effect interface |
| 37 | `MOD-IT-DEVOPS` | MODULE CODE PARTIAL | Pipeline assessment exists; provider-run observation, approval, cancellation and deployment receipts are absent | CI credential/RUN interface |
| 38 | `MOD-ENGINEERING` | MODULE CODE PARTIAL | Resistive-DC simulation exists; broader circuit/model validation and reviewed artifacts are absent | Tool/artifact interface; physical trial if acted upon |
| 39 | `MOD-ELECTRONICS` | MODULE CODE PARTIAL | ADC-divider analysis exists; device telemetry, calibration and supervised flash/control lifecycle are absent | Device identity/RUN; hardware G8 |
| 40 | `MOD-3D-PRINT` | MODULE CODE PARTIAL | Material estimation exists; slicer validation, printer queue, cancellation and physical outcome receipt are absent | Slicer/printer interface; hardware G8 |
| 41 | `MOD-ENERGY` | MODULE CODE PARTIAL | UPS snapshot assessment exists; authenticated UPS telemetry and approved control receipts are absent | UPS credential/device G8 |
| 42 | `MOD-AVATAR3D` | MODULE CODE PARTIAL | Joint-pose review exists; rig loading, animation/physics runtime and actual frame receipt are absent | Renderer factory; GPU/display G8 |
| 43 | `MOD-AVATAR-STUDIO` | MODULE CODE PARTIAL | Layer review exists; authoring/export pipeline, rig compatibility and managed asset lifecycle are absent | Artifact interface and owner asset review |
| 44 | `MOD-INTERACTION` | MODULE CODE COMPLETE | None identified in the attached offer parsing, consent/context and Core-response boundary | Parent package admission; presentation G8 |
| 45 | `MOD-VTUBER-BRIDGE` | MODULE CODE COMPLETE | None identified in owner pairing, localhost transport, protected token and owned-process contract | Parent package admission; VTube credential/application G8 |
| 46 | `MOD-WORKSHOP` | MODULE CODE PARTIAL | Experiment-plan review exists; guest lifecycle is implemented elsewhere but lacks a module package/factory and signed artifact handoff | Platform factory/admission; hypervisor G8 |
| 47 | `MOD-DIGITAL-TWIN` | MODULE CODE PARTIAL | Scenario comparison exists; versioned topology ingestion and replayable failure-model lifecycle are absent | Fleet topology contract |
| 48 | `MOD-KNOWLEDGE-LIBRARY` | MODULE CODE PARTIAL | Revision-index planning exists; bounded external index storage, retrieval and deletion lifecycle are absent | Reviewed state namespace and retrieval interface |
| 49 | `MOD-MEMORY-IMPORT` | MODULE CODE COMPLETE | None identified in candidate parsing, source revalidation and canonical promotion fencing | Parent admission; owner-reviewed protected-state G8 |
| 50 | `MOD-PROJECT-FORGE` | MODULE CODE PARTIAL | Manifest review exists; authorized project run, evaluation, cancellation and artifact delivery are absent | RUN/artifact interface |
| 51 | `MOD-FILE-WATCH` | MODULE CODE PARTIAL | Supplied-change summarization exists; approved-root watcher, overflow recovery and permitted trigger receipts are absent | Filesystem grant/watcher interface |
| 52 | `MOD-HOUSEHOLD` | MODULE CODE PARTIAL | Inventory review exists; Grocy/Mealie/Homebox sync and mutation receipts are absent | Provider credentials and RUN |
| 53 | `MOD-FINANCE` | MODULE CODE PARTIAL | Aggregate budget review exists; Firefly III sync, retention/deletion and transaction-import receipts are absent | Sensitive-data grant and provider credential |
| 54 | `MOD-DATA-ANALYTICS` | MODULE CODE PARTIAL | Numeric summary exists; CSV ingest, chart/report artifacts and large-job cancellation are absent | Filesystem/artifact interface |
| 55 | `MOD-CALENDAR` | MODULE CODE PARTIAL | Conflict review exists; provider sync, event mutation approval and invitation receipts are absent | Calendar credentials and RUN |

## Exact Platform/OpenCode interface handoff

These interfaces are absent or insufficient for module-owned completion. They
belong to the shared owner and should be implemented once, rather than recreated
inside 47 packages.

1. **Generic reviewed optional-process factory.** Platform currently provides a
   digest-bound isolated factory only for `MOD-RESEARCH`. A shared factory needs
   an explicit reviewed entry-point registry, authenticated bounded IPC, package
   digest/module/component/host/epoch binding, drain and forced-stop behavior,
   health observation, crash isolation and registration rollback. It must not
   dynamically discover package code.
2. **Cancellation/deadline contract.** `CapabilityRequest` has no canonical
   cancellation token or deadline. Network, generation, training, browser and
   device modules cannot implement deterministic cancellation against a shared
   interface until RUN exposes a fenced cancellation context.
3. **Effect receipt contract.** Advisory handlers can truthfully return
   `effect: none`; provider/device modules need a typed dispatch identity,
   idempotency key, uncertain-outcome state and independently reconcilable
   receipt. A module dictionary must not substitute for RUN evidence.
4. **Settings application contract.** Platform has lifecycle settings storage,
   but packages need a stable SDK-facing revision/apply/rollback callback and an
   effective-settings receipt. Modules must not write Platform settings tables.
5. **Health protocol.** The signed maintenance profile needs a shared probe ID
   and semantics bound to component, package digest, host and generation. An
   importable handler or self-report is not runtime health.
6. **Secret/provider binding.** Packages need opaque credential references and
   audience/host-scoped provider clients. Secret bytes must not enter module
   settings, manifests, logs or effect receipts.
7. **Artifact service.** DEV, Creative, Media, Documents, CAD, ML, Avatar Studio,
   Project Forge and Analytics need bounded read/write handles, digest receipts,
   retention and deletion. Direct filesystem access would bypass authority.
8. **Observation admission.** Vision, Homelab, Sensors, Smart Home and IT modules
   need authenticated source identity, freshness, audience and revocation in a
   common observation envelope before their existing analyzers run.
9. **Companion and attached packaging.** The current unsigned release kit covers
   exactly 47 optional identities. Platform/release owners must define immutable
   package identity and parent packaging for the five release companions and the
   three attached components; optional aliases must not be reused.
10. **Capability parameter schemas.** Owner review must select stable schema
    identifiers. The current Python validators are fail-closed behavior, but a
    string invented by release tooling is not an approved SDK schema.

## Local release boundary

The repository can prepare unsigned, digest-locked drafts for all 47 optional
sources after an owner-reviewed policy is supplied. It cannot safely generate
that policy, approve package IDs, create a production key, register factories,
write readiness evidence or perform host acceptance. The five release modules
and three attached entries still need shared package definitions.

No Core, Platform, SDK, protected state, physical host or production credential
was modified for this handoff.

## Verification on this branch

- Optional/package/security selection: **759 passed in 142.54s**.
- Companion selection: **1005 passed, 10 skipped, 14 failed in 234.02s**
  under the default sandbox. Every failure was local socket creation denied by
  the sandbox before the tested server could start.
- Exact cached failure rerun with sandbox network permission: all 14 Core Link
  and Mobile socket tests passed. Pytest also included 59 other cached tests;
  that run finished **68 passed, 5 failed in 173.09s**. The five failures were
  pre-existing live-Ollama integration probes and each reported that Ollama was
  unavailable; they are unrelated to module release source.
- Attached Interaction, VTube bridge and Memory Import selection: **609 passed
  in 34.21s**.

Skipped tests and unavailable provider probes are not release acceptance. No
test assertion failure attributable to the audited module source remains in
these selections.
