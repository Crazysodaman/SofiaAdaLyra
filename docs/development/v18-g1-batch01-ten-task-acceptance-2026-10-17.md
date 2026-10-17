# Gate 1 batch 01: CA-3101 through CA-3110

**Branch:** main. **Scope:** 10 original Phase 00 design/research requirements, no status awards.
**Gate 1 rule:** an independently reviewed complete deliverable satisfying *every* original clause. Draft documents are not proof of implementation, production behavior or host measurements.

This batch consolidates the existing Group A/B candidate decisions into explicit, independently reviewable acceptance checks. Original requirements are in `docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md`. Source drafts:
- `docs/development/v18-g1-review-batch-a-architecture-2026-10-17.md`
- `docs/development/v18-g1-review-batch-b-fleet-evidence-2026-10-17.md`

| Task | Exact Gate 1 deliverable and independent review check | Required evidence still missing / decision required |
|---|---|---|
| CA-3101 | One authoritative owners/writers/consumers/error/retention table for all 12 named owners, **plus three complete end-to-end diagrams**, with principal and audience guards annotated. Reviewer follows actual bootstrap-to-store write paths. | Compare contract and diagrams with live interfaces, resolve unmatched writers and retention fields, obtain independent design sign-off. |
| CA-3102 | Owner-approved single-writer runtime placement diagram distinguishing writer, logical DB, UI and disposable workers. Diagram covers running, writer unreachable, standby available, old writer returns and failback. | Owner-approved primary/standby placement, explicit fencing proof and authenticated failover decision. Do not infer deployment from design. |
| CA-3103 | Four-option redundancy tradeoff matrix (snapshot, WAL ship, exclusive replicated storage, promoted standby) with RPO/RTO, validation, encryption/key custody, fencing, conflict handling and failback. | Owner must approve RPO/RTO targets; recovery review must verify backup and a fenced failover without simultaneous writers. |
| CA-3104 | LIFE/RUN state-transition table covering all nine original states. Each entry must name retry/reconcile/critique/milestone/ask/silence consequence and forbid replay of uncertain effects. | Trace all actual state transitions and restart boundaries in canonical coordinator and RUN manager; demonstrate dedupe and crash recovery. |
| CA-3105 | Five-tier rights table for read-only, bounded autonomy, reversible effects, protected host/credential mutations and never-self-authorized identity. For each provision step list principal, exact operation, approval duration, revocation and audit. | Check all real SAFE/UI/CLI/Fleet callers and owner presence; reject blanket approvals or privilege minted by model output. |
| CA-3106 | Actual Artemis-to-guest network comparison, choose offline/internal/broker, specify reachability, firewall, identity, DNS and prohibited egress; include broker reachability and negative isolation evidence. | Approved host topology plus actual switch/broker firewall observations; no guest network assertions from planned config alone. |
| CA-3107 | Compare JEA/isolated agent vs one-time owner provisioning, name exact constrained Hyper-V operations, immutable plan hash, one-use approvals and audit events. | Host ACL/JEA evidence and Artemis negative authorization test. No unattended admin operations without independent approval. |
| CA-3108 | Distinct host and guest identities with issuance, on-device key storage, expiration, rotate/revoke, snapshots/log scrub, compromise recovery and escrow. | Pin PKI lifecycle and reenrollment contract; prove private keys absent from images/shares and revocation independently. |
| CA-3109 | Eight-level evidence taxonomy with correction graph, source, subject, observation and processing times, principal/audience and provenance. Show MEM/LIFE/conversation effects of correction/revocation. | Field-level persistence mapping plus negative tests for cross-audience, future timestamps and revoked ancestors. |
| CA-3110 | Measured VM-vs-reimage-vs-process decision table for isolation, startup, CPU/RAM, reproducibility, tool coverage and restore cost. Explicit acceptance/rejection thresholds and cleanup isolation. | Reproducible guest measurements and clean-state recovery demonstration; do not mistake proposed quotas for actual isolation. |

## Batch rules and handoff

1. Independent reviewer records a clause-by-clause decision, source SHA, reproducible evidence, objections and named reviewer approval in an owner-controlled review artifact. A source author cannot self-approve.
2. Owner-only choices and real Artemis/Venus observations must remain OPEN until obtained. No host, production credentials, canonical DB or VM changes are authorized by this document.
3. Keep `docs/development/v18-task-evidence.json` unchanged until an independently verifiable reviewed Gate 1 result is supplied for each individual task. One green CI run cannot satisfy 10 heterogeneous design requirements.
4. For the next implementation pass, begin with CA-3101 ownership/diagram reconciliation and CA-3104 transition-table source tests; parallelize pure documentation reviews, not privilege changes.

**Result:** 10 tasks explicitly triaged for Gate 1 acceptance. **0 newly awarded Gate 1**.