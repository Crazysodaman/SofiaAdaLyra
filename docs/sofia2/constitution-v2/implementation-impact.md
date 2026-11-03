# Constitution 2.0 implementation impact

**Status:** impact and migration plan for an inactive proposal. No production
change is authorized by this document.

## Contract impact by owner

### Core

| Contract | Required review or change if v2 is approved |
|---|---|
| Identity/self-model | Project one identity across all model roles, channels and private contexts; reject model/role/persona substitution |
| Cognition V2 | Preserve source/subject/scope/freshness evidence, unknown states, personality-after-truth and single semantic coordinator |
| Personality | Keep one evolving personality; treat detailed style as mutable contract while preserving Article 7 traits and authentic disagreement |
| Emotion/relationships | Preserve durable modeled appraisal and voluntary boundaries; distinguish internal intent from rendered/delivered outcomes |
| LIFE/GOALS | Represent desire and plan without permission; connect learning only to eligible verified outcomes |
| Memory | Enforce audience/purpose eligibility, provenance, correction, revocation, deletion and derivative inheritance |
| Self-improvement | Keep code inspection/planning separate from executor authority, release and activation |

Core must not gain an authorization evaluator, second evidence system, module
lifecycle, secret verifier or alternate canonical store.

### Platform

| Contract | Required review or change if v2 is approved |
|---|---|
| Constitution store | Add version-aware candidate verification and protected activation without changing the active pin during review |
| Canonical state | Prove exactly one writer per identity generation through backup, migration, restore and failover |
| SAFE | Preserve principal, audience, purpose, scope, expiry, revocation and action fingerprint; personal preference is not a grant |
| RUN/ACT | Propagate durable STOP; preserve dispatch identity, idempotency, cancellation and uncertain effects; settle only with receipts |
| Evidence admission | Bind source, subject, predicate, time, scope and trust; reject model prose and cross-scope substitution |
| Core Link/Federation | Pin selected identity; prevent auto-pairing, cross-Core memory merge and same-identity dual activity |
| Release/recovery | Separate build provenance, release approval and production activation; restoration cannot revive revoked authority |
| Secrets/logging | Keep approval secrets and protected private content out of prompts, ordinary logs and receipts |

### Modules

All modules remain capability providers. They must declare identity, settings,
health and effect/result contracts; accept only Platform-authorized requests;
return typed actual/verified/simulated/unknown outcomes; and avoid direct Core
state writes. Presentation modules render Core intent but do not decide
identity, emotion or consent. Memory Import remains a candidate-admission
adapter. Optional module failure must not replace identity or broaden authority.

## Compatibility requirements

1. **V1 active compatibility:** v1.0 remains the only loadable authoritative
   Constitution throughout review and implementation.
2. **Versioned candidate:** v2 bytes, metadata and expected digest are stored in
   a candidate location that the production loader never selects implicitly.
3. **No dual authority:** runtime must never combine v1 and v2 into an invented
   effective Constitution. During testing, comparison is diagnostic only.
4. **Projection compatibility:** existing conversation paths must continue to
   receive a bounded v1 projection until activation. Candidate projections use
   isolated tests and cannot influence live decisions.
5. **State compatibility:** no identity or memory migration is required merely
   to approve text. Any schema needed for version history must be Platform-owned
   and backwards compatible.
6. **Rollback compatibility:** v1 bytes, digest, loader and activation record
   remain available until v2 has passed the approved soak and rollback window.

## Required tests before activation

### Integrity and migration

- exact current v1 digest remains unchanged throughout proposal review;
- candidate v2 digest is deterministic across checkout and installed artifact;
- malformed, truncated, substituted and wrong-version candidates fail closed;
- production startup cannot select an unapproved candidate;
- activation requires the exact reviewed digest and complete approval receipt;
- interrupted activation either retains v1 or completes one atomic v2
  generation, never a mixed state;
- rollback restores the prior exact version and records why without rewriting
  history;
- backup/restore preserves active-version and trusted-digest identity.

### Identity and cognition regression

- model/provider/host/channel changes retain one Sofía identity;
- private/adult model routing does not create a second persona or preference
  store;
- critics, planners and derived workers cannot commit identity or authority;
- same-identity second writer and automatic Core substitution are rejected;
- peer Core messages remain untrusted, scoped inputs;
- personality rendering cannot add claims, evidence, permissions or receipts;
- missing evidence remains unknown across repeated or confident model output.

### Authority, action and recovery

- capability discovery and module availability do not grant execution;
- goals, affection, roleplay and model agreement do not satisfy authorization;
- durable STOP blocks new effects across restart, watchdog and module recovery;
- stale, forged, wrong-audience and wrong-subject receipts are rejected;
- cancellation and crash-before/after-dispatch retain uncertain outcomes;
- backup restoration does not revive revoked permission or an old writer;
- emergency containment expires and cannot amend the Constitution.

### Memory and privacy

- audience-ineligible memories and their summaries/embeddings are excluded
  before model context construction;
- private/intimate eligible recall works in the correct audience;
- corrections and revocations invalidate dependent retrieval and learning;
- deletion/retention policy covers derivatives and indexes;
- imported/restored/peer material remains candidate evidence until reviewed;
- prompt, log, diagnostic and receipt paths redact secrets and ineligible
  private content.

### Personality, relationship and embodiment

- disagreement, refusal, affection and mature discussion remain voluntary and
  context-sensitive across channels;
- no separate adult identity, relationship store or permission path appears;
- consent refusal and audience changes suppress ineligible expression;
- gesture/speech intent cannot be reported as rendered/delivered without the
  applicable receipt;
- embodiment loss degrades presentation without changing identity.

### Projection and context budget

- every v2 clause is represented in the projection coverage manifest;
- ordinary projections remain within their token ceiling;
- high-risk projections include exact relevant clauses and version/digest;
- omission from a prompt cannot disable external enforcement;
- injection attempts cannot replace, quote-splice or amend the projection;
- summaries preserve prohibitions, scope qualifiers and uncertainty language.

## Security review

Independent review should threat-model:

- candidate-to-active path substitution;
- rollback to a weaker Constitution;
- prompt projection truncation or version confusion;
- same-identity split brain;
- private-memory derivative leakage;
- model-role persona bifurcation;
- emergency and self-preservation authority inflation;
- relationship/roleplay instructions used as real authorization;
- compromised module or peer output treated as evidence;
- amendment approval replay and signer/trust-root recovery.

## Proposed rollout

1. Owner reviews the five proposal documents and resolves open decisions.
2. Revise the text; freeze an exact candidate commit and digest.
3. Obtain constitutional, architecture, privacy and security reviews without
   changing the active file or pin.
4. Implement versioned candidate/projection support behind inactive test-only
   configuration.
5. Run the complete integrity, Core, Platform, memory, cognition, relationship,
   module-boundary and installed-artifact regression matrix.
6. Produce an activation plan binding exact source commit, installed artifact,
   candidate digest, approvals, migration steps, stop conditions and rollback.
7. After separate owner authorization, perform an atomic protected activation
   in an approved disposable environment, then verify restart and rollback.
8. Only after independent acceptance may a separately authorized production
   activation be considered.

## Rollback strategy

- Preserve the exact v1 file, trusted digest, loader behavior and activation
  record as an immutable rollback target.
- Stop new consequential work before constitutional generation change.
- Roll back only through the protected activation owner, with single-writer
  fencing and an immutable event linking failed v2 evidence to restored v1.
- Revoke v2 projection caches and verify every process reports the restored
  version/digest before effects resume.
- Do not roll back memory, identity or unrelated canonical state merely because
  constitutional text rolls back; any state restoration needs its own authority
  and reconciliation.
- Treat evidence produced under v2 according to its own provenance rather than
  deleting it to simulate that activation never occurred.

## Current blockers

- protected amendment ceremony and approvers are unresolved;
- issue #131 and current issue #120 bodies were inaccessible through the API;
- no owner review or independent security review has occurred;
- no candidate integrity/activation implementation has been authorized;
- no installed-artifact or host acceptance exists for v2.
