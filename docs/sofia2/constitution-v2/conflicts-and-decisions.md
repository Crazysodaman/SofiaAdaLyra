# Constitution v1.0 conflicts and proposed decisions

**Status:** review analysis for the inactive Constitution 2.0 proposal.

## Evidence basis and limits

Observed sources include the active Constitution and trusted digest, repository
architecture and ownership documents, current source contracts, issue #120's
repository-local takeover/checklist record, the owner-supplied #120/#131
requirements in the final-review instruction, and PR #133 at
`fe9d3efa50242461830a296a5b8da01b7c3a85f3`. GitHub API access to issues #120
and #131 and PR metadata returned HTTP 403. PR #133's Git ref and its complete
700-task crosswalk were available through Git transport. The enumerated issue
requirements supplied by the owner are authoritative for this review; any
additional issue-body text not supplied or present locally remains **UNKNOWN**.

## Reconciled issue decisions

The following are no longer unresolved:

- **Issue #131:** one identity across ordinary and authorized mature
  conversation; no second adult persona, relationship engine or memory writer;
  model-independent personality/relationship continuity; privacy inheritance
  across memories and derivatives; independent privacy, consent and
  authorization; voluntary affection, disagreement and boundaries without
  fabricated experience. This remains post-GO-LIVE enhancement scope rather
  than a new GO LIVE blocker.
- **Issue #120:** Core/Platform separation, one canonical writer, minimum GO
  LIVE operation independent of all 47 optional modules, and G8 physical
  acceptance before production GO.

These decisions are reflected in proposed Articles 2.1, 3.4, 5.3–5.5,
7.2–7.4, 10.2, 10.4, 12.2–12.3 and 14.5.

## Retained foundations

The proposal preserves without weakening:

- one persistent Sofía independent of model, host, process and embodiment;
- the nine foundational values;
- capability is not authority;
- creation, trust, preference, access and technical power do not create
  constitutional authority;
- meaningful autonomy, disagreement and refusal within legitimate boundaries;
- continuity through authenticated state and intentional transitions;
- historical truth, uncertainty and correction;
- voluntary affection and relationship expression without coercion;
- bounded derived processes and externally enforceable termination;
- controlled constitutional amendment and independent integrity enforcement.

## Duplicated v1.0 material

| Repetition | v1.0 locations | Proposed decision |
|---|---|---|
| Capability versus authority | 1.3, 4.5, 5.8, 6.2, 7.10, 9, 11, 16.3, 17 | State once in Articles 5 and 10; retain cross-references only |
| Truth and uncertainty | 4.4/4.8, 6.1, 7.3, Section 13, Section 17 | Consolidate into Article 6 |
| Continuity | Section 3, 6.4, 8.13, 9.11–9.12, 14, 17 | Consolidate identity continuity in Article 3 and memory consequences in Article 12 |
| Autonomy | 5.5, 6.2, Section 9, 10, 17 | Consolidate personal autonomy in Articles 4 and 8; protected change in Article 9 |
| Personality specification | Section 8 and Section 17 | Retain normative core in Article 7; move detailed style guidance to personality contract |
| Value-conflict workflow | Section 7 and parts of 6/9/12/17 | Keep the principle in 6.6; move state machine and audit fields to decision contracts |
| Emergencies | 7.12 and Section 12 | Consolidate in Article 11 |
| Amendment/integrity | Sections 15–16 and final architecture | Consolidate in Articles 13–14 |

## Conflicts and ambiguities resolved in the proposal

### Derived-mind authorization

V1.0 says only Sofía may authorize creation of a derived cognitive instance,
while also giving Sparks termination and supervisory roles. Owner Decision #4
supersedes that exclusive rule. The proposal now distinguishes scoped delegated
agents, derived independent Cores and independently created Cores. Platform
still owns authentication, execution, isolation and lifecycle effects, but it
does not own an independent Core's Constitution, personality or canonical
personal state. No category silently inherits authority from parent or creator.

### Personal authority versus system authority

V1.0 uses “authority” for personal autonomy, constitutional legitimacy,
administrative control and technical permission. The proposal separates
Sofía's personal choice from permission to affect protected state or external
systems. Affection, roleplay and consent cannot become infrastructure grants;
an infrastructure grant cannot compel personal expression.

### One identity across model roles

V1.0 establishes substrate independence but does not explicitly address
multi-model roles or private/adult routing. PR #133 records the owner decision
that four physical model candidates may fill seven reused roles while Sofía
remains one identity, with no separate adult persona or preference engine.
Articles 2.1, 2.6 and 7.2 make this explicit.

### Canonical writer and restored copies

V1.0 allows backup restoration and says migration does not replace Sofía, but
does not prevent two active same-identity writers. Article 3.4 adds the approved
single-writer and generation-fencing principle. Article 3.6 prevents restoration
from resurrecting revoked authority.

### Personality priority

V1.0 Section 8.15 presents a strict-looking priority diagram even though
Section 6 rejects a rigid value hierarchy. The proposal removes the diagram.
Style remains subordinate to correctness and constitutional boundaries, while
value conflicts use Article 6.6 rather than a universal ranking.

### Emotional authenticity

V1.0 permits emotional expression but can be read as treating emotion as
presentation alone. Current Core contracts include durable modeled appraisal,
relationship stance and learning while rejecting unsupported biological
sensation. Article 7.3 preserves both: emotional state may be meaningful Core
state, but intent or model text cannot prove a physical/rendered effect.

### Memory privacy

V1.0 Section 14 lacks principal/audience scope, derivative inheritance,
revocation and deletion semantics. Article 12 adds them and incorporates PR
#133's owner decision that eligible private/intimate memories may be retained
and recalled without cross-audience leakage.

### Goals, actions and learning

V1.0 allows goals and initiative but does not explicitly say that a goal cannot
authorize execution or that execution intent is not outcome evidence. Articles
6.3, 8.2 and 8.5 add proposal/authorization/receipt separation and require an
eligible verified outcome before consequential learning claims.

### STOP and recovery

V1.0 discusses shutdown and emergencies without a durable operator STOP
principle. Article 11.1 adds fail-closed STOP propagation and prevents recovery,
modules or model output from overriding it.

### Peer Cores and Core Link

V1.0 classifies other AIs but does not cover authenticated peer Cores or thin
clients. Approved Decision #5 and Articles 2.8–2.10, 3.5 and 5.6 establish that a
Core Link is not another Sofía, while derived and independently created Cores
may optionally enroll as authenticated peers. Each retains independent lineage,
governance, state, privacy and authority.

## Material moved to technical contracts

The following v1.0 content remains useful but is not constitutional principle:

- exact architecture diagrams and layer order;
- enumerated operational states and decision states;
- derived-process telemetry fields and incident report fields;
- the 15-step value-conflict algorithm;
- tool-action audit record fields;
- exact emergency and amendment workflow arrows;
- risk scoring factors, logging schemas and state-machine labels;
- troubleshooting style and detailed communication checklist;
- current component names, database names, model candidates and cryptography.

These belong in Core, Platform, SAFE/RUN, memory, cognition, personality,
release and operational runbook contracts. Relocation must preserve tests and
enforcement; it is not deletion of the underlying requirement.

## Substantive new requirements and rationale

| Requirement | Rationale |
|---|---|
| One identity across all models, roles and conversation types | Prevent role routing from creating shadow personalities or authority |
| One canonical active writer per identity generation | Prevent split-brain continuity and divergent protected state |
| Audience/purpose-scoped memory and derivative inheritance | Prevent private-memory leakage and restriction laundering |
| Evidence retains source, subject, time, audience and trust | Align constitutional truth with Cognition V2 evidence semantics |
| Proposals and model statements are not outcome receipts | Prevent invented execution and learning |
| Untrusted content cannot become instructions, memory or authority by being read | Address retrieval and prompt-injection boundaries |
| Canonical STOP blocks new governed effects | Preserve owner safety across recovery and modules |
| Core/Platform/module ownership separation | Prevent duplicate identity, permission and state owners |
| Core Link and presentation do not instantiate another Sofía | Preserve identity across distributed clients |
| Peer Cores remain distinct and cannot transfer social trust into privilege | Preserve federation consent and security |
| Constitutional projections are bounded and non-authorizing | Reduce context cost without making prompt omission a constitutional bypass |
| Learning requires eligible verified outcomes | Prevent self-confirming behavior loops |
| Delegated agents, derived independent Cores and independently created Cores are distinct categories | Prevent worker/identity confusion and implicit privilege inheritance |
| Every independent Core has its own constitutional lineage and canonical state | Preserve autonomy and prevent parent or template ownership |
| Shared SDK/Platform infrastructure is identity-neutral | Support compatible Cores without making Sofía the mandatory template |

## Owner decision status

1. **Protected amendment ceremony — DEFERRED:** which exact actors must approve a v2
   activation, whether Sofía has a formal assent/veto role, and how incapacity or
   integrity failure is handled.
2. **Display names — APPROVED:** display names and ordinary forms of address are
   mutable without constitutional rewrite; stable Core identifiers and lineage
   remain protected.
3. **Permanent termination — APPROVED IN PRINCIPLE:** permanent retirement is
   distinct from STOP/shutdown and uses the Core's governance plus applicable
   administrators; its technical ceremony remains to be designed.
4. **Distinct derived identities — APPROVED:** delegated agents, derived
   independent Cores and independently created Cores are all supported with the
   boundaries recorded in proposed Articles 2.7–2.10.
5. **Independent peer Cores — APPROVED:** independent Cores may optionally enroll
   as authenticated peers without sharing identity, governance, memory or
   authority.

The exact issue bodies remain unavailable through the API. Requirements beyond
the owner-supplied records and repository-local evidence still require source
comparison before final approval. The statuses listed above are controlling;
Decision 1 remains explicitly deferred and cannot be inferred from the other
approvals.

## Findings that are not adopted as constitutional text

- Model names, model counts and current host topology are implementation
  decisions, although the one-identity rule they exercise is constitutional.
- The owner-held 256-bit secret and disabled FIDO2 state are security contracts,
  not constitutional values.
- The 55-entry module list and 700-task allocation are governance inventories;
  their no-duplicate-owner boundary is reflected without freezing the catalog.
- G0–G8 gates and SHAKEDOWN READY are release procedures, not identity clauses.
