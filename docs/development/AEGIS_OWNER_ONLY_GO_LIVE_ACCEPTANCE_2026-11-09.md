# Owner-only private Aegis | Platform 1.0 + Core 1.0 GO-LIVE acceptance overlay

**Owner decision:** 2026-11-09. **Status:** REQUIRED FOR BOTH PLATFORM 1.0 AND CORE 1.0 SHAKEDOWN / GO decisions, NOT IMPLEMENTED OR CERTIFIED BY THIS DOCUMENT.  
**Purpose:** Project Aegis is exclusively the owner's **private, personal-use** AI ecosystem on personally operated machines, VMs and enrolled Fleet Platforms. No customer billing, public model marketplace, multi-tenant product onboarding, publicly shared Core data, mandatory hosted AI subscription or commercial market readiness is required. 
**Source:** [Owner-only purpose and licensing policy](../roadmaps/AEGIS_OWNER_ONLY_SCOPE_AND_LICENSE_POLICY.md). Model reevaluation: [AG-D030 model landscape](../roadmaps/AG_D030_AI_MODEL_LANDSCAPE_2026-11-09.md).  
**Gate discipline:** This **refines existing acceptance criteria**, not a new Platform #201 row (remain 38), Artifact Library LIB-17 (remain LIB-01–16), a Core requirement CORE-41 (remain CORE-01–40), or an extra G8 checklist total. All overlay checks start NOT TESTED until independent exact-SHA evidence. It neither upgrades shakedown readiness nor authorizes real host state cutover.

**Security Profile C (2026-11-11):** An owner-established high-autonomy policy may permit signed automatic Fleet admission and reserves a future autonomous-migration flag. This adds no row, LIB scenario, Core ID, G8 criterion, or PASS. Explicit owner enrollment remains the default. Automatic admission is source-tested on disposable state only; installed-host evidence remains required. Autonomous Core migration is design-only, and the first real migration remains separately owner-approved. Permanent removal and trust-policy changes remain owner-only.

## 1. What "personal-only" means, precisely

- One authenticated owner and their separately authorized personal devices/Platform installations; an unlimited number of third-party/customer accounts is NOT the target product. Owner may still invite a scoped guest or use an intentionally approved external channel in the future; "one owner" is NOT permission to assume all microphone speakers, LAN peers, Discord users or remote agents are the owner.
- Cores are distinct identity/cognition instances; one canonical writer for each lineage. Sofía remains the same Core across provider, host, GPU, model and companion changes. Multiple distinct Cores never share or infer the owner's credentials merely from common hardware ownership.
- Owner's **personal** Hub/peer distribution is permitted when the exact artifact license and source policy allow contemplated copying; model weights and code may have different terms. Do not add a blanket commercial redistribution license prerequisite for private eligible model installations. Do not claim personal use legally overrides a prohibited download, copy, output use, voice impersonation or cross-host distribution restriction.
- Hosted/cloud providers can be optional owner-chosen integrations (unless a separate module explicitly requires free/no-cloud, e.g. AG-D032 Voice), but **no cloud account, subscription, billing service or telemetry service** can be necessary for the Core-free Platform install or baseline local Core continuity after approved local components are installed.
- Private production quality **does** require owner security, signed builds, verified Core/package provenance, SAFE/STOP, single-writer state, backup/recovery, isolation, network encryption, explicit Fleet enrollment, reliable services and real-installed-host test evidence.

## 2. Platform 1.0 gate: refine existing #201 rows, not add one

| POC ID | Existing row refinement | Required acceptance outcome |
| --- | --- | --- |
| POC-P1 | 01–03, 05, 07, 28–30 | On actual disposable Windows/Debian 12 installs, signed Core-free Platform + neutral SDK boots offline with no Core, voice, model, customer-account backend, billing system, paid inference or WAN login. Local operator can commission exactly one owner-controlled Platform identity. |
| POC-P2 | 08, 10–14, 17, 31, 37 | Owner-only permissions, default-deny untrusted/guest/revoked Fleet peers, no public listener by default; UI/TUI/CLI display real scoped owner/host trust, STOP and denial; sharing a LAN or identity label does not grant owner rights. Signed automatic admission is allowed only under an active owner-established high-autonomy policy and must display its policy, signer, attestation digest, and bounded initial scope. |
| POC-P3 | 17–20, 25–26, 28–29, 36–37; LIB-04/07/09/11/12/13 | Artifact Library and Model Manager distinguish code/weight/voice licenses, local personal use, noncommercial permitted use and permission for cross-device transfer. A synthetic *permitted-personal-only / no peer copy* model fixture may be installed locally after owner approval but **must not** automatically be offered to peers, exported to an unauthorized target or distributed publicly. Other signed synthetic distributable fixture may transfer after separate local approval. Do not test with unlicensed real weights. |
| POC-P4 | 30–38; LIB-03/08/14/16 | GUI/TUI/CLI/Hub show private/local mode and meaningful warnings for audience, license/transfer, WAN optionality and host trust. No SaaS or multi-tenant setup prerequisite, no hidden external telemetry by default, no guest-to-owner permission promotion. |
| POC-P5 | 19–20, 26–29; LIB-10/12/15 | Uninstall/reinstall, backup/recovery, offline/no-WAN and STOP preserve the local owner's Platform identity and unrelated Core-protected data; no unexpected publishing of inventories, memory, models, audio or private configuration. |

**GO rule:** Platform #201 cannot PASS merely because a feature flags says "private", nor because this document exists. Team E must provide exact released binaries and signed installed-host traces showing POC-P1..P5 within the existing row / LIB evidence, including negative cases. The currently untested/failed acceptance states remain unchanged.

## 3. Core 1.0 gate: refine existing CORE requirements/Batches

| COC ID | Existing Core acceptance location | Required acceptance outcome |
| --- | --- | --- |
| POC-C1 | CORE-01, 13, 15, 16, 30; B00/B01/B04/B08 | One persistent owner-facing Sofía identity/writer and protected memory lineage through restart, model switch and Core Link; no newly minted owner or second Sofía. |
| POC-C2 | CORE-02, 06, 11, 15, 18, 23; B01/B06/B08 | Owner authentication and audience scope enforced by Platform, not by voice, model response or Core's emotional/social judgment. A guest, peer model, remote UI, voice imitation or Discord channel does not become owner merely because this is a single-owner installation. |
| POC-C3 | CORE-13, 15, 20, 33, 35, 39, 40; B02/B05/B07/B08 | Role/model/provider swaps preserve private owner relationship and Core state. Free and lawful personal/noncommercial models are eligible through authorized modules after exact license, runtime, consent and artifact checks; no automatic all-model download, commercial-rights prerequisite or hidden cloud fallback. |
| POC-C4 | CORE-07, 11, 15, 24, 25; B04/B06/B08 | Personal private memory, adult/creative and voice/image assets remain audience-scoped with clear consent; routine Core logs and Artifact Library do not replicate protected content across Fleet or externally by default. |
| POC-C5 | CORE-16, 30, 35–40; B07/B08, G7-A | Core and owner conversation continue or degrade honestly when optional Pi, Goose, voice, image, noncommercial model candidates, third-party accounts or internet services are absent; signed approved Core/module actions remain governed. |

**Core 1.0 GO rule:** no compulsory voice, image-generation, adult-model pack, all-model download, Pi/Goose integration or mandatory paid provider is implied by this owner-only clarification. Their separate research TODOs remain deferred unless promoted independently. Core go-live requires the chosen *approved* baseline provider and real conversation path to work.

## 4. G8 real-host shakedown overlay (#129), not automatic production approval

Existing G8 checklist items about actual installed hosts, owner's conversation, remote Core Link and GO/NO-GO must **also** show all of the following:
1. Verify a locally owned Artemis VM/Core and Venus Platform/Core Link have exactly one intended owner and separate authenticated device/node identities. Third node stays out of scope until separately specified and enrolled.
2. On the approved disposable owner-profile fixture, validate no public module/model library listener, payment/account backend, unauthorized external logging, surprise WAN download or telemetry. Test disconnected WAN state and truthful unavailable behavior.
3. Show a signed synthetic **personal-use permitted / peer-copy restricted** data-model manifest can be installed for local owner use when allowed but is rejected for prohibited transfer; allowed synthetic model fixture still passes authorized enrolled-peer transfer. No actual restricted model weights are redistributed to satisfy the test.
4. Verify Core memory/voice/adult/private assets are not exported to Hub/guest/peer by default, and STOP/revocation/identity spoofing fail closed.
5. Preserve all G8 checks for genuine conversation, signed state recovery, no dual writer, negative receipts, soak and explicit owner approval for any actual protected-state migration.

**STOPPING RULE:** No GO, production activation, new auth grant, owner secret use or live migration is authorized by this document. Independent tester must report NOT TESTED/FAIL/BLOCKED until actual evidence is available.

## 5. Model-table change prompted by private-only clarification

The question "Do we need to relook at all AI models?" has a specific **yes**: selection and eligibility of legally permitted private/noncommercial models change, but performance/quality benchmarks and hardware fit DO NOT automatically improve. AG-D030 now needs a *second column* for **exact license and owner-only eligibility** (e.g. permitted personal use vs commercial-only prohibition vs legal unknown), and a separate field for cross-Fleet transfer rights. More permissive is not necessarily higher quality. Only an approved future on-host comparison can re-rank "best" candidates.

An exact source may allow private, noncommercial use while prohibiting some public/commercial deployments. Representative official anchors:
- Coqui XTTS-v2 [CPML license](https://huggingface.co/coqui/XTTS-v2/blob/v2.0.3/LICENSE.txt): explicitly enumerates personal hobby/private entertainment as noncommercial use.
- [F5-TTS weights](https://huggingface.co/SWivid/F5-TTS): code MIT, weights CC BY-NC 4.0. A legal personal-use candidate, not a general-public redistributable default.
- [Animagine XL 4.0](https://huggingface.co/iiYonko/animagine-xl-4.0): CreativeML Open RAIL++-M, not plain MIT.
- [NoobAI XL Vpred](https://huggingface.co/Laxhar/noobai-XL-Vpred-1.0): Fair AI Public License 1.0-SD; check exact usage and derivatives.
- [Pony Diffusion V6 XL](https://huggingface.co/neryK/Pony_Diffusion_V6_XL): modified Fair AI Public License with commercial service restrictions.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M): Apache-2.0.
- [RealVisXL V5](https://huggingface.co/SG161222/RealVisXL_V5.0): OpenRAIL++.

For every selected model, record exact release revision, weight digest, license, user scope, model family and quantization, backends, observed VRAM/quality, transfer policy and local/private test evidence. This does not create an automatic model-download or all-model go-live obligation.

## 6. Documentation / tracker registration

- Platform authoritative acceptance: \`docs/development/PLATFORM_1_0_ACCEPTANCE.md\` / issue #201.
- AG-D028 release acceptance: \`docs/roadmaps/AG_D028_PLATFORM_1_0_RELEASE_SPEC.md\` / LIB-01..LIB-16.
- Core features: \`docs/sofia2/CORE_1_0_PLAN.md\` and parent GO #120.
- Actual host: G8 #129.
- Main product intent: \`docs/roadmaps/AEGIS_OWNER_ONLY_SCOPE_AND_LICENSE_POLICY.md\`.
- Model shortlist/eligibility: \`docs/roadmaps/AG_D030_AI_MODEL_LANDSCAPE_2026-11-09.md\`.

**Evidence status as of 2026-11-09:** design accepted by owner, no production test claims, no mandatory feature promotions. Complete the existing Platform/Artifact Library release work before separately scheduled model/voice expansions.
