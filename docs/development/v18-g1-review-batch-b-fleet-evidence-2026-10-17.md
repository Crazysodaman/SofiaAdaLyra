# G1 original-requirement design candidates, group B (5 tasks)

**Status: independent G1 review pending.** This records decisions and source-trace boundaries only; no Artemis, Venus, VM or credential modifications performed.

## CA-3107: Artemis privilege controls

**Original:** **CA-3107 P0 [DESIGN/RESEARCH]** Review **Artemis privilege minimization** for Hephaestus creation: constrained JEA/runbook or isolated provisioning agent, exact VM name/resources/network paths, immutable plan digest, non-reusable approvals and full administrative event logging. Compare to one-time operator-run setup.

**Decision / comparison:** Owner-created Hephaestus is the approved v1 path. Compare one-time host-admin setup with an always-on provisioning service: prefer owner-supervised preparation and only a separately enabled fixed-operation Hyper-V provider for read-only inspect, exact host-only link stage and approved existing-VM installer boot. Reject wildcards, unrestricted PowerShell, spontaneous VM creation, general admin credentials and blanket approvals. Pin GUID, signed image digest, internal switch, one-use 10-min approval, expiring Fleet grant, pre/post observation and UNCERTAIN on timeout.

**Unresolved evidence:** OS-enforced host JEA or equivalent principal isolation is not independently demonstrated. Inspect Artemis Windows logs and exact authorized negative host arguments before G1 review.

**Grounded source leads:** src/sofia/integrations/hyperv.py; src/sofia/distributed/agent_tools.py; docs/ops/HEPHAESTUS_OWNER_CREATED_HYPERV.md

**G1:** OPEN (no independent reviewer acceptance).

## CA-3108: Guest/host identity lifecycle

**Original:** **CA-3108 P0 [DESIGN/RESEARCH]** Design **host and guest identity and credential lifecycle**: separate Fleet identities, secure key provisioning, rotation, revocation, bootstrap escrow, no private-key copies in broad SMB shares, secrets absent from images/snapshots and scrubbed logs.

**Decision / comparison:** Keep canonical Sofia identity, Artemis Fleet host certificate and untrusted Hephaestus guest identity separate. Never trust VM name alone. Guest enrollment requires exact machine/host binding, authenticated key possession, signed boot media evidence, owner approval and protocol/version handshake. Generate private keys on the owning device; forbid copied identities in images, VM snapshots, Git/SMB and diagnostic output. Define rotation as owner-approved overlap with revocation, recovery from protected owner-held keys, compromise quarantine and independently logged reenrollment.

**Unresolved evidence:** Reconcile exact PKI rotation and revocation window, certificate/secret cleanup on snapshot, and host/guest end-to-end proof. No guest OS currently verified.

**Grounded source leads:** src/sofia/ops/fleet.py; src/sofia/safe/execution_approval.py; docs/ops/HEPHAESTUS_OWNER_CREATED_HYPERV.md

**G1:** OPEN (no independent reviewer acceptance).

## CA-3109: Truth labels and correction

**Original:** **CA-3109 P0 [DESIGN/RESEARCH]** Specify an **evidence taxonomy** covering observed, verified, inferred, simulated, hypothesized, stale, unknown and revoked; define how sources, times, principal/audience and correction chains propagate into LIFE, MEMORY and conversation.

**Decision / comparison:** Define eight evidence categories: OBSERVED source data, VERIFIED independent check, INFERRED hypothesis, SIMULATED virtual result, HYPOTHESIZED untested claim, STALE expired, UNKNOWN absent, REVOKED invalidated. Every observation has source, subject, principal, audience, event time versus processing time, confidence where meaningful, modality and dependency/correction chain. Promotion requires compatible observed/verified fact; model statements, simulations and later text summaries cannot retroactively mint physical observations. Corrections invalidate descendant memory, goals and preferences until reverified.

**Unresolved evidence:** Independent reviewer must map taxonomy onto COGNITION/MEM/NEURO/LIFE actual persisted fields, correct/revoke events and negative tests for cross-audience, future-date and invalid ancestor.

**Grounded source leads:** src/sofia/cognition/matrix/trace.py; src/sofia/goals/evidence.py; src/sofia/life/coordinator.py

**G1:** OPEN (no independent reviewer acceptance).

## CA-3110: Workshop isolation trade-offs

**Original:** **CA-3110 P1 [DESIGN/RESEARCH]** Document **VM trade-offs**: always-on Debian guest versus disposable/re-imaged per-project guest versus temporary per-job isolated process. Decide using isolation strength, snapshot time, CPU/RAM overhead, reproducibility, tool suitability and restore cost.

**Decision / comparison:** Compare always-on Debian VM (warm but persistent attack surface), reimaged per-project guest (strong isolation/reproducibility with boot/disk cost) and isolated per-job process (fast but weaker boundary). Continue existing owner-created Hephaestus with signed installer media and no unapproved VM copies. Execute work only within bounded reviewed ephemeral workspaces with pinned toolchain, input/output hash manifests, quota and operator stop. A JSON budget alone is never proof of resource isolation.

**Unresolved evidence:** No measured snapshot/boot/CPU/RAM cost, actual guest OS isolation or return-to-clean-state proof exists. Reviewer should reject claims of automatic provisioning and require measured tradeoff matrix before changing v1.

**Grounded source leads:** src/sofia/ops/workshop_policy.py; src/sofia/ops/workshop_provision.py; docs/ops/HEPHAESTUS_OWNER_CREATED_HYPERV.md

**G1:** OPEN (no independent reviewer acceptance).

## CA-3111: Dependency failure and deterministic restart

**Original:** **CA-3111 P1 [DESIGN/RESEARCH]** Identify **single points of failure** and critical dependencies: Venus model runtime, Artemis power, DNS, PKI, Fleet broker, NAS, `sofia.db`, backup location, NWS, JMRI, Home Assistant and Ollama. Design explicit degraded/offline modes with deterministic restart.

**Decision / comparison:** Failure map: Venus primary model down -> no invented answer, optional deep work deferred; Artemis power/mTLS/Hyper-V unavailable -> Fleet unknown, no remote effect; DNS/PKI down -> deny unsafe endpoints; NAS/backup inaccessible -> no unverified restore; canonical SQLite corrupt/absent -> stop new writer and require integrity restore; NWS/Hestia/JMRI stale -> label unavailable not zero; Discord transport down -> avoid duplicate replies. Recover identity and SAFE first, canonical DB single writer second, reconcile uncertain RUN receipts third, then resume user-facing projections without unrequested social pings.

**Unresolved evidence:** Provide fault-injection matrix covering all named systems, real observed restart receipts and host power loss; deterministic idle/recovery must be independently witnessed for G1.

**Grounded source leads:** src/sofia/application/bootstrap.py; src/sofia/run/work.py; src/sofia/ops/backup.py; src/sofia/ops/fleet.py

**G1:** OPEN (no independent reviewer acceptance).
