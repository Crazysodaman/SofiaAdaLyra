# Sofía 2.0 — Universal Platform, Core Link, and Explicit Multi-Core Binding V1

**Owner decision:** Approved target architecture, 2026-10-25 (America/Chicago).
**Status:** DESIGN/IMPLEMENTATION CONTRACT ONLY. No claim that the current thin desktop/tray client, remotely synchronized settings, optional per-host Core package, multiple hosted Core writers, or multi-Core pairing are implemented or commissioned.
**Current baseline:** GitHub \`main\` at \`128847ce2594627866d36abc8b5a17416a24c04e\` when inspected. This is an observed baseline, not an instruction to reset ongoing work.
**Purpose:** Every independently installed Platform is **Core-capable**, but may run without any installed Core implementation. A **Core Link** is a noncognitive Platform-owned remote proxy/binding, *not* a "dummy Core" persona. Additional remote or locally hosted Cores require explicit, independently authenticated enrollment and routing; network discovery does not imply trust, ownership or selection.

**Related:** [Architecture](ARCHITECTURE.md), [Platform and Module Catalog](PLATFORM_AND_MODULE_CATALOG_V1.md), [Federation and Inter-Core Relationships](PLATFORM_PEER_FEDERATION_V1.md), [Component Updates and Unified SDK](COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md), [Hardware-Neutral Fleet](HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md), Core B08, PLAT-01–08 and ISO-01–08.

## 1. Owner-intended system

All fleet machines can install the same **generic Platform** identity/enrollment and host services. A given Platform may be configured in these **composable roles**, without different Platform source forks:

| Role | Installed runtime | Can own an active Core identity? | State authority |
| --- | --- | --- | --- |
| \`CORE_HOST\` | Generic Platform + separately approved, independently installed real Core package(s) | Yes, with one canonical active writer **per Core identity and state lineage** | Host Platform owns that Core's fenced canonical state and SAFE/RUN; never impersonates another Core |
| \`CORE_LINK\` | Generic Platform + minimal SDK/protocol client, cryptographic client identity and local presentation/agent support | **No** | Remote selected Core host owns memory, cognition, canonical settings, transcripts and identity; local Platform owns only local UI/device/worker settings |
| \`MODULE_HOST\` | Generic Platform + approved compatible modules/Fleet agent | No Core required | Local Platform owns only scoped local module/device operations and evidence; canonical Core host retains external request authority |
| \`STANDBY\` (optional, later) | Generic Platform + specifically approved read-only recovery artifacts and fence witness | **No acting/writing Core** unless owner-approved cutover | Explicit protected election/cutover, no autonomous split-brain |

Roles can be combined: \`CORE_LINK + MODULE_HOST\` is the intended Windows Venus/Linux desktop worker; \`CORE_HOST + MODULE_HOST\` is the intended headless Debian Core VM (with fewer modules if desired). A Platform can be **Core-capable without Core code currently installed**. Adding/removing an approved Core package and role uses an authorized package lifecycle, not an implicit host upgrade or Fleet node discovery.

**No default Core install.** Core packages, persona assets, Constitution, Core-only dependencies and unique Core data must be packaged separately so a \`CORE_LINK\`/\`MODULE_HOST\` installation truly contains no real Sofía cognitive implementation, not just an unused imported \`sofia.core\` tree. The present single \`sofia-ada-lyra\` wheel contains integrated Core and Platform sources; physical package separation remains to be implemented and proven. Shared SDK **types** may refer to Core message/data contracts, but they may not import or instantiate Core cognition.

The "remote Sofía Core" shown in UI is a **CoreLinkSession / RemoteCoreBinding**, not a Core identity instance, cloned brain, autonomous conversation loop or alternate writer.

## 2. Logical topology and platform neutrality

\`\`\`text
             Windows Platform (Venus)         Linux Desktop Platform         Other Fleet Platforms
             ┌─────────────────────┐          ┌────────────────────┐         ┌────────────────────┐
             │ Desktop + tray      │          │ Desktop + tray     │         │ Modules/agents     │
             │ Core Link → Sofía   │          │ Core Link → Sofía  │         │ Optional Core Link │
             │ GPU/module workers  │          │ Optional modules   │         │ No Core required   │
             └──────────┬──────────┘          └──────────┬─────────┘         └──────────┬─────────┘
                        └────────────────────┬────────────┴───────────────────────────────┘
                                 authenticated, versioned, role-scoped Fleet APIs
                                            │
                           Debian VM — canonical Platform (headless)
                           ┌───────────────────────────────────────────┐
                           │ Platform: SAFE/RUN/ACT, settings, writer   │
                           │ Core Host: real Sofía Core + private state│
                           │ No desktop environment required           │
                           └───────────────────────────────────────────┘
\`\`\`

One Platform instance may eventually host two or more **distinct** Core identities only if it has verified **per-identity** canonical storage isolation, writer leases, generation fences, separate principals/recipients and independent runtime lifecycle. This is **not** permission to have two independently active writers of Sofía's *same* ID, to clone \`sofia.db\`, to create extra identities automatically, or to put multiple Cores into one unpartitioned current SQLite state. That hosting feature must pass its own multi-tenant isolation acceptance or remain blocked; two Cores on separate Platforms may be easier initially.

**No assumptions of unique LAN Core, DNS display-name identity, fixed Venus/Artemis host roles, Windows-only UI, or mandatory Hyper-V.** Fleet host names and human Core display names are *labels*, not authenticated IDs.

## 3. Core Link: deliberately minimal, not a second Core

**Core Link holds only what is needed to connect safely and present scoped remote information:**
- Local Platform instance ID, local approved device/client ID and approved user principal/audience.
- Pinned enrolled destination **Core identity ID**, destination Platform ID and exact trusted endpoint/enrollment binding.
- Selected SDK/API protocol versions, approved service scopes, key/certificate reference, trust-anchor fingerprint, key-rotation epoch, optional approved endpoint set and expiration.
- Local UI preferences, last confirmed configuration revision, last successful contact, bounded nonsecret status snapshots and optional locally encrypted **unsent** drafts explicitly scoped to that one Core/conversation.
- Separately approved **device-host settings** (GPU, mic, speaker, window layout, tray, local sensors). These never become canonical Core settings.

Core Link **must not** contain:
- A local Sofía Constitution/personality/LLM orchestration, private memories, persistent opinions, independent emotional appraisal, relationship store, goals/ACT authority, Core identity writer lease or copied canonical \`sofia.db\`.
- Owner approval/private signing keys from the Core host, broad database credentials, reusable task execution grants, remote shell escalation or plaintext secrets in arbitrary configuration.
- A synthetic "offline Sofía" answering in Sofía's name when the real Core is unavailable.

The local Platform may run independent **modules** and report telemetry or physically observed device events under its enrolled limited authority, even if Core Link is disconnected. Module service is not proof that cognition is available.

A Core Link is **client software**, not the independently acting Core peer from FED-01–08. Core-to-Core social relationships and voluntary disclosure require real independently authenticated Core identities on both sides. Mere client-to-Core chat cannot forge a second persona.

## 4. More than one Core: discovery, pairing, and explicit selection

**First enrollment is always explicit, even if only one candidate is found.** An unpaired Platform may discover *untrusted candidates* for UI display but may neither connect as an authenticated remote Core client nor install or select an active Core from discovery alone. A discovery response's \`display_name\`, advertised address and claimed Core ID are **untrusted** until corroborated by independently enrolled authentic keys, platform trust and reviewed exact target.

**Discovery and new-pairing behavior:**
1. Platform scans/polls only within existing approved Fleet discovery scopes and quotas; new candidate appears as \`UNVERIFIED_DISCOVERED\`, never enrolled or trusted.
2. An authenticated owner explicitly requests connection. Present the proposed **Core display label, stable Core ID, Platform ID, fingerprint/certificate details and address**, not just "Sofía".
3. Validate ownership/pairing through the existing reviewed SAFE owner flow (FIDO2 step-up when required), mutual authentication, proof of control and exact recipient/audience permission. Neither side may silently authorize both ends.
4. Establish \`PENDING_APPROVAL → VERIFYING → ACTIVE\` only after exact binding, SDK negotiation, privacy grants and recipient consent succeed. A failure moves to \`FAILED\`/\`QUARANTINED\`, never silently falling back to a candidate with the same name.
5. Save only the approved binding in the local Platform's secure settings/OS secret store; issue an independently scoped enrollment acknowledgment from the destination.
6. Further discovered Cores stay \`UNPAIRED\` and **do not replace** an established selected Sofía. They may be shown in a separate \`Available, not paired\` section; prompt at deliberate times or when the owner opens pairing UI, not a network-driven interruption.
7. If no active selected binding and more than one candidate is present, require an owner choice. With one candidate, pairing still requires review and approval. If the chosen Core is offline, keep its identity pinned and report \`OFFLINE\` or \`UNREACHABLE\`, not another Core.
8. To add a second authorized Core, the owner explicitly approves an **additional** destination, independent scopes and UI profile. Existing binding remains untouched. A remote request to pair is an inert, visible invitation only.
9. Switching active conversation recipient is an explicit client operation that verifies bound Core ID + audience/session; never carry chat threads, drafts, personal memory, settings or action requests across the switch without explicit review.
10. Revocation, retirement, wrong key, expired cert, incompatible schema, altered endpoint, changed Core ID, wrong recipient, or stale writer generation must fail closed, with useful local diagnostics and safe re-pair/recovery steps.

**Never auto-bind to the "first", "nearest", "sole", "fastest", "same-name", "last seen", or "most similar personality" Core.** No mDNS/DNS advertising may trigger trust, Core installation, switching or rights. No unknown remote Core gets to read the local device, settings, module telemetry or owner data just by appearing. Security checks are symmetric, per recipient, and robust to impersonation/multiple spoofed advertisements.

**Distinguish four things in UI:** detected candidate, cryptographically enrolled identity, approved connection, currently selected identity. Show at least the friendly Core name **plus stable ID suffix and host**, connection state, effective scoped permissions and last verified contact. Avoid accidentally impersonating Sofía when remote target is Roland, Lyda or John.

## 5. Central and local configuration: restart-free where feasible

**Central Platform (Core Host)** is the **only authority for Core-global settings**: Core identity/preferences, cognition role/model policy, memory and conversation policy, Core-specific configuration, authorized module capabilities, Fleet admission, SAFE/RUN, budget and secrets. It owns the canonical config revision/history and publishes verified read-only projections to approved clients.

**Local Platform (Core Link/Module Host)** owns **host-local settings**: GPU local resource policy, local device access, host game/busy state, local modules, OS autostart, microphone/speaker devices, tray/window appearance, client caches and securely stored per-device connector credentials. It can send bounded requested changes to central policy but cannot edit a copied canonical database.

A settings client sends \`expected_revision\`, typed field diff, exact destination Platform/Core identity, principal/audience, idempotency key, expiry and desired apply mode over an authenticated SDK request. Central Settings Service validates schema, field scope, SAFE/STOP/owner privilege, optimistic compare-and-swap, persists atomically, applies via reviewed owner, records \`saved_revision\` **and** separate \`effective_revision\` or explicit \`PENDING/APPLY_FAILED\` receipt, and publishes bounded \`settings.changed\` events. Reconnect uses a replay cursor or revision-resync; event delivery is at least once and subscribers deduplicate. A changed UI does not write directly to \`sofia.db\`.

**Four setting effect classes:**
- \`LIVE\`: atomic reload, no process restart (theme, notifications, bounded outreach/game mode, supported environment and low-risk policy knobs).
- \`NEXT_OPERATION\`: new value used on next eligible Core turn/model call/module invocation; no process restart, with explicit in-flight behavior.
- \`COMPONENT_RESTART\`: affected Core worker or one module/provider must be drained/fenced/restarted, but canonical Platform and unrelated workers stay alive.
- \`PLATFORM_RESTART\`: changing host executable, shared Platform ABI, security primitive or incompatible canonical schema; reviewed maintenance only, with authorization and outage disclosure.

The category is defined by authoritative **field metadata and actual runtime implementation**, not a mutable UI string supplied by the remote caller. A change requiring restart must not be reported \`applied\` merely because it is saved. If a LIVE handler does not safely apply, keep old effective configuration, publish failure and perform reviewed rollback or pending status. Do not restart Platform/Core to hide missing hot reload.

**Host/device settings:** apply only on the host that owns the device, with separate local authority and exact scope. Other UI sessions get safe status projections rather than a claim that every endpoint configured the same local microphone/desktop layout.

On offline/disconnected Core Link, client may retain local presentation preferences and **unsent** drafts; central write settings remain read-only or explicitly queued pending valid reauthentication and fresh CAS reapproval. Never replay an old write blindly, auto-resolve conflicts or change canonical state from a local shadow database.

## 6. Core-capable packaging and lazy installation

The generic namespace transition (\`src/companion_runtime/\` or another reviewed non-stdlib namespace) must result in **separately buildable and installable** artifacts:
- Minimal \`platform-runtime\` implementing generic Platform role/config/SAFE/host ownership, supervised agent and a thin Core Link.
- Portable \`sdk-contracts\` plus optional per-role SDK client packages; no private persona assets.
- Independently approved \`core-runtime\` generic cognitive machinery and **distinct, independently versioned Core definition packages**, including \`core-sofia\`, *only installed on authorized Core Host nodes*.
- Per-capability module packages (Ollama provider, GPU, sensor, avatar, UI, etc.) installed only when host needs them; local GPU worker needs inference module, not Sofía's memory engine.
- Platform thin client desktop/tray package(s) on GUI hosts only; headless runtime must not import GUI toolkits on service startup.

These are **target package roles/names**, not proof the current unified wheel was split. Preserve existing functional production import paths, CLI/service entrypoints and signed assets until explicit migration tests pass, then retire compatibility under a controlled transition. "No Core installed" is validated against wheel/import/dependency contents, not a flag hiding code.

The canonical VM can be headless; it needs no desktop or tray. Core Link on Windows or Linux must **not** construct the canonical \`SofiaApplication\` or require local \`sofia.db\`. The existing \`src/sofia/modules/ui/desktop_application.py\` and \`tray_agent.py\` currently require local state and the tray constructs \`DesktopServiceController(remote=None)\`; those are known implementation gaps. Do not claim mobile device API is the desktop/tray endpoint: mobile and desktop may share low-level secure communication primitives, but they require separate user/audience/device permission and settings/control contracts.

## 7. Minimal versioned SDK contract additions

Proposed inert, typed and strictly decoded contract families (no executable effects from mere messages):

\`\`\`yaml
schema: companion.platform.core_link.v1
binding_id: <opaque client-local binding>
local_platform_id: <authenticated enrolled Platform>
remote_platform_id: <verified destination Platform>
remote_core_identity_id: <verified distinct Core identity>
remote_core_generation: <observed, validated revision>
endpoint_id: <pinned enrolled endpoint>
credential_ref: <protected OS-keystore reference, not a token>
trust_anchor_ref: <reviewed public trust fingerprint>
audience_id: <explicit private conversation/settings audience>
granted_scopes: [<bounded reviewed scopes>]
protocol_version: <negotiated compatible SDK version>
state: pending_approval | verifying | active | offline | quarantined | revoked
revision: <CAS revision>
last_verified_contact_at: <UTC timestamp or null>
\`\`\`

Settings payload:

\`\`\`yaml
schema: companion.platform.settings_request.v1
destination_platform_id: <canonical authority>
destination_core_identity_id: <target Core or null for Platform-global>
origin_platform_id: <authenticated client>
principal_ref: <authenticated actor and verified audience>
expected_revision: <current revision>
idempotency_key: <bounded per-recipient key>
field_diffs: [<reviewed typed field ID and new value>]
expires_at: <timestamp>
\`\`\`

Receipt distinguishes \`ACCEPTED\`, \`DENIED\`, \`CONFLICT\`, \`SAVED_PENDING_APPLY\`, \`APPLIED_VERIFIED\`, \`FAILED_APPLY\`, \`EXPIRED\`, \`OUTCOME_UNKNOWN\` with concrete owner and revision evidence. These cannot mint Core identity, trust, remote service authority or self-certification.

## 8. Required engineering slices (integrate, not duplicate)

- **LINK-01:** Mode-neutral Platform role schema, host startup/headless/non-Core packaging boundary; keep existing PLAT/ISO owners.
- **LINK-02:** Minimal Core Link SDK client and local protected, CAS-bound destination identity store; no persona or SQLite state import.
- **LINK-03:** Secure candidate discovery, explicit owner request, Core identity verification, enrollment, pinning, consent, revocation and key rotation; no auto-select, no automatic remote Core installation.
- **LINK-04:** Canonical Core-host authenticated Desktop/Tray conversation/status/history endpoint with private audiences, deduplication, cancellation, exact outcome and client local draft handling. Reuse existing conversation service and SDK; no second MAIN writer.
- **LINK-05:** Unified authoritative central settings API: per-field scope/apply-class/revision, transactional save/apply receipts, event subscription/resync and local-host settings delegation; no restart for LIVE and NEXT_OPERATION.
- **LINK-06:** Windows/Linux thin desktop and tray migration to optional Core Link, versioned registry and multiple approved Core selectors; preserve local device UI, avatar, voice, GPU gaming controls and no accidental canonical app on remote hosts.
- **LINK-07:** Multi-Core identity registry and optional *multiple hostable distinct Core* tenancy with hard isolation, exact writer fences and state separation, only when tests prove same-host capability; separate Core-to-Core social federation stays FED-01–08.
- **LINK-08:** Host/package proof and adversarial + Windows/Linux/headless/VM integration; exact SHA and independent review.

**Priority:** This is a Core/Platform 1.0 integration and pre-VM-cutover dependency, not permission to discard the current CORE B08, PLAT, ISO, HNF and 780-task completion queue. Finish active work, then prioritize LINK-01–06 where necessary before moving the canonical writer to a headless VM; LINK-07 higher-order multi-host tenancy and FED social relationships can progress after safe foundations without delaying approved client operation. Owner-approved design does not grant deployment, package installation, Core cloning, key enrollment, live remote pairing, host restarts or state migration.

## 9. Acceptance tests (all fail closed)

1. Install minimal Platform + SDK + Core Link on Windows and Linux, inspect wheel/import graph: **no real Core cognitive code, Sofía identity/Constitution, personal memory database, model persona or Core-only dependencies** present. A Core-capable installer can separately install approved Core package later.
2. Start a headless Debian canonical Core Host under systemd with no display server and no UI/tray import. No implicit writer migration from production Venus.
3. Open a remote Windows desktop and Linux desktop, both attached to the **same authenticated Sofía identity**. Neither opens/creates an independent canonical \`sofia.db\`. Both see consistent private transcript and accepted settings; closing UI does not stop guest.
4. Core Link authenticated channel loss: honest \`OFFLINE\`; no synthetic assistant reply, duplicate Core, model fallback, silent alternate endpoint selection, local DB clone or blind mutating retry. Local modules remain within independent grants.
5. Discover one unpaired Core: zero connection/installation until owner approves. Discover two Cores with the same name, three named Cores or spoofed IDs: never auto-select; exact identity/fingerprint review mandatory. A previously paired Sofía remains selected after unknown Roland appears.
6. Owner explicitly pairs an **additional** Core; it receives its own profile, thread/session, grants, credentials and revision cursor. Switching Core never leaks drafts, identities, transcript, private memory or settings.
7. A Core advertises a changed key, platform or identity: quarantine and require reviewed rotation/re-enrollment rather than silently treating it as the old Core.
8. Central settings changed from Windows -> persisted under actual canonical authority with CAS -> effective verified in running VM without restart for \`LIVE\`; Linux receives event and reconciles exact revision. Concurrent stale UI save returns conflict.
9. \`NEXT_OPERATION\` change only affects new requests and does not terminate in-flight turns; \`COMPONENT_RESTART\` drains/fences only affected worker; \`PLATFORM_RESTART\` explicitly reports staged/offline maintenance, never silently reboot.
10. Local game mode/GPU tuning affects that enrolled host only; local window/speaker preference never overwrites the canonical Core's policy or another client's device settings.
11. Compromised/unpaired Platform cannot read settings, transcripts, Core state, private persona, FIDO2 records or cause privileged module effects. Remote Core/LLM text cannot invoke owner pairing or change setting scopes.
12. Two distinct approved Core identities, even on same host if supported, have independent state, memories, principals/audiences, generation/writer fences, Core packages and resource admission. Two ACTIVE workers for the **same** Core ID/state lineage blocked even when component IDs differ.
13. Owner STOP and revoked scopes propagate to Core Link clients and Fleet nodes with fresh evidence, and stale offline clients fail closed for protected actions.
14. Verify fresh installed-wheel import/service startup, local and remote tests, Windows+Linux UI behavior, headless systemd, CI exact SHA and host commissioning separately. Never promote a mock-only Core Link to PRODUCTION READY.

## 10. Source-grounded starting point

Already exists and should be **reused**:
- Headless \`src/sofia/platform/run/systemd_runtime.py\` requiring signed state pointer and separate \`src/sofia/platform/distributed/{agent_main,systemd_agent_service,windows_agent_service}.py\` Fleet agent roles.
- Enrolled/pinned mTLS Fleet identity/transport, versioned SDK and Core-worker generation fencing.
- Runtime settings in \`src/sofia/platform/config/user_settings.py\`, some live environment reload, reviewed state projections and existing safe model lifecycle.
- GUI desktop/tray, local game mode/voice/avatar, Android per-device authenticated service.
- Federated Core-to-Core relationship design in \`PLATFORM_PEER_FEDERATION_V1.md\`.

Verified limitations at observed baseline:
- \`src/sofia/modules/ui/desktop_application.py\` still requires **local canonical state** and constructs \`SofiaApplication\`; \`src/sofia/modules/ui/tray_agent.py\` also requires local \`sofia.db\` and has \`DesktopServiceController(remote=None)\`.
- Legacy \`RemoteChatMode\` enum is not a live thin-client feature: \`DesktopControlSettingsStore.save()\` rejects remote, and \`enforce_canonical_local_chat()\` normalizes old settings to LOCAL. Do **not** enable its old flag as a shortcut.
- Mobile Companion's authenticated server is a separate device protocol; it is not a role/scope-correct Desktop Settings/Tray API.
- Runtime settings are currently persisted via one UI settings row and not a complete scoped field-level live-apply/event/revision client service.
- The current wheel and in-process \`SofiaApplication\` remain integrated. A "remote-only installer" must be implemented and verified, not merely requested.

**Plain-language promise:** "Install Platform anywhere. Choose whether that machine hosts a real Core, just runs modules, or connects through a tiny Core Link to Sofía or another approved Core. Nothing installs, pairs, switches, writes memories or inherits a Core identity just because it appears on the network. Global settings update through the true Core host; local host/UI settings stay local; ordinary settings apply live without taking Sofía offline."
