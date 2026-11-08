# AG-D027 | Owner-approved module rationalization implementation program

**Owner decision (2026-11-08):** Proceed with **all AG-D026 recommendations**, preserving necessary permission and physical-safety boundaries, including six consolidation proposals, all existing modules' individual refinement requirements, and evaluation of two conditional new modules. This **authorizes an implementation program and staged changes**, not automatic deletion of signed IDs, production installs or a completed certification verdict.
**Reference inventory:** [AG-D026 full 55-row audit](AG_D026_MODULE_CATALOG_RATIONALIZATION_AUDIT.md), [55-entry ownership matrix](../sofia2/MODULE_OWNERSHIP_MATRIX.md), [module catalog](../sofia2/PLATFORM_AND_MODULE_CATALOG_V1.md), [AG-D025 Portainer](AG_D025_PORTAINER_DOCKER_STACK_CONTROL.md), [AG-D006 live module settings](AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md).
**Workstream policy:** Do not divert active #201 Platform shakedown, conflict with open GUI/TUI/installer management PRs, introduce a second source of authority or delete original module identities while signed package/recovery plans depend on them. Each phase can land independently only after applicable tests and explicit release/merge review.
**Production verdict:** NO new module is production certified merely by this program. Current optional source analyzers generally implement no-effect OBSERVE/ADVISE/SIMULATE logic on supplied projections. Installed module permissions and Core identity remain unchanged until an independently approved effect deployment.

## Phase A | Inventory-preserving consolidation, code-backed first step

All six source-to-parent recommendations are **approved design targets**, but the active catalog's 47 optional IDs remain registered until a compatibility/retirement ceremony is verified.

| Source module | Planned home | Change scope | Migration acceptance |
| --- | --- | --- | --- |
| `MOD-GENERALIZATION` | `MOD-ML` transfer-evaluation profile | Reuse the transfer evidence evaluator without moving Core learning | Same result/error semantics for existing capability, signed package manifest, no duplicate state or permission |
| `MOD-CALENDAR` | `MOD-PRODUCTIVITY` calendar provider | Shared task and scheduling UI/data contracts, separate credentials and attendee privacy | Exact provider identity, no inherited invitation write, offline/duplicate-events tests |
| `MOD-PROJECT-FORGE` | `MOD-PRODUCTIVITY` workflow + `MOD-CREATIVE` artifact service | Shared project manager and renderer pipeline, durable jobs | Preserve historical project IDs/artifacts and correct verified outcome receipts |
| `MOD-FILE-WATCH` | `MOD-IT-OBSERVABILITY` provider + Platform event broker | Scoped filesystem source with authenticated source/consumer | No unscoped path/content leak; event is not effect grant; missed-event catchup |
| `MOD-DIGITAL-TWIN` | `MOD-HOMELAB` / `MOD-WORKSHOP` simulation profile | Reuse simulation and sandbox orchestration, optional isolated heavyweight worker | Simulation-only facts, no live calls, tested host/resource limits |
| `MOD-AVATAR-STUDIO` | `MOD-CREATIVE` / `RM-AVATAR2D` authoring | Shared media pipeline and rig/wardrobe validation, optional Studio frontend | Preserve identity/rig/assets/privacy, no second Core decision engine |

**Done in first source batch (not merged at authoring time):** `src/sofia/modules/catalog_consolidation.py` is a **read-only consolidation planner**, wired as a non-authoritative `consolidation_review` projection into `optional_release_audit.py`. No dispatch, signing, aliasing, unloading or source retirement occurs. Focused tests in `test/test_module_catalog_consolidation.py` check known mapping and fail-closed input. This is infrastructure for migration; **none of the six actual runtime/packaging merges is complete** until modules are rewritten and accepted.

**Next real code batch:** choose a source with easiest *correct* migration: Generalization → ML transfer review, preserving the old public `review_generalization` and exact registered capability until signed SDK compatibility tests and source-artifact inclusion pass. Never make a standalone signed module import another optional module by accident. Calendar provider integration follows only after independent privacy/permission review. Changes to `EXPECTED_OPTIONAL_IDS`, module manifests, package signatures and database migration must be a separate source-backed revision with comprehensive tests, not a hard-coded alias in an audit script.

## Hot-pluggable module socket contract (owner clarification 2026-11-08)

**Owner requirement:** The Platform is the permanent backplane. Optional modules are dynamically admitted/removed capability sockets: signed installation, activation, pause, disable, upgrade, and approved uninstall **must not require a Platform/OS reboot**. The Aegis GUI and headless TUI continue running and render module state after a bounded authenticated refresh without reopening Settings. A Core is a client; no Core is required for Platform module management.

**Verified source foundations, not yet installed-host certification:** `platform/modules/lifecycle.py` registers exact capabilities only on complete verified activation, unregisters them during pause/drain, requires an inactive module to update its package pointer and keeps removal records. `platform/modules/operations.py` records external worker start/stop outcomes and uncertain states; `process_worker.py` has an isolated Research worker. `test/test_module_lifecycle_v1.py` already exercises activate/pause/resume/disable/remove, update+rollback without implicit auto-activation, and cold-start non-resurrection of stale capability registrations. These are code/test coverage facts, **not proof** every optional provider currently supports hot swapping or UI event auto-refresh.

| Operation | Expected Platform behavior | Local module effect and boundary |
| --- | --- | --- |
| Discover/install/stage | Platform and unrelated modules stay running; no Core required | Only verified signed package is staged; new capability remains unavailable until approved activation |
| Activate/reconnect | Only the exact module worker is started, registered after independent health/identity proof | Revision/generation/permissions checked; no silent permission from discovery |
| Pause/disconnect | Immediately withdraw executable capability admissions; drain exact worker | Unrelated modules/Core/Platform remain alive; in-flight effects must reconcile |
| Disable | Retain signed package and permitted settings but remove any active capability | UI keeps read-only module details and policy/history |
| Upgrade/rollback | Fence old generation and suspend target worker; stage reviewed version and migrate state as approved | Restart/recreate that **one module worker** may be necessary; do not restart Platform/OS or auto-activate |
| Remove | Apply dependency/lease safety checks; unregister all of target capabilities; audited removal | Keep history, obey owner block/unblock and data retention; external resources (e.g. Docker stacks) remain untouched |
| Fault/reconnect | Runtime status UNKNOWN/DEGRADED during lost health, source restart or IPC outage | Re-sync snapshot/event cursor; no fake connected state from lifecycle ACTIVE |

**Honest limitation:** “No reboot” means no *OS/Platform* reboot for module lifecycle. A specific worker may restart for its own update or settings apply. OS drivers, device firmware, kernel interfaces and inaccessible legacy start-only integrations may need a separately described *component* restart or reviewed maintenance window; never promise live kernel/driver changes. Current legacy Portainer tool registration uses startup environment and is not a fully hot-enrolled signed module yet.

**Required cross-interface acceptance:** On installed disposable Windows/Debian hosts, run Platform + GUI + SSH TUI once. Install/activate/pause/update/remove a signed disposable module and a real provider connection. Verify live Installed/Available/Blocked/History, exact IDs, truthful health, no unrelated service restart, zero-Core operation, permission revocation, two simultaneous UI clients, and missed-event recovery. Repeat with pending settings edits and a worker crash. No signed/host evidence means NOT CERTIFIED.

**Read-only Portainer follow-on in this branch:** `it_containers/portainer_projection.py`, legacy adapter `stack_inventory_summary()`, and Core tool mapping in `integrations/capabilities.py` produce bounded allowlisted stack metadata rather than raw Portainer stack records. Tests cover secrets in omitted fields, endpoint mismatch and unknown health. This is **not** stack editing, independent module enrollment, HTTPS hardening or deployment authority. Portainer inspect/logs/container tools still require a separate secret-exposure audit before assigning wider Core permissions.

## Phase B | Flesh out existing release modules

| Wave | Catalog modules | Required acceptance before release |
| --- | --- | --- |
| B1 | RM-DESKTOP, RM-DISCORD | Neutral Aegis vs personal Workbench, source-backed settings, owner Inbox, principal/DM revocation, delivery and recovery receipts |
| B2 | RM-AVATAR2D, RM-VOICE, RM-MOBILE | Real frame/playback receipts, consent for capture and private assets, device pairing, network reconnection, no fabricated output |
| B3 | MOD-AVATAR3D and attached Interaction/VTube Bridge | Shared renderer/gesture contract, rig validation, actual frame proof, optional provider isolate, no duplicated Core personality |

## Phase C | Flesh out all 47 optional modules

| Wave | Catalog IDs (preserve even when consolidating) | Functional deliverable / major risk |
| --- | --- | --- |
| C1: Homelab & operations | MOD-HOMELAB, MOD-IT-CONTAINERS, MOD-IT-NETWORK, MOD-IT-SYSTEMS, MOD-IT-STORAGE, MOD-IT-OBSERVABILITY, MOD-IT-HELPDESK | Signed optional provider adapters: Portainer/Compose diff+approved deploy, DNS/router/tunnel inspect, machine/VM read-to-approved-effect, NAS metrics, correlated incidents. Protected trusted endpoints, exact rollback, and Core-free GUI/TUI. |
| C2: Safety, recovery, delivery | MOD-IT-SECURITY, MOD-IT-BACKUP-DR, MOD-IT-DATABASE, MOD-IT-DEVOPS, MOD-DEV, MOD-REMOTE-ACCESS | Read-only evidence first. Separate security findings from SAFE grants; backup external systems not canonical writer; DB migrations gated; Git/CI/source changes have separate exact approval and provenance. |
| C3: Personal workflows | MOD-PRODUCTIVITY, MOD-CALENDAR, MOD-PROJECT-FORGE, MOD-COMMUNICATIONS, MOD-HOUSEHOLD, MOD-FINANCE, MOD-DATA-ANALYTICS | Bound provider credentials, separate identity/privacy, no inherited spending/invite rights; Grocy/Mealie/Homebox/Firefly III; task/calendar/project non-effect proposals and grounded receipts. |
| C4: Documents & cognition tools | MOD-RESEARCH, MOD-KNOWLEDGE-LIBRARY, MOD-DOCUMENTS, MOD-BROWSER, MOD-MEDIA, MOD-CREATIVE, MOD-GENERALIZATION, MOD-ML, MOD-MENTOR | Distinct retrieval, external reference index, file render, web session, media playback, artifact creation, model evaluation and independent reviews, no duplicate Core autobiography. |
| C5: Physical / maker / simulations | MOD-SMART-HOME, MOD-SENSORS, MOD-ENERGY, MOD-ENGINEERING, MOD-ELECTRONICS, MOD-CAD, MOD-3D-PRINT, MOD-ROBOTICS-GAIA, MOD-TRAINS | Calibrated sensor/physical limits, host-pinned device leases, ESPHome/firmware, CAD/slicer data lineage, UPS/failsafe, JMRI physical proof with explicit owner-scoped approval. |
| C6: Human interaction / other | MOD-VISION, MOD-DESKTOP-ACT, MOD-GAMES, MOD-VWORLD, MOD-DIGITAL-TWIN, MOD-WORKSHOP, MOD-FILE-WATCH, MOD-AVATAR-STUDIO, MOD-AVATAR3D | Scope/consent and separated vision vs actions, game policies, virtual-only simulation vs real effect, lab isolation, bounded event source/authoring resources. |

Each module must have: reviewed package ID and signed manifest/digest; SDK/OS/host compatibility; narrowly named observation vs proposal vs effect capabilities; owner approval/STOP/revocation; provider identity and secret broker; state ownership; resource budget; live health/freshness; UI/TUI parity; disconnection and error handling; backups/restore where applicable; package update/revert; install/remove and owner no-reinstall; exact-sha targeted and broad CI plus installed-host evidence. None is automatically classified PRODUCTION READY.

## Phase D | Conditional new optional modules (evaluate, not mandatory)

1. **`MOD-IT-GAME-SERVERS`:** First implement game-server management as an independent *provider/profile* under `MOD-GAMES` / `MOD-IT-SYSTEMS` (RCON, SteamCMD, world save backup, update approval, health). Only promote to new signed standalone module after a separate privilege/lifecycle use case exists. Until then this is a conditional design idea, not a 56th active module.
2. **`MOD-IT-IDENTITY-DIRECTORY`:** First assess exact external Active Directory/LDAP targets and necessary read versus write authority. Keep separate from Platform SAFE/owner authentication. Only create standalone optional module with a real independent identity provider and approved protected operations. Until then this is a conditional design idea, not a 57th active module.

**No new identities simply for Portainer, Pi-hole, NPM, Cloudflare Tunnel, Hyper-V or Podman**. Extend existing IT-CONTAINERS, IT-NETWORK, IT-SYSTEMS or HOMELAB with separately scoped provider connections; promote only if independent lifecycle and threat model require it.

## Phase E | Release fences and progress truth

Status vocabulary per row: `DESIGN_APPROVED`, `SOURCE_IN_PROGRESS`, `CODED_UNTESTED`, `FOCUSED_TESTED`, `FULL_CI_VERIFIED`, `SIGNED_RC`, `HOST_ACCEPTED`, `PRODUCTION_READY`, `BLOCKED`. Each requires evidence, exact SHA and where applicable installed-host receipts. A PR being open is not a merge, tests not executed cannot be reported passed, a module's self-report cannot certify itself.

**Owner instruction:** Execute the recommendations *in batches*, minimizing risk, without waiting for OpenCode rate-limit resets, but never perform real host/Portainer/Docker/financial/physical actions or identity/state migrations without reviewed independent authority. New optional work should not reset the Platform 1.0 GO-LIVE readiness ledger.
