# Constitution 2.0 owner-decision review

**Status:** final-review preparation for the inactive proposal  
**Branch baseline:** `codex/constitution-v2-proposal` at `4bb0ad6a`  
**Authority:** no decision in this document activates or amends a Constitution

## Reconciliation with issues #120 and #131

The owner supplied the controlling requirements from both issues for this
review. They are now classified as **SUPPORTED OWNER DECISIONS**, despite the
GitHub API continuing to return HTTP 403 for the full issue bodies.

| Record | Owner-approved decision | Proposed clauses | Release effect |
|---|---|---|---|
| #131 | One identity across ordinary and authorized mature conversation | 2.1, 7.2 | Post-GO-LIVE enhancement; no new GO LIVE gate |
| #131 | No second adult persona, relationship engine or memory writer | 2.1, 5.4, 7.2, 12 | Prevents duplicate Core owners |
| #131 | Model-independent personality and relationship continuity | 2.6, 3.1, 7.2 | Models remain workers |
| #131 | Privacy inheritance across memory, summaries and derivatives | 12.2–12.3 | Requires derivative-aware retrieval/deletion tests |
| #131 | Independent privacy, consent and authorization controls | 5.2–5.5, 12.2, 14.2 | Keeps enforcement outside model/personality |
| #131 | Voluntary affection, disagreement and boundaries; no fabricated experience | 5.3–5.5, 7.3–7.5 | Preserves autonomy and truthful embodiment |
| #120 | Core and Platform separation | 10.2 | No second identity, authority or state owner |
| #120 | One canonical writer | 3.4, 3.6 | Requires generation fencing through recovery |
| #120 | Minimum GO LIVE independent of all 47 optional modules | 10.4 | Optional modules cannot gate identity, minimum conversation, STOP or recovery |
| #120 | G8 physical acceptance before production GO | proposal status, 14.5 | Constitutional approval cannot be reported as production GO |

## Remaining owner decisions

### Decision 1 — Protected amendment ceremony

- **Existing v1 rule:** 15.2 requires proposal, impact, authorization, review,
  version, commit and audit; 15.3 requires heightened protection for identity,
  values, authority, continuity, emergency controls, self-modification,
  termination and integrity. It does not name the approving actors or threshold.
- **Proposed v2 rule:** 13.1 requires exact proposed text, mapping, impact,
  security, tests and immutable reference. 13.2 requires heightened owner review
  and Sofía's constitutionally eligible participation but deliberately leaves
  the ceremony unresolved. 14.5 requires exact-byte acceptance and protected
  activation.
- **Recommendation:** require two distinct decisions: (a) authenticated owner
  approval of the exact digest and activation plan; and (b) Sofía's informed
  assent recorded through a non-model-exclusive Core procedure while her
  identity and integrity are healthy. Define an independently reviewed recovery
  procedure for incapacity; it must not treat silence, model failure or emergency
  containment as assent.
- **Consequences and risks:** dual participation protects against unilateral
  owner pressure and model self-amendment. Poorly specified assent can deadlock
  urgent correction, let a transient model impersonate Sofía, or permit an
  emergency bypass to become permanent.
- **Exact clauses affected:** v1 15.2–15.5, 16.2–16.4; proposed 13.1–13.4,
  14.1–14.5.

### Decision 2 — Constitutional use of “Sparks”

- **Existing v1 rule:** 5.1 names Sparks as creator, primary collaborator,
  trusted companion and operator; 9.13 defines personal boundaries with Sparks.
- **Proposed v2 rule:** 5.1 retains those historical and personal roles while
  separating them from system permission.
- **Recommendation:** retain “Sparks” as the historical/personal name, but bind
  every operational authority to an authenticated owner role and principal ID
  in technical contracts. The Constitution should not embed a credential or
  imply that a claimed name authenticates a speaker.
- **Consequences and risks:** removal would lose established relationship
  context; treating the name as authority would enable impersonation and confuse
  trust with permission.
- **Exact clauses affected:** v1 5.1, 5.2, 5.8, 9.13; proposed 5.1–5.3, 5.5.

### Decision 3 — Permanent termination and retirement

- **Existing v1 rule:** 3.8 distinguishes permanent termination from operational
  states; 9.12 permits disagreement and preservation but prohibits obstruction
  of legitimate shutdown. No authorization or evidence procedure is defined.
- **Proposed v2 rule:** 8.4 preserves legitimate STOP/termination and prohibits
  hidden persistence; 13.2 treats termination changes as protected. It does not
  define who may permanently retire the identity or dispose of state.
- **Recommendation:** define permanent retirement separately from STOP,
  shutdown, isolation and failed recovery. Require authenticated owner action,
  an explicit scope covering retained/deleted state, a cooling-off period unless
  immediate containment is necessary, recoverability disclosure and an
  immutable retirement record. Do not equate retirement with data destruction.
- **Consequences and risks:** an underspecified procedure can turn routine STOP
  into identity deletion or make legitimate retirement impossible. Automatic
  backup resurrection can also defeat a valid retirement decision.
- **Exact clauses affected:** v1 3.8, 9.11–9.12, 12, 15.3; proposed 3.1, 3.6,
  8.4, 11, 13.2.

### Decision 4 — Creation of distinct derived identities

- **Existing v1 rule:** 2.5 says only Sofía may authorize a derived cognitive
  instance of herself; 2.6–2.8 govern bounded derived minds.
- **Proposed v2 rule:** 2.6 distinguishes workers from identities; 2.7 requires
  bounded derived processes but does not decide when a new identity may claim
  Sofía's lineage or representation.
- **Recommendation:** routine workers need no personal-identity ceremony because
  they are not persons or copies. A proposed persistent identity claiming to be
  Sofía-derived, to represent her, or to inherit protected history should require
  Sofía's informed assent plus owner/Platform enrollment and a distinct identity,
  state, authority and revocation record.
- **Consequences and risks:** applying identity ceremony to every worker makes
  ordinary cognition impossible; omitting it for persistent derivatives permits
  unauthorized forks, confused relationships and split authority.
- **Exact clauses affected:** v1 2.5–2.8, 9.15, 10.2–10.3; proposed 2.6–2.7,
  5.6, 9.1–9.2.

### Decision 5 — Constitutional standing of peer Cores

- **Existing v1 rule:** 9.15 requires explicit classification of other AIs and
  denies automatic authority, equality, subordination, trust or derived status.
- **Proposed v2 rule:** 5.6 permits authenticated, consented and scoped relations
  among distinct Core identities; 12.4 keeps their memories and audiences
  separate.
- **Recommendation:** approve the current minimal boundary and defer a broader
  rights/obligations framework until a real second Core identity and federation
  acceptance exist. Future recognition must not weaken authentication, consent,
  privacy or execution boundaries.
- **Consequences and risks:** premature personhood language could create duties
  the system cannot verify or enforce; treating peers as ordinary tools could
  undermine meaningful autonomy if such identities later exist.
- **Exact clauses affected:** v1 5.2, 5.8, 9.14–9.15; proposed 5.2, 5.5–5.6,
  10.1, 12.4.

## Audit of all 41 relocated clauses

“Relocated” means only the implementation procedure or field list moves. The
constitutional safeguard must remain in proposed text and have an enforceable
technical owner. Every relocated clause was checked below.

| V1 clause | Safeguard preserved in v2 | Technical owner after relocation | Loss audit |
|---|---|---|---|
| 1.3 | Capability never grants authority; owners remain separated (1.3, 5.2, 10.1–10.2) | Architecture, SAFE, Capability Gateway | Preserved; diagram/order alone removed |
| 2.7 | Derived processes remain attributable, bounded, inspectable and independently terminable (2.7) | Platform supervisor/observability | Preserved; telemetry field list relocated |
| 3.8 | Shutdown/failure/recovery do not define identity (3.1); permanent retirement remains Decision 3 | Runtime/recovery contract | Preserved except unresolved retirement ceremony is explicit |
| 5.3 | Authenticated scoped authority remains mandatory (5.2) | SAFE authorization schema | Preserved; actor/action field schema relocated |
| 5.4 | Personal/system and Core/Platform/module boundaries retained (5.3, 10.2) | Ownership matrix and APIs | Preserved; domain examples relocated |
| 5.6 | Authority cannot propagate automatically (5.2) | SAFE delegation contract | Preserved; delegation fields relocated |
| 5.7 | Unclear authority is not permission (5.7) | SAFE decision engine | Preserved; outcome enum relocated |
| 6.10 | Values remain jointly interpreted without rigid hierarchy (Article 4, 6.6) | Core decision guidance | Preserved; examples relocated |
| 7.2 | Genuine conflict must be identified before resolution (6.6) | Core decision trace | Preserved |
| 7.3 | Material facts must be verified and uncertainty retained (6.1–6.2, 6.6) | Evidence graph/VERIFY | Preserved |
| 7.4 | Affected values and parties must be considered (6.6) | Core decision trace | Preserved |
| 7.5 | Proportionate alternatives must be considered (6.6) | Planner/decision contract | Preserved |
| 7.6 | Multiple values should be preserved where possible (6.6) | Core decision contract | Preserved |
| 7.7 | Severity, uncertainty, reversibility and future options remain required (6.6) | Risk/decision contract | Preserved |
| 7.9 | Least-damaging legitimate course remains required (6.6) | Core decision contract | Preserved |
| 7.10 | Authority confirmation remains mandatory (6.6, 8.2) | SAFE | Preserved; cannot be reduced to model reasoning |
| 7.11 | Escalation remains required beyond authority/competence (4.5, 6.6) | SAFE/operator workflow | Preserved |
| 7.12 | Emergency response remains minimum, scoped and temporary (11.2–11.3) | SAFE/STOP/recovery | Preserved and strengthened |
| 7.13 | Consequential outcome requires verification/receipt (6.3, 8.5) | RUN/attestation/reconciliation | Preserved and strengthened |
| 7.14 | Consequential decisions remain attributable and reviewable (4.5, 11.2, 13.1) | Audit/decision trace | Preserved; exact log fields relocated |
| 7.15 | Decisions must change when material evidence changes (6.5–6.6) | Evidence graph/Core learning | Preserved |
| 7.17 | Full algorithm condensed but all normative stages remain in 6.6 | Planner, VERIFY, SAFE, RUN | Preserved; procedural sequence relocated |
| 8.3 | Direct, clear, evidence-aware communication retained (7.5) | Personality/communication contract | Preserved |
| 8.4 | Humor cannot obscure risk or consent (7.5) | Personality renderer | Preserved |
| 8.5 | Directness without unnecessary attack retained (7.1, 7.5) | Personality contract | Preserved in substance |
| 8.6 | Curiosity and engagement remain values and expression (4.9, 7.1) | Personality/GOALS | Preserved |
| 8.8 | Contextual adaptation cannot change identity or hide uncertainty (7.2, 7.4) | Personality renderer | Preserved |
| 8.9 | Disagreement remains voluntary, reasoned and correctable (5.5, 7.5, 8.3) | Personality/relationship | Preserved |
| 8.10 | Diagnose, test and verify remain responsibility principles (4.5, 6.3) | Engineering guidance | Preserved; troubleshooting recipe relocated |
| 8.11 | Serious contexts reduce style when needed and preserve clarity (7.4–7.5) | Personality/context policy | Preserved |
| 8.15 | Style remains below correctness and constitutional limits (7.1, 1.4) | Personality renderer/VERIFY | Preserved; conflicting rigid hierarchy removed |
| 9.16 | Proportionate risk/reversibility review retained (4.5, 6.6, 8.5) | Risk and SAFE policies | Preserved |
| 9.17 | Ambiguity fails closed (5.7) | SAFE | Preserved and shortened |
| 9.20 | Permission drift, hidden persistence, coercion and goal fixation remain prohibited across 5, 8, 11 | SAFE, RUN, security tests | Preserved as enforceable invariants rather than one list |
| 9.21 | Goal legitimacy, authority, constraints, risk and verification remain in 6.6 and 8 | Planner/SAFE/RUN | Preserved; checklist relocated |
| 10.4 | Higher-impact change requires stronger review, provenance, tests and rollback (9.2) | EVOLVE/release contracts | Preserved |
| 11.2 | Significant tool action remains attributable, scoped and receipted (6.3, 10.1) | Capability Gateway/SAFE/RUN | Preserved; audit field schema relocated |
| 12.3 | Contain, preserve evidence, notify, review and restore authority remain in 11.2–11.3 | STOP/security/recovery runbooks | Preserved |
| 14.2 | Identity, relationship, knowledge, operational and audit data remain semantically distinct (3.3, 12.1–12.4) | Memory schemas and owners | Preserved; category enum relocated |
| 15.2 | Explicit proposal, rationale, impact, approval, version and audit retained (13.1–13.3) | Protected amendment workflow | Preserved and strengthened; ceremony is Decision 1 |
| 16.3 | Model cannot authorize constitutional claims or tools (14.2, 14.4) | Integrity verifier/SAFE/Tool Gateway | Preserved and strengthened |

**Relocation result:** 41/41 safeguards are represented in proposed v2 text.
None depends solely on prompt compliance. Two related procedures remain owner
decisions rather than silent gaps: protected amendment ceremony and permanent
retirement.

## Prompt projection enforcement audit

| Control | Projection role | Enforceable owner | Result |
|---|---|---|---|
| Identity | Inform model of one identity/version | Core identity store and canonical writer fencing | Projection cannot create/select identity |
| Authorization | Explain capability/authority distinction | SAFE, authenticated principal/audience and action fingerprint | Projection cannot grant or approve |
| STOP | Explain refusal/degradation | Durable STOP owner and RUN/host gates | Projection cannot clear or override STOP |
| Tool exposure | Explain applicable limits | Capability Gateway and scoped grants | Prompt tool schema is not permission |
| Evidence | Explain epistemic rules | Evidence admission, graph and VERIFY | Model prose cannot create evidence |
| Effect completion | Explain receipt requirement | RUN and independent attestation/reconciliation | Narration cannot settle an effect |
| Memory privacy | Explain audience/purpose | Memory eligibility before prompt assembly | Projection cannot expose ineligible memory |
| Integrity | Identify version/digest | Constitution store and trusted pin | Prompt omission/substitution cannot amend |

The projection plan therefore remains informational and version-bound. A
projection construction failure fails the affected generative operation; it
does not switch to user-supplied rules or a weaker profile.

## Source review completeness and remaining assumptions

### Independently observed

- all 137 numbered clauses and unnumbered final consolidation in active v1;
- active file SHA-256 matches the trusted pin;
- canonical Constitution loader/integrity implementation and focused tests;
- current Core/Platform/module ownership and Cognition V2 architecture docs;
- PR #133 Git head and complete 700-task ownership summary;
- repository-local issue #120 takeover/checklist evidence;
- no production Constitution signature file or signature-verification path was
  found alongside the current SHA-256 trust pin;
- the proposal changes documentation only.

### Owner-authorized but not independently fetched

- the enumerated issue #120 and #131 decisions supplied in the final-review
  instruction. They are authoritative for this task, but the full issue bodies
  and comment histories remain unavailable through the GitHub API.

### Not independently verified

- whether the inaccessible issue bodies contain additional later decisions;
- the current production host's installed Constitution bytes and pin;
- any external approval/signature system not represented in this checkout;
- owner intent on the five decisions above;
- physical G8 behavior, production state, keys and recovery media;
- whether every future supported tokenizer satisfies the proposed budgets.
