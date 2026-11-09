# Project Aegis | Owner-only purpose, use scope and licensing policy

**Owner clarification:** 2026-11-09. **Status:** Binding product-intent design constraint; not authorization to install, execute, change trust policies, or migrate protected state.

## 1. Purpose

**Project Aegis is a private, single-owner AI ecosystem designed for the owner's personal use.** It is not being designed as a customer-facing SaaS, marketplace, commercial hosted service, public model distribution platform, or multi-customer product.

One owner can operate multiple Aegis Platforms, Cores, VMs, computers, authorized personal devices, local interfaces and enrolled Fleet nodes. Single-owner does **not** mean single-process, single-host, or single-Core. Support distinct personally owned Cores and one canonical writer per Core identity.

Source-code repository visibility (public vs private GitHub) is a separate decision. A public repository does not itself grant third parties access to running Aegis or make the owner's use a commercial offering. Do not infer public distribution plans from having a package installer or signed release artifacts.

## 2. Design consequences

- **Optimize for the actual owner:** home-lab hardware, hardware efficiency, private identity continuity, local model quality, expressive character and voice, and reliable owner-operated Windows/Debian nodes.
- **Keep Core-free Platform operation:** headless and UI-equipped personal machines, authorized Fleet connections, independent library Hub and peer transfers, and signed releases are still useful even when there's only one owner.
- **Private production quality is real production:** signed install/rollback, isolated modules, SAFE/STOP, credentials, verified software, permissions, crash recovery, data durability, audit and installed-host acceptance remain meaningful for the owner's actual machines. Do not downgrade security because this is not sold.
- **No unrequested commercialization features:** do not prioritize billing, tenant metering, customer management, public marketplace/CDN, commercial licensing SKU, seat counts, advertising, subscription systems, public onboarding, external telemetry or cloud dependence.
- **Default private:** store protected Core identity, memory, recordings, voices, adult content, generated images, home-lab secrets and logs locally with audience-scoped access; no automatic third-party sharing or Artifact Library replication of protected personal state.
- **Zero-cost voice requirement remains binding:** AG-D032 must provide complete local speech input/output without paid API or subscription. Other provider choices should remain free/local first, but this document does not retroactively prohibit optional owner-chosen paid compute or software elsewhere.
- **No automatic implementation or deployment:** this design clarification does not modify the Platform 1.0 #201 acceptance row count, AG-D028 LIB gates, owner's separate explicit host approvals, or any current coding priorities.

## 3. Free vs open source vs noncommercial use

Treat each component as having potentially different **code**, **model weights**, **voice pack**, **training/reference data**, **checkpoint**, **dataset**, **extension**, **codec** and **distribution** licenses.

| Claim | What it means for this single-owner project |
| --- | --- |
| Free price, local download | Good cost fit; license and use restrictions still need review |
| Open-source code, MIT/Apache | Often good implementation and packaging fit; do not assume model weights share that license |
| Noncommercial/personal-use checkpoint | **Eligible for evaluation** if owner use fits that exact license; do not exclude simply because commercial resale is prohibited |
| Copyleft/GPL | May be usable locally; external provision/distribution and packaging impose conditions that still need review |
| Redistributing downloaded model/voice between personally owned Fleet nodes | Must review exact terms and rights; local copying for own use and distribution are not legally interchangeable in all licenses/jurisdictions |
| Public release/mirroring of model weights | Not requested; disallow by default unless separately approved and permitted |
| Voice cloning, protected identities, mature images | Consent, laws, audience security, license and data protection still apply; personal use does not remove those obligations |

Avoid universal legal claims that private/noncommercial use always cures licensing problems. For a license that forbids a proposed use, mark the candidate **ineligible**, regardless of zero price. Record the exact source, revision, governing terms and any obligations before Aegis packages or peers the asset. Do not silently treat model artifacts as signed executable packages or publishers as trusted solely because they're on a model Hub.

## 4. Existing research to interpret under this scope

- **AG-D005 Model Manager:** personal-use and noncommercial models become eligible candidates if their exact terms permit. Keep role assignments, VRAM budgets and allowed sources independent from Core identity.
- **AG-D028 Artifact Library:** owner's personal LAN Hub and enrolled peer transfer, not a public model CDN; enforce license and independent host authority. A local download never authorizes a third-party redistribution.
- **AG-D029 Pi/Goose/inference:** select on safety, quality, CPU/GPU efficiency and ability to run locally, rather than ease of commercial product packaging.
- **AG-D030 model landscape:** do not systematically prefer commercial-use models; include personal-use roleplay/adult, art and image checkpoints if permitted and technically suitable.
- **AG-D031 Fleet efficiency:** make best use of Artemis, Venus and separately specified third machine, rather than designing for anonymous customers.
- **AG-D032 Voice:** zero subscription requirement stays; permitted noncommercial voice checkpoints are valid candidate options when rights match owner's private use. Keep protected Sofía reference/embedding private, with independently verified voice consent and no impersonation.

## 5. Practical decision policy

1. Select candidate on quality and technical suitability.
2. Confirm exact pinned weights, dependency licenses and personal-use rights.
3. Check whether importing, modifying, storing, backing up, or transferring on the owner's nodes is permitted.
4. If not, use only an allowed local path or an alternative free model; never pretend rights exist.
5. Maintain security, safe consent, consented audio/video capture, explicit activation and real-host acceptance.

**Scope statement:** Build the best dependable private Aegis for one owner across their own trusted personal Fleet. Do not optimize for hypothetical external customers, but do not waive engineering discipline.
