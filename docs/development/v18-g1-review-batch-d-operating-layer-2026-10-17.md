# G1 original-requirement design candidates, group D (5 tasks)

**Status: G1 reviewer action still pending.** These are architecture decisions consistent with existing owner direction, not an independent review or authorization to deploy.

## CA-4501: Distinct OS and operating-layer terms

**Original:** **CA-4501 [DESIGN/RESEARCH]** Resolve terminology in an architecture decision record: **operating system kernel**, **user-level agent operating layer**, **dedicated Sofía appliance OS image**, and **desktop shell/launcher** are separate proposals with different obligations.

**Chosen design and rationale:** Operating-system kernel means the privileged Windows/Linux resource and driver substrate; user-level Sofia operating layer is the existing SAFE/RUN/Fleet/Memory/session application services above it; an appliance OS image is a reproducible Linux deployment and supervision package of the SAME runtime; a desktop shell is a UI/launcher client. An Ollama model is one replaceable cognitive provider, not a kernel, agent authority or second Sofia. Every proposal must name target, patch/boot responsibility, storage and private data boundary, rollback and independent operation status.

**Remaining independent proof:** Independent review must verify runtime/UI/architecture docs and deployment labels use these terms consistently. No new kernel, VM, driver or host migration is authorized by terminology.

**Source references:** docs/development/p0-architecture-release-audit-2026-10-10.md; docs/development/companion-autonomy-contract.md; src/sofia/application/bootstrap.py

**G1 acceptance:** OPEN until the original requirement is independently reviewed.

## CA-4503: Thin typed operating layer

**Original:** **CA-4503 [DESIGN/RESEARCH]** Specify **Sofía Operating Layer** as a set of existing SAFE/RUN/Fleet/Memory/session service interfaces with strict authority and resource budgets, rather than a bootable custom kernel. Audit against AIOS to avoid rebuilding its scheduler abstractions unnecessarily.

**Chosen design and rationale:** Define no second orchestration engine. The public service boundary composes authenticated conversation session retrieval, reviewed MEM recall, asset-scope inspection, existing goal/RUN job and GOALS receipt lookup, SAFE/ACT grants, Fleet mTLS tools, and application lifecycle/health. Minimal envelope fields: principal, audience, session, request_id, exact operation version, purpose, observed_at, expiry, nonce/replay key and explicit allowed capability. Outcomes have enum status, original typed evidence reference, partial/stale flag and read-only projection freshness. Auth for every consumer is independent of content recommendation; role switches do not alter rights.

**Remaining independent proof:** Review each existing endpoint and avoid accidentally allowing an offline cached client to mint canonical writes. Accept only versioned API+schema and negative wrong-session/wrong-principal/expired-scope/replay tests. Treat the above as a design spec, not implementation proof.

**Source references:** src/sofia/application/bootstrap.py; src/sofia/capability/gateway.py; src/sofia/goals/evidence.py; src/sofia/run/work.py; src/sofia/social/

**G1 acceptance:** OPEN until the original requirement is independently reviewed.

## CA-5401: Option A approved today

**Original:** **CA-5401 [DESIGN/RESEARCH]** Record architecture decision: **Option A approved now** = user-level Sofía Operating Layer on established Windows/Linux, one canonical identity, SAFE/RUN/Fleet, Memory, session APIs, permission boundaries and typed platform capability drivers; don't create a custom kernel.

**Chosen design and rationale:** The currently approved platform is standard Windows/Debian user-space services, maintaining one canonical identity, sofia.db, configuration, Constitution, SAFE/GOALS/RUN/Fleet writer and independent model routing. Typed OS adapters expose Windows desktop/Hyper-V, Linux services, Fleet, JMRI and Hestia only through authenticated governed capabilities. Keep application logic independent of OS and graphics; desktop is a client. Do not build a custom kernel or run duplicate autonomous daemons to simulate progress.

**Remaining independent proof:** Confirm continued owner approval and trace actual platform-specific drivers; no code promotion is implied by recording an architecture decision.

**Source references:** docs/development/p0-architecture-release-audit-2026-10-10.md; docs/development/companion-autonomy-contract.md; src/sofia/application/bootstrap.py

**G1 acceptance:** OPEN until the original requirement is independently reviewed.

## CA-5403: Deferred option B appliance

**Original:** **CA-5403 [DESIGN/RESEARCH]** Record **Option B approved but deferred** = dedicated reproducible Linux appliance image after baseline acceptance. Appliance packaging must reuse existing application/identity, never fork a second constitution/brain or active database.

**Chosen design and rationale:** Owner-approved concept, NOT a production migration. Future Debian appliance would be a reproducible signed base with service supervision, encrypted backup and two-slot rollback for exactly the same Sofia identity. Preserve original canonical database ID, original owner-held encryption keys, personality, reviewed memory and permissions. All clients and Hephaestus remain subordinate to one active writer. Host-selection and promotion require verified backup, the previous writer fenced, approved service/host identity and operator-confirmed single promotion; never silently start two active LLM/automation owners.

**Remaining independent proof:** Entry requires pinned CI and installed-wheel release, working startup and LIFE cycle, actual voice/avatar and channel operation, Fleet/backup/restore evidence and a seven-day supervised soak. Debian release CI alone is not owner consent to deploy. Independent reviewer must explicitly accept this staged design before G1 status.

**Source references:** docs/development/p0-architecture-release-audit-2026-10-10.md; docs/development/v18-gate4-development-standard.md; .github/workflows/debian-release-candidate.yml

**G1 acceptance:** OPEN until the original requirement is independently reviewed.

## CA-5408: Kernel deferral boundary

**Original:** **CA-5408 [DESIGN/RESEARCH]** Put any true operating-system kernel proposal outside active scope until a documented capability cannot be supplied by Linux/Windows drivers, hypervisor or isolated worker; require risk/cost comparison and independent design approval.

**Chosen design and rationale:** Set custom-kernel implementation outside active scope. A new OS kernel is considered only if the owner documents a testable hardware/driver need demonstrably unsatisfied by Windows/Linux drivers, Hyper-V, sandboxing, containers, existing service APIs or JEA. Compare kernel patch cadence, boot chain, storage, network, graphics/audio hardware support, hypervisor compatibility, security supply chain, rollback and 24-hour operations burden against the same measurable objective under user-space alternatives. Default rejection: added maintenance and authority surface without evidence of a capability gain.

**Remaining independent proof:** Independent decision approval and a measured, reproducible unmet hardware requirement would be required to reopen research. No kernel code is planned or needed for Sofia Gate 1, and this deferred concept must never be treated as a hardware benchmark result.

**Source references:** docs/development/p0-architecture-release-audit-2026-10-10.md; docs/development/companion-autonomy-contract.md; src/sofia/safe/permissions.py

**G1 acceptance:** OPEN until the original requirement is independently reviewed.
