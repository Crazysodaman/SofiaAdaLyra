# Sofía 2.0: authoritative 55-entry module ownership matrix

**Decision:** All previous 41 catalog entries and all 14 newly identified entries are included as proposed Sofía 2.0 design requirements. The repository's working source is evidence of candidate code to reuse, **not proof of implementation or release readiness**. No production hosts, LLMs, approvals, or canonical state are changed by this document.

**Count:** 5 companion release modules + 47 optional module designs + 1 attached interaction submodule + 2 adapters = **55 entries**, of which **52 are separately scoped module designs** and 3 belong to existing parents. This is not a mandate for 52 processes: independently installable packaging is conditional on actual permission, state, dependency and resource boundaries.

## Layer ownership rules

| Layer | Owns | Never delegates |
| --- | --- | --- |
| **Core 1.0** | Identity, personality, emotional appraisal/journal, memory, personal preferences and convictions, self-directed goals, internal decision to gesture, romance/intimacy interests, boundaries, relationships and learning from experiences | Protected autobiography and internal personal judgments to an optional adapter |
| **Platform: PLAT-01–08 / SF-01–16** | Runtime, canonical writer, SAFE/STOP, RUN/ACT, evidence/trust, module profiles/manifest/update/maintenance, compatibility tests, resource forecasts and host recovery | Authorization to a module-generated string, untrusted sensor, LLM preference or private avatar art |
| **Companion RELEASE** | Desktop, Discord, 2D avatar, Voice and Mobile channel/presentation execution | Canonical conversation identity, emotional truth or permissions |
| **OPTIONAL** | Scoped domain skill or connector, independently disabled/updated if implementation supports it | Core cognition, memory, permission issuance or signed package certification |
| **SUBMODULE** | Inherited packaged capability with a parent; shared Avatar interaction interpretation is one instance | A second gesture-choice, consent or social reaction engine |
| **ADAPTER** | Provider integration or owner-supervised migration boundary within a parent lifecycle | Independent Core writer, privilege or execution supervisor |
| **CONTENT PACK** | Versioned gesture, scene, wardrobe and public/private asset sets under Avatar renderer | A separate personality, additional catalog module or implied execution permission |

## Complete inventory

| # | ID | Design name | Classification | Correct host or domain |
| ---: | --- | --- | --- | --- |
| 1 | `RM-DESKTOP` | Desktop | RELEASE | Standalone capability |
| 2 | `RM-DISCORD` | Discord | RELEASE | Standalone capability |
| 3 | `RM-AVATAR2D` | Avatar 2D | RELEASE | Standalone capability |
| 4 | `RM-VOICE` | Voice | RELEASE | Standalone capability |
| 5 | `RM-MOBILE` | Mobile | RELEASE | Standalone capability |
| 6 | `MOD-DEV` | Development | OPTIONAL | Standalone capability |
| 7 | `MOD-RESEARCH` | Research | OPTIONAL | Standalone capability |
| 8 | `MOD-CREATIVE` | Creative Studio | OPTIONAL | Standalone capability |
| 9 | `MOD-VISION` | Vision | OPTIONAL | Standalone capability |
| 10 | `MOD-DESKTOP-ACT` | Desktop Automation | OPTIONAL | Standalone capability |
| 11 | `MOD-HOMELAB` | Homelab | OPTIONAL | Standalone capability |
| 12 | `MOD-ROBOTICS-GAIA` | Gaia Robotics | OPTIONAL | Standalone capability |
| 13 | `MOD-TRAINS` | Model Trains | OPTIONAL | Standalone capability |
| 14 | `MOD-GAMES` | Gaming | OPTIONAL | Standalone capability |
| 15 | `MOD-PRODUCTIVITY` | Productivity | OPTIONAL | Standalone capability |
| 16 | `MOD-ML` | Machine Learning | OPTIONAL | Standalone capability |
| 17 | `MOD-GENERALIZATION` | Generalization | OPTIONAL | Standalone capability |
| 18 | `MOD-VWORLD` | Virtual World | OPTIONAL | Standalone capability |
| 19 | `MOD-MENTOR` | Mentor | OPTIONAL | Standalone capability |
| 20 | `MOD-BROWSER` | Browser | OPTIONAL | Standalone capability |
| 21 | `MOD-MEDIA` | Media | OPTIONAL | Standalone capability |
| 22 | `MOD-DOCUMENTS` | Documents | OPTIONAL | Standalone capability |
| 23 | `MOD-COMMUNICATIONS` | Communications | OPTIONAL | Standalone capability |
| 24 | `MOD-SMART-HOME` | Smart Home | OPTIONAL | Standalone capability |
| 25 | `MOD-CAD` | CAD | OPTIONAL | Standalone capability |
| 26 | `MOD-SENSORS` | Sensors | OPTIONAL | Standalone capability |
| 27 | `MOD-REMOTE-ACCESS` | Remote Access | OPTIONAL | Standalone capability |
| 28 | `MOD-IT-HELPDESK` | IT Helpdesk | OPTIONAL | Standalone capability |
| 29 | `MOD-IT-NETWORK` | IT Networking | OPTIONAL | Standalone capability |
| 30 | `MOD-IT-SYSTEMS` | IT Systems | OPTIONAL | Standalone capability |
| 31 | `MOD-IT-CONTAINERS` | IT Containers | OPTIONAL | Standalone capability |
| 32 | `MOD-IT-STORAGE` | IT Storage | OPTIONAL | Standalone capability |
| 33 | `MOD-IT-DATABASE` | IT Databases | OPTIONAL | Standalone capability |
| 34 | `MOD-IT-BACKUP-DR` | IT Backup/DR | OPTIONAL | Standalone capability |
| 35 | `MOD-IT-SECURITY` | IT Security | OPTIONAL | Standalone capability |
| 36 | `MOD-IT-OBSERVABILITY` | IT Monitoring | OPTIONAL | Standalone capability |
| 37 | `MOD-IT-DEVOPS` | IT DevOps | OPTIONAL | Standalone capability |
| 38 | `MOD-ENGINEERING` | Engineering and Electrical | OPTIONAL | Standalone capability |
| 39 | `MOD-ELECTRONICS` | Electronics and IoT | OPTIONAL | Standalone capability |
| 40 | `MOD-3D-PRINT` | 3D Printing | OPTIONAL | Standalone capability |
| 41 | `MOD-ENERGY` | Energy and UPS | OPTIONAL | Standalone capability |
| 42 | `MOD-AVATAR3D` | 3D Avatar | OPTIONAL | Companion/Avatar |
| 43 | `MOD-AVATAR-STUDIO` | Avatar Studio | OPTIONAL | Creative/Avatar |
| 44 | `MOD-INTERACTION` | Avatar Interaction | SUBMODULE | RM-AVATAR2D + MOD-AVATAR3D (also Virtual World) |
| 45 | `MOD-VTUBER-BRIDGE` | VTube Studio Bridge | ADAPTER | RM-AVATAR2D |
| 46 | `MOD-WORKSHOP` | Hephaestus Workshop | OPTIONAL | Homelab/Science |
| 47 | `MOD-DIGITAL-TWIN` | Digital Twin | OPTIONAL | Homelab/Simulation |
| 48 | `MOD-KNOWLEDGE-LIBRARY` | Knowledge Library | OPTIONAL | Research/Documents |
| 49 | `MOD-MEMORY-IMPORT` | Memory Import | ADAPTER | PLAT-02 + Core MEM admission |
| 50 | `MOD-PROJECT-FORGE` | Project Forge | OPTIONAL | Creative/Productivity |
| 51 | `MOD-FILE-WATCH` | File Watch | OPTIONAL | IT/Observation |
| 52 | `MOD-HOUSEHOLD` | Household | OPTIONAL | Home/Productivity |
| 53 | `MOD-FINANCE` | Personal Finance | OPTIONAL | Private productivity |
| 54 | `MOD-DATA-ANALYTICS` | Data Analytics | OPTIONAL | Research/Productivity |
| 55 | `MOD-CALENDAR` | Calendar | OPTIONAL | Productivity/Communications |

## Newly added code-backed boundaries

| Entry | Existing foundation or known evidence gap | Required owner boundary |
| --- | --- | --- |
| `MOD-AVATAR3D` | ui/avatar3d_renderer.py | 3D rig, full-body animation, physics and actual frame receipts |
| `MOD-AVATAR-STUDIO` | avatar/authoring.py; avatar/scene_editor.py | Wardrobe and scene authoring, layered rig compatibility, review of public/private assets |
| `MOD-INTERACTION` | interaction/; avatar/vtuber_hit_test.py | Pointer hit tests, user-offered virtual interactions and gesture event parsing; Core chooses its own response |
| `MOD-VTUBER-BRIDGE` | avatar/vtube_studio_bridge.py | Owner-paired external 2D renderer adapter; no independent personality or render claims |
| `MOD-WORKSHOP` | ops/workshop_provision.py; ops/workshop_policy.py | Isolated VM experiments, guest preparation and signed lab artifacts |
| `MOD-DIGITAL-TWIN` | ops/digital_twin.py | Hypothetical infrastructure dependency and failure scenarios, not live effects |
| `MOD-KNOWLEDGE-LIBRARY` | knowledge/service.py | External indexed references, bounded retrieval and source revisions, not autobiographical memory |
| `MOD-MEMORY-IMPORT` | memory/chatgpt_import.py; memory/chatgpt_migration.py | Reviewed foreign memory/conversation imports; candidate promotion stays with canonical memory owner |
| `MOD-PROJECT-FORGE` | life/draft_agent.py; creative/service.py | Artifact generation, run management, evaluation and delivery; Core owns personal goals |
| `MOD-FILE-WATCH` | filesystem/changes.py; filesystem/orchestrator.py | Approved directory-change observation and permitted workflow triggers |
| `MOD-HOUSEHOLD` | Specific domain provider unverified; generic integration framework exists | Grocy, Mealie, Homebox and consented inventory/meal workflows |
| `MOD-FINANCE` | Dedicated finance provider not yet verified | Firefly III and budget analysis with distinct sensitive-data grants; no unapproved transfers |
| `MOD-DATA-ANALYTICS` | Dedicated analytics provider not yet verified | CSV/structured data, statistics, reports and charts |
| `MOD-CALENDAR` | Dedicated calendar provider not yet verified | Provider event sync, conflict checks, meeting preparation and action receipts |

## Cross-cutting capabilities, without duplicate engines

- **Emotion and gesture:** Core retains the existing `emotion/`, `personality/`, `neuro/` and application expression-decision foundations. Core decides *whether and why* to express; Avatar 2D/3D, Voice, and their animation packs render *what actually occurred*, producing independent playback receipts. Never claim that text, desire, a proposal, a virtual simulation, or a queued gesture proves rendered action.
- **Gestures and adult presentation:** Large, varied everyday/non-adult gestures and separate opt-in adult-only animation packs belong to avatar implementations. Core owns voluntary affectionate/intimate preference and personal refusal; SAFE/Platform controls access, principal/audience scope, consent, redaction, and STOP. A simulated state does not establish biological sensation or blanket consent.
- **Interactions:** The interaction submodule parses authenticated user gestures and avatar hit regions and produces candidate offers. Core chooses its own reaction based on context and history; Platform determines authorized actions and outcomes.
- **Environmental evidence:** Weather from ENVIRONMENT/NWS, calibrated local weather stations via Sensors, approved Home Assistant observations via Smart Home and mobile sensors via Mobile all use existing trusted evidence/admission with freshness. No duplicate weather memory, camera authorization or claims based on disconnected sensor readings.
- **IT/Homelab/Fleet:** Reusable IT diagnostics cover network, system, containers, backup, databases and security. Homelab knows owner-approved topology; Platform Fleet owns identity, placement, maintenance and safety. Workshop runs sandboxed tests, Digital Twin produces *simulated* outcomes only.
- **Knowledge vs memory:** Knowledge Library indexes outside documents; Research finds sources; Browser interacts with websites; Documents creates/parses files. Imported memories are candidates to review, never unrestricted autobiographical writes.
- **Projects/skills/engineering:** Core owns the wish, chosen hobby and personal goals. Project Forge and domain modules own specific artifacts/actions through RUN/ACT and bounded permission. Engineering, 3D printing, Gaia, railroads and UPS/energy control require independently validated physical interlocks and supervised trials.
- **Personal data:** Household, Finance, Calendar and Productivity have distinct grants, storage and retention; no connector inherits another's authority.
- **External rendering:** VTube Studio is a renderer adapter, while 2D/3D renderer modules and rig-validated versioned art packs own assets; no competing body or identity.

## Certification and sequencing

Per module and applicable subcomponent require immutable manifest and maintenance profile, named operating profiles, version and dependency contracts, host/device and resource demands, source and scope evidence, trusted caller, effect receipts, installation rollback, fault-isolation tests, security/privacy review and original CA/ML/GA task crosswalk. Use the owner's separate readiness labels: **DESIGN, ALPHA, BETA, RELEASE CANDIDATE, PRODUCTION READY, BLOCKED**. This inventory records *DESIGN*, not Gate 4, installed functionality or independently verified releases.

**Development order:** OpenCode's already-active Core B00–B08 proceeds without interruption; Platform first (PLAT-01–08 and shared facilities), then Companion, then individually approved Optional modules. Existing V18 implementations must be audited and reused where valid rather than silently rewritten. Real-host effects and `sofia.db` migration need distinct approvals. See [catalog](PLATFORM_AND_MODULE_CATALOG_V1.md), [Core](CORE_1_0_PLAN.md) and [non-Core](NON_CORE_MODULE_PLAN.md).
