# AG-D026 | Full 55-module rationalization and functional gap audit

**Status:** SOURCE-BACKED DESIGN RECOMMENDATIONS, NOT OWNER APPROVED MERGES OR CODING ASSIGNMENTS.
**Baseline:** GitHub `main` inspected November 8, 2026; catalog `docs/sofia2/PLATFORM_AND_MODULE_CATALOG_V1.md`, `MODULE_OWNERSHIP_MATRIX.md`, `src/sofia/modules/optional_release_audit.py`, `optional_release_packages.py`, directory inventories for release and optional modules, and sample 0.1.0 candidate source. **Not** full line-by-line audit of each module, signed install or exact-commit runtime certification.
**Inventory:** 55 accepted catalog entries: **5 release channels + 47 optional identities + 1 attached submodule + 2 adapters**. Inventory identity is not equivalent to 55 independently deployable processes. Most optional candidate files sampled implement OBSERVE/ADVISORY/SIMULATE **over supplied, unverified projections**; the release-preparation code explicitly produces UNSIGNED, NOT_VERIFIED drafts. Existing V18 production-adjacent code in other directories may be deeper; no global code-empty conclusion is implied.
**Decision:** Do not add new required modules now. Reuse existing modules, restore clear ownership, and promote effect-capable implementations only through Platform SDK, signed package/maintenance contract, scoped authority and installed-host evidence. All merge/attach proposals below remain **unapproved**; preserve IDs, data and signed package compatibility until migration decision.

## 1. Per-entry review of all 55 modules

| Catalog ID | Recommendation | What to modify, flesh out, or consolidate |
| --- | --- | --- |
| `RM-DESKTOP` | **Keep, refine** | Separate neutral Aegis Control Center from personal chat/tray; live module/settings status and authenticated owner inbox; UI never writes canonical state. |
| `RM-DISCORD` | **Keep, refine** | Maintain separately revocable principal/DM binding; sent/delivered/seen receipts, privacy and outage recovery; share transport SDK with Communications. |
| `RM-AVATAR2D` | **Keep, flesh** | Finish rig/wardrobe/gesture/lip-sync and actual rendered frame receipts; VTube bridge stays provider; Core alone chooses expressions. |
| `RM-VOICE` | **Keep, flesh** | Harden real STT/TTS devices, interrupt/cancel, consent, playback evidence and text fallback; coordinate avatar visemes. |
| `RM-MOBILE` | **Keep, flesh** | Device pairing/revocation, offline queue reconciliation, notifications, optional consented sensors; do not create a second Core. |
| `MOD-DEV` | **Keep, clarify** | Source review, patch/test candidate and bounded build tools; real Git commits/merges/deploys remain approved Platform jobs; share pipeline with IT-DevOps. |
| `MOD-RESEARCH` | **Keep, clarify** | Source-grounded evidence, citations and freshness; Browser retrieves, Knowledge Library indexes, Documents renders; no duplicate truth store. |
| `MOD-CREATIVE` | **Keep, clarify** | Shared artifact generation pipeline for images/audio/writing; Avatar Studio uses the pipeline without duplicating personal identity or wardrobe choice. |
| `MOD-VISION` | **Keep, flesh** | Consented screen/window/camera perception, scope/revocation, evidence freshness and masking; separate from desktop actions and Sensors. |
| `MOD-DESKTOP-ACT` | **Keep, flesh** | Approved mouse/keyboard/application effects, verified screen target, interruption and undo; no inherited Vision capture grant. |
| `MOD-HOMELAB` | **Keep, narrow** | Own owner-specific topology, integrations and playbooks; reuse Platform Fleet trust, IT adapters, Workshop and Digital Twin rather than replacing them. |
| `MOD-ROBOTICS-GAIA` | **Keep, flesh** | Simulation before supervised calibrated actuators, host-pinned device leases, emergency stop, fault and interlock trials. |
| `MOD-TRAINS` | **Keep, flesh** | JMRI roster/turnout/sensor plans, layout graph and verified train movement; physical throttle/power require dedicated grants. |
| `MOD-GAMES` | **Keep, expand** | Gameplay assistance and performance-aware scheduling; consider separate game-server administration adapter/profile, not uncontrolled server admin. |
| `MOD-PRODUCTIVITY` | **Keep, expand** | Shared task/project/calendar workflow surface; defer Core goal ownership; host Calendar provider and Project Forge workflow after security review. |
| `MOD-ML` | **Keep, expand** | Model evaluation/experiments, dataset provenance, budgeted compute; absorb Generalization transfer-trial evaluator as a subprofile. |
| `MOD-GENERALIZATION` | **Merge candidate** | Fold its current transfer-trial evidence review into MOD-ML evaluation; Core retains native skill learning. Preserve ID as alias until migration reviewed. |
| `MOD-VWORLD` | **Keep, flesh** | Reproducible virtual scenes, entity physics and interaction evidence; separate real device effects from simulation; share simulation contracts with Digital Twin. |
| `MOD-MENTOR` | **Keep, clarify** | Independent rubric/challenge/review service with reproducible evidence; share evaluation schemas but stay independent of MOD-DEV and ML for review integrity. |
| `MOD-BROWSER` | **Keep, flesh** | Approved websites/session boundaries, injection-resistant page observations, downloads and consent; no automatic local desktop control grant. |
| `MOD-MEDIA` | **Keep, flesh** | Library indexing, local playback/transcode, provider accounts and receipts; media consumption distinct from Creative production. |
| `MOD-DOCUMENTS` | **Keep, flesh** | PDF/Office parse/generate/edit, format validation, versions and redacted exports; reuse Knowledge indexing and Creative artifacts. |
| `MOD-COMMUNICATIONS` | **Keep, flesh** | Email/message provider adapters, recipient scope, drafts, delivery receipts and revocation; release Discord/Mobile remain distinct user channels. |
| `MOD-SMART-HOME` | **Keep, flesh** | Home Assistant adapter and separate physical actuation scopes; locks/heating/security require fresh protection and verified state. |
| `MOD-CAD` | **Keep, flesh** | Parametric model/drawing formats, geometry validation, file lineage; integrates Engineering, Electronics and 3D Print via shared artifacts. |
| `MOD-SENSORS` | **Keep, narrow** | Physical telemetry drivers, calibration, timestamp/units, consent; hand off trustworthy evidence to ENVIRONMENT/Smart Home/Vision. |
| `MOD-REMOTE-ACCESS` | **Keep, flesh** | Authenticated one-target remote terminal/desktop sessions, consent/audit/expiry; no generic remote shell route around SAFE. |
| `MOD-IT-HELPDESK` | **Keep, flesh** | Incidents, diagnostic evidence, ticket/runbook preparation and owner-approved repair jobs; reuse Observability and Systems. |
| `MOD-IT-NETWORK` | **Keep, expand** | DNS/DHCP, routers, firewall, Cloudflare tunnels, reverse proxy and Pi-hole/adapters as profiles, not new modules by default; no implicit network writes. |
| `MOD-IT-SYSTEMS` | **Keep, expand** | Windows/Linux service, package, account and VM host observations; protected OS mutations, patch planning and identity-scoped receipts. |
| `MOD-IT-CONTAINERS` | **Keep, prioritize** | Make legacy Portainer provider a signed independent Platform module; add stack inspect/diff/validation, protected approved deploy, verified rollback and safe credentials (AG-D025). |
| `MOD-IT-STORAGE` | **Keep, flesh** | NAS/share/mount/SMART/filesystem health, capacity and recovery; no direct access to protected state or document content authority. |
| `MOD-IT-DATABASE` | **Keep, flesh** | Typed read-only database inventory/health and reviewed maintenance/migrations; never a second Aegis canonical DB writer. |
| `MOD-IT-BACKUP-DR` | **Keep, distinguish** | External workload backup/restore inventory and test drills; Platform PLAT-02 retains its own canonical recovery authority. |
| `MOD-IT-SECURITY` | **Keep, distinguish** | Host/network vulnerability and security findings, policy drift and incident triage; Platform SAFE still alone issues grants/trust. |
| `MOD-IT-OBSERVABILITY` | **Keep, expand** | Metrics/logs/alerts/correlation, freshness and incident triggers; share event feed with Helpdesk and optional File Watch. |
| `MOD-IT-DEVOPS` | **Keep, clarify** | CI/CD pipeline artifacts, build/rollout evidence and authorized deploy; MOD-DEV reviews source and code candidate, not duplicate release authority. |
| `MOD-ENGINEERING` | **Keep, flesh** | Electrical calculations, units, standards/version provenance and reviewed safety checks; export verified CAD/BOM artifacts. |
| `MOD-ELECTRONICS` | **Keep, flesh** | ESPHome/Arduino/firmware/board tooling, flashing/device consent, versioned electrical constraints and test records. |
| `MOD-3D-PRINT` | **Keep, flesh** | Slicer/printer provider profiles, material/temperature rules, job approval, verified print status; consume CAD artifacts. |
| `MOD-ENERGY` | **Keep, flesh** | UPS/battery/load/thermal observation and forecast; load shedding/shutdown as separately approved safety actions. |
| `MOD-AVATAR3D` | **Keep, flesh** | Optional high-resource 3D renderer, physics and actual rig/frame receipts; share body/expression contracts with 2D, not the renderer process. |
| `MOD-AVATAR-STUDIO` | **Attach/merge candidate** | Reuse Creative asset pipeline and Avatar 2D/3D rig/wardrobe validation; optional Studio authoring UI can remain separate if independently packaged. |
| `MOD-INTERACTION` | **Keep attached** | Shared 2D/3D/avatar input event interpreter and offer routing, not an independent service or Core reaction engine. |
| `MOD-VTUBER-BRIDGE` | **Keep adapter** | VTube Studio renderer provider under RM-AVATAR2D with pairing, version/health and frame receipts; no independent module process. |
| `MOD-WORKSHOP` | **Keep scoped** | Hephaestus/Lab scenario definitions and guest templates; Platform owns VM sandbox, approvals, secrets and physical effects. |
| `MOD-DIGITAL-TWIN` | **Attach/merge candidate** | Keep scenario engine as a Homelab/Workshop simulation profile unless isolation/resources warrant separate deploy; no live authority. |
| `MOD-KNOWLEDGE-LIBRARY` | **Keep, clarify** | External indexed documents/citations/revisions and permissions; shared source for Research/Documents, never personal Core autobiography. |
| `MOD-MEMORY-IMPORT` | **Keep adapter** | Owner-reviewed import candidate parsing tied to Core memory admission/Platform recovery; cannot write protected memory by itself. |
| `MOD-PROJECT-FORGE` | **Merge candidate** | Fold project workflow/tracking into Productivity and artifact execution into Creative; preserve distinct proposal/run receipts and ID migration plan. |
| `MOD-FILE-WATCH` | **Attach/merge candidate** | Make authorized directory-change observer a scoped provider to Platform events/IT-Observability; triggers remain governed jobs. |
| `MOD-HOUSEHOLD` | **Keep, flesh** | Grocy/Mealie/Homebox connectors, inventory/meal workflows, narrow household privacy and approvals; avoid redundant task engine. |
| `MOD-FINANCE` | **Keep, flesh** | Firefly III/budget projections and personal-finance privacy boundary; never share raw financial data with general modules or authorize transfers. |
| `MOD-DATA-ANALYTICS` | **Keep, share library** | Sandboxed tables, statistics, report/visualization outputs with sensitive-data scoping; reusable by Research/Finance without merging grants. |
| `MOD-CALENDAR` | **Merge candidate** | Offer calendar provider/profile within Productivity (and Communications for invitations); retain separate credentials, attendee privacy and write approvals. |

## 2. Highest-value consolidation candidates

| Candidate | Recommendation | Why / guardrail |
| --- | --- | --- |
| `MOD-GENERALIZATION` → `MOD-ML` | **Merge evaluation feature/profile, provisional** | Its current transferable-trials reviewer fits ML experiment/evidence evaluation; never move native Core personal learning, autonomous goal selection or protected identity into optional ML. Preserve ID aliases and history. |
| `MOD-CALENDAR` → `MOD-PRODUCTIVITY` | **Merge UI/packaging only after credential review** | Scheduling fits Productivity, but calendar provider credentials, event privacy and invitation sending need distinct per-provider grants. |
| `MOD-PROJECT-FORGE` → Productivity + Creative | **Merge workflow front end, keep RUN receipts** | Project lifecycle belongs in task/projects; rendering artifacts belongs to Creative/Documents; do not blur actual execution vs ideas. |
| `MOD-FILE-WATCH` → IT-Observability / Platform event broker | **Move to scoped source adapter** | Event fan-out is an existing Platform facility; path-watch permissions remain independent and triggers cannot auto-execute. |
| `MOD-DIGITAL-TWIN` → Homelab / Workshop simulation profile | **Consolidate simulation engine, conditional** | Simulated host dependency work should reuse one sandbox and scenario format; separate process still warranted for heavyweight independent simulation. |
| `MOD-AVATAR-STUDIO` → Creative + Avatar authoring | **Share authoring engine, optional separate Studio UX** | 2D/3D rig/wardrobe-specific edits need one source/preview lineage and Core-selected identity; no second avatar personality. |
| `MOD-RESEARCH` + `MOD-KNOWLEDGE-LIBRARY` + `MOD-DOCUMENTS` | **Share retrieval/index/artifact contracts, keep modules** | Research finds/evaluates sources, Knowledge indexes external references, Documents edits/exports; permissions, storage, freshness and workflows differ. |
| `MOD-DEV` + `MOD-IT-DEVOPS` | **Share build/artifact workflow, keep modules** | Code review/proposals and CI/deploy production effects have separate review and approval levels. |
| `MOD-IT-OBSERVABILITY` + `MOD-IT-HELPDESK` + `MOD-IT-SECURITY` | **Share incident evidence, keep modules** | Metrics triage, human ticketing and security enforcement/alerts should not share blanket administrative grants. |
| `RM-AVATAR2D` + `MOD-AVATAR3D` + Interaction + VTube Bridge | **Share rig/event/render receipt interfaces, do not merge renderers** | Different GPU/render engines and vendor adapters; attached Interaction and VTube Bridge inherit parent lifecycle. |
| `MOD-SMART-HOME` + `MOD-SENSORS` + `MOD-ENERGY` | **Share trusted telemetry, not write authority** | Physical actuation, passive sensors and UPS/load control have different device safety and privacy scopes. |
| `MOD-HOMELAB` + IT-* + Platform Fleet | **Site-specific orchestration over reuse, not merge** | Platform Fleet is mandatory trust/placement; Homelab stores site topology; IT modules supply provider-specific actions. |

## 3. Genuinely new entries? Use a high bar

| Idea | Decision | Justification and ownership |
| --- | --- | --- |
| **`MOD-IT-GAME-SERVERS`** | **Conditional NEW optional module candidate, not accepted yet** | If dedicated game-server administration needs independent RCON/SteamCMD/game save backup, patch windows, world lock/quiescence and permissions beyond gameplay `MOD-GAMES` or generic `MOD-IT-SYSTEMS`. Could begin as `MOD-GAMES` provider profile; split only when separately installable lifecycle/authority is demonstrated. |
| **`MOD-IT-IDENTITY-DIRECTORY`** | **Conditional NEW optional module candidate, not accepted yet** | External AD/LDAP/identity-directory audits and separately authorized user/group administration are distinct from Aegis owner identity and SAFE. Do not add until an actual external directory/authorization use case exists. |
| Docker/Portainer | **NO NEW module** | Existing `MOD-IT-CONTAINERS` has detailed [AG-D025](AG_D025_PORTAINER_DOCKER_STACK_CONTROL.md); make signed Platform provider module, not duplicate. |
| Pi-hole, DNS/DHCP, NPM, Cloudflare tunnels | **NO NEW module** | Add provider profiles to `MOD-IT-NETWORK` / `MOD-IT-SECURITY`; independent endpoint scopes and exact approval, no redundant networking module. |
| Hyper-V/Proxmox/VMware | **NO NEW module initially** | Use `MOD-HOMELAB` orchestration and `MOD-IT-SYSTEMS` provider adapter with Platform Fleet trust; split reusable hypervisor module only after genuine independent need. |
| Vaultwarden/Bitwarden integration | **NO NEW module initially** | Platform PLAT-03 already owns secrets and selective disclosure; optional owner-bounded external vault provider can be integrated without duplicating Platform credential authority. |
| Kubernetes/Podman | **NO NEW module initially** | Add separated provider adapters under `MOD-IT-CONTAINERS` with Kubernetes-specific API/policy and no inherited Docker grants. |

## 4. Requirements to flesh out uniformly

Every selected module must specify: exact parent/module ID; signed manifest/publisher/package version; capabilities split OBSERVE, ADVISE, SIMULATE and individually approved effects; OS/host/device/resource profile; provider configuration and least-privilege token storage; canonical namespace and migration contract; dependencies, installation/update/pause/uninstall and persistent owner block; side-effect and failure/unknown receipt; health/freshness with no fake VERIFIED; backup/rollback where stateful; safe UI/TUI parity, offline/NO_COLOR; privacy/consent boundaries, fail-closed STOP; acceptance tests with source SHA, actual signed install, host-specific observations, independent review. A sample `analysis.py` exposing a source-agnostic advisory handler is **not** a connector or production execution implementation.

**Work sequencing:** Do **not** bulk-merge or delete any accepted catalog IDs during Platform #201 shakedown. Start from source-backed acceptance in Platform PLAT-01..08, then release channels, then highest-use optional modules including IT-CONTAINERS, HOMELAB, IT-NETWORK, IT-OBSERVABILITY, HOUSEHOLD/FINANCE as specifically approved. Compare existing V18 code, provider wrappers and optional advisory stubs before writing new code. Protect one canonical writer and owner grants. This document changes no installation, modules, protected state, Fleet permissions, files outside design docs, or releases.
