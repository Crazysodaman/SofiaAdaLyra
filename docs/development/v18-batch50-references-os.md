# V18 next 50: reference systems and operating-layer decision (CA-4001–4506)

Research reviewed 2026-10-13 against vendor/maintainer materials. Architecture review, not permission to import a dependency. Verify current versions, licenses, security advisories and deployment claims before any adoption.

## CA-4001 | Source-verified reference matrix
| System | Confirmed focus in maintainer docs | Candidate reuse for Sofía | Scope / missing proof |
| --- | --- | --- | --- |
| Letta | Stateful agents with persisted agent state and conversations | Memory/agent identity separation, not Letta's data store | Hosted/local parity, license and current release require independent pinning |
| OpenClaw | Channel/session and per-origin gateway patterns; further identity-link behavior **unverified** here | Review peer identity mapping, keep SAFE grants per principal/channel | Official identity-link semantics and exact version still need pinned primary source |
| Hermes Agent | Bounded curated MEMORY.md/USER.md, separate session search, skill authoring and explicit memory edits | Reviewed summaries + learned *candidate* procedures | Agent-managed writes are **not** Sofía approval; verify source/permission boundaries |
| OpenHands | Agent Server and UI separation; Docker-backed isolated agent task environments | Hephaestus isolated DEV worker and user-visible receipts | Never import its container as a trusted Fleet controller |
| Open-LLM-VTuber | Local hands-free LLM, voice interruption and Live2D avatar | Render/TTS latency and interrupt UX comparisons | Backend/frontends/assets have distinct licenses; no blanket license assumption |
| AIOS (agiresearch) | Agent operating-layer scheduling, memory/tool management over host OS | Interface and scheduler comparison | Is an agent framework, not evidence a new physical kernel improves Sofía |
| OpenDAN | Experimental personal assistant services over Docker/personal server | Portable owner-hosted deployment inspiration | Early-stage docs; long-term security and production support unverified |

Primary references: https://docs.letta.com/ ; https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/ ; https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/ ; https://github.com/OpenHands/OpenHands/blob/main/docs/architecture.md ; https://github.com/OpenHands/docs/blob/main/openhands/usage/advanced/custom-sandbox-guide.mdx ; https://github.com/Open-LLM-VTuber/Open-LLM-VTuber ; https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/releases ; https://github.com/agiresearch/AIOS ; https://github.com/fiatrete/OpenDAN-Personal-AI-OS/blob/main/doc/QuickStart.md . License and release cadence should be captured at exact immutable upstream commits before dependency selection. No unverified numerical maturity scores are assigned.

## CA-4002 | Letta-pattern boundary
Adopt only the conceptual separation of long-lived agent identity, owner-reviewed memory and multiple conversation/session projections. Existing `sofia.db` remains sole canonical state and sole writer. A new Letta daemon/database would create conflicting truth ownership; reject unless an independently accepted migration and exit plan proves a measurable benefit.

## CA-4003 | OpenClaw identity comparison
Evaluation must test shared actor versus channel-origin authority: authenticated principal, device credential, channel, audience, thread, expiration, revoked link and capability source. Two linked chats may share authorized history **without** inheriting privileged tool access. Hold off implementing `identityLinks`-style config until exact upstream contract, collision threats and owner consent are reviewed.

## CA-4004 | Hermes profile, transcript and skills
Separate tiny curated active context, owner-scoped searchable source transcript and procedural skill proposals. On correction or deletion invalidate dependent context and skill advice; no self-written memory or successful-sounding text can become independent fact. Store source, review receipt, audience and expiry with any candidate. Existing MEM pipeline is the owner, not an imported parallel memory store.

## CA-4005 | OpenHands and VTuber versus existing paths
Use OpenHands to check sandbox guarantees: untrusted task code, outbound network, mounted secrets, timeouts, resource caps, host escape and cleanup receipts. Use Open-LLM-VTuber to compare latency, interruption, expression timestamping and renderer crashes against Sofía voice/avatar. Estimate maintenance burden (licenses, update channel, bundled assets, attack surface) before replacement. Do not copy whole stacks absent measured gains.

## CA-4006 | AIOS/OpenDAN missing-feature test
Map their claimed scheduler, capability, memory, tool API, agent service and personal-server facilities against `RUN`, `SAFE`, `Fleet`, `MEM` and `application`. Only unmet *behavioral* requirements justify implementation. Duplicate schedulers, detached permission issuers and twin background workers are explicitly rejected.

## CA-4501 | Terminology decision
(1) OS kernel: privileged hardware/process/driver substrate; (2) **Sofía Operating Layer**: user-space orchestrated services on Windows/Linux; (3) appliance image: reproducibly provisioned distro and supervision for the same layer; (4) shell: optional desktop avatar/chat UI. They are not synonyms or evidence of intelligence.

## CA-4502 | Options and failure domains
| Option | Primary benefit | Additional failure domain | Decision |
| --- | --- | --- | --- |
| A Windows/Debian services | Current APIs, patch support, small operational delta | Existing host and OS | **Approved now** |
| B Dedicated Debian VM/appliance | Better process isolation and independent power lifecycle | Hypervisor, guest OS, storage migration, PKI | **Approved target, deferred cutover** |
| C Fullscreen desktop shell | Immersive interaction only | Desktop session/graphics drivers | Optional client, never state authority |
| D Agent orchestration framework | New abstraction or adapters | Second scheduler/permission plane | No wholesale adoption |
| E Custom kernel | No documented required capability gain | Driver/security/maintenance/boot risk | Out of scope |
No fabricated benchmark numbers: compare measured p95, idle watts, RAM, RPO/RTO and outage survival on actual hardware before choosing packaging.

## CA-4503 | User-space interface contract
SAFE alone authorizes effects; RUN persists bounded work; Fleet exposes authenticated read/act adapters; MEM supplies audience-filtered facts; sessions own timeline/continuity; developer/experiment APIs stay untrusted. Capabilities use typed principal, audience, effect scope, nonce, evidence reference, expiry, error and immutable receipt. Never let model prose mint rights.

## CA-4504 | Future appliance design
Debian 13 guest supervised by systemd, pinned signed wheel + hash-locked dependencies, encrypted volume and separate owner-controlled key recovery; reproducible image build and tested two-slot rollback before migration. Canonical DB and erasure journal must remain independently exportable, no fixed VM-only identity. Verify exact-once writer fencing plus offline restore and backup snapshots. This design does **not** indicate guest installation or deploy completion.

## CA-4505 | Kernel defer decision
Use standard Windows/Linux process, driver, hypervisor and container APIs for screen capture, USB serial, Fleet mTLS and isolation. A kernel proposal needs a documented unreachable required feature and independent security/driver maintenance budget; presently no such gap is proved. Reject new kernel development.

## CA-4506 | Outcome-based host selection
Test five user-facing outcomes: authenticated cross-device continuity, an independently completed LIFE project, safe Hephaestus isolated task, genuine voice/avatar synchronization and fenced Fleet recovery. Compare A with future B using paired measures and *signed* effect/host receipts, including failure injection. Choose the smallest stable layer; a sophisticated boot splash is not an acceptance criterion.

**End gate:** Twelve design/research topics reviewed with concrete decisions and unresolved primary-source checks. All original task acceptance remains subject to separate verification.
