# G1 original-requirement design candidates, group A (5 tasks)

**Status: completed review candidates, NOT independently accepted G1.** The original development standard requires an independently reviewed complete design deliverable, not a source-only note. No canonical task statuses are altered.

Each entry preserves the original source requirement, a concrete proposed decision, evidence to inspect and remaining independent verification.

## CA-3101: Component ownership

**Original requirement:** **CA-3101 P0 [DESIGN/RESEARCH]** Map a single **component ownership table** for COGNITION v2, LIFE, GOALS, RUN, SAFE, ACT, MEM, NEURO, WORLD, DEV, Fleet and VM; record authoritative writer, consumers, error states and data retention. Design deliverable: reviewed owners table and 3 end-to-end sequence diagrams.

**Design decision and boundaries:** Preserve the existing companion-autonomy-contract.md single-writer table. COGNITION/Matrix owns turn choices and observed traces; LIFE owns personal project intent; GOALS owns commitments; RUN owns work lifecycle; SAFE owns permissions; ACT owns permitted effects; MEM owns reviewed memory; NEURO advises attention; WORLD and CREATIVE own virtual assets; Fleet owns identities and transport; hypervisor guest can produce only ephemeral results. Draw three causal paths: authenticated user turn to delivery receipt, original LIFE project to independently graded artifact, and exact approval through mTLS Fleet job to authoritative outcome.

**Unresolved review/acceptance:** Review each writer, consumer, principal/audience binding, error state and retention rule against current bootstrap and stores. Existing contract includes three sequence diagrams but not an independently signed review.

**Source locations:** docs/development/companion-autonomy-contract.md; src/sofia/application/bootstrap.py; src/sofia/run/work.py

**G1 decision:** NOT YET ACCEPTED. Independent reviewer and any specified host/owner evidence still required.

## CA-3102: Canonical runtime and host failure

**Original requirement:** **CA-3102 P0 [DESIGN/RESEARCH]** Decide **canonical Sofía runtime location and failover ownership** before adding Hephaestus. Distinguish runtime process, logical canonical `sofia.db`, user-visible UI and disposable workers. Design deliverable: one-writer state diagram with host-failure behavior.

**Design decision and boundaries:** Separate canonical identity and sofia.db logical authority from the physical active SofiaApplication process, Desktop/Discord/Terra clients and Hephaestus disposable worker. One selected, leased primary host is a writer; a backup copy is never another active writer. When primary host or fencing is unknown, all state-changing jobs fail closed; cached read-only history must disclose staleness. A promoted standby can write only after old authority is fenced and backup integrity reviewed.

**Unresolved review/acceptance:** Record the actual approved primary host and canonical state location. Independent recovery review must verify fencing, failover behavior, clean stopping of old writer and failback on exact host identities.

**Source locations:** src/sofia/application/bootstrap.py; src/sofia/state/sqlite_plane.py; src/sofia/ops/backup_topology.py

**G1 decision:** NOT YET ACCEPTED. Independent reviewer and any specified host/owner evidence still required.

## CA-3103: Dual-location database recovery

**Original requirement:** **CA-3103 P0 [DESIGN/RESEARCH]** Resolve the desired **two-location database redundancy** without two independent writers corrupting SQLite. Compare encrypted snapshot replication, SQLite backup/WAL shipping, single-writer replicated storage, and promoted-standby failover; specify RPO/RTO, fencing, reconciliation and failback.

**Design decision and boundaries:** Compare four techniques: encrypted SQLite online snapshot to independently protected standby (simple, conservative RPO), WAL/backup shipping with ordered checkpoints (higher operational risk), replicated block storage with exclusive fencing (complex dependencies), and owner-promoted standby (recovery action, not simultaneous writers). Recommend encrypted independently validated snapshots first. Propose RPO at most 24h and RTO at most 4h as unmeasured targets pending owner approval. Capture source digest, transaction integrity, encryption key custody, retention, offsite restores, failover lease fencing and controlled failback.

**Unresolved review/acceptance:** Owner must accept targets and a specific exclusive-writer lease/fence; run independently observed restore/kill-primary/attempted-dual-writer trial before any claimed production guarantee.

**Source locations:** src/sofia/ops/backup.py; src/sofia/ops/backup_topology.py; docs/development/companion-autonomy-contract.md

**G1 decision:** NOT YET ACCEPTED. Independent reviewer and any specified host/owner evidence still required.

## CA-3104: Project and job failure machine

**Original requirement:** **CA-3104 P0 [DESIGN/RESEARCH]** Formalize the **LIFE state machine** for queued, running, completed, waiting-approval, blocked, failed, uncertain, paused, abandoned and verified objective complete. Spell out which state triggers critique, retry, operator question, next milestone or silence.

**Design decision and boundaries:** RUN job states QUEUED and WAITING_APPROVAL imply no completed effect; RUNNING needs durable authority; COMPLETED triggers artifact byte + SHA/revision + scoped receipt recheck; FAILED is not permission to retry; UNCERTAIN requires reconciliation not replay. LIFE project ACTIVE, PAUSED, ABANDONED and COMPLETED is a distinct state machine; VERIFIED objective PASS can advance milestone, typed FAIL may authorize one budgeted revision, UNKNOWN pauses for review, and inactivity/silence is valid. Owner stop and busy gaming prevent new voluntary work.

**Unresolved review/acceptance:** Inspect every real state transition in coordinator and TaskExecutionManager, test crashes before/after authorization, RUN, evaluation and milestone CAS without duplicate effects.

**Source locations:** src/sofia/life/coordinator.py; src/sofia/life/model.py; src/sofia/run/work.py; test/test_life_verified_milestone_production.py

**G1 decision:** NOT YET ACCEPTED. Independent reviewer and any specified host/owner evidence still required.

## CA-3105: Authority and consent rights

**Original requirement:** **CA-3105 P0 [DESIGN/RESEARCH]** Define a **decision-rights matrix** across read-only sensing, safe autonomous tasks, scoped reversible actions, protected changes and never-self-authorized permissions; identify exactly which provisioning steps require fresh operator consent and which can be leased.

**Design decision and boundaries:** Five logical classes: read-only scope-admitted perception, low-risk preauthorized tasks, narrowly scoped reversible actions, fresh-owner-presence protected host/credential changes, and non-self-authorizable identity roots. No observation, model message, NEURO salience, simulated result or goal creates an approval. Hephaestus internal-switch staging and installer boot each require separate exact VM/node/policy digest protected approval plus Fleet lease. Guest enrollment is separate and must prove identity.

**Unresolved review/acceptance:** Independently check SAFE Level policy and exact-action, single-use, TTL, revoke, stop and audience binding on production callers. Original plan cannot be marked accepted merely by a decision table.

**Source locations:** src/sofia/safe/permissions.py; src/sofia/safe/execution_approval.py; src/sofia/distributed/agent_tools.py; docs/ops/HEPHAESTUS_OWNER_CREATED_HYPERV.md

**G1 decision:** NOT YET ACCEPTED. Independent reviewer and any specified host/owner evidence still required.

## Review checkpoint

Independent reviewers must sign off each original clause against concrete source evidence and owner-controlled decisions. No model-generated proof or historical CI badge is an independent review.
