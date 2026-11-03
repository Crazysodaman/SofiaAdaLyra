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

## Exact version migration plan

### Current trust model observed

The active Constitution is loaded from
`src/sofia/core/constitution/constitution.md`. Its trusted reference is the
single SHA-256 value in `constitution.sha256`; the verified active digest during
this review is
`f30afedf195f77907d32a108ca35d4db751646bde3fd902be66e7b78f4b89dc0`.
No Constitution-specific signature file or signature-verification path was
observed in the current Constitution store. Release signatures elsewhere in the
repository must not be assumed to authorize constitutional amendment.

### Candidate preparation

1. Resolve every owner decision and freeze the exact UTF-8 v2 bytes at a
   reviewed commit. Define newline normalization before calculating identity.
2. Calculate SHA-256 from those exact bytes using the same normalization as the
   canonical loader. Record source commit, byte length and digest in a candidate
   manifest outside the active Constitution path.
3. Obtain the protected-amendment approvals over the tuple `(version,
   predecessor_digest, candidate_digest, source_commit, activation_plan_digest)`.
4. If a signature envelope is adopted, use an independently approved signing
   identity and include algorithm, key ID, trust-root generation, signature,
   approval references and expiry/revocation semantics. A test key, GitHub build
   attestation or ordinary release signature is not automatically constitutional
   authority.
5. Verify candidate digest, approval/signature envelope and predecessor against
   an installed artifact in a disposable environment. Do not modify the active
   pin during candidate testing.

### Atomic activation

1. Enter the approved maintenance state, apply durable STOP and drain governed
   effects without changing identity or memory.
2. Verify the active predecessor bytes/digest, canonical writer generation,
   backup/rollback artifact and exact candidate approvals again.
3. Stage candidate text, trusted digest and activation metadata as one protected
   generation. The runtime must never observe v2 text with the v1 pin, v1 text
   with the v2 pin, or projections from both generations.
4. Commit the generation atomically through the one canonical Platform owner.
   An interrupted commit must resolve to complete v1 or complete v2.
5. Restart/reload only through the reviewed mechanism, verify source and
   installed bytes, then require every Core/model worker and projection cache to
   report the v2 version and digest before effects resume.
6. Run identity, privacy, SAFE/STOP, memory, cognition, channel, module-absence,
   recovery and rollback smoke tests. G8 physical acceptance remains a separate
   prerequisite for production GO.

### Old-state compatibility

- V2 interprets existing identity, personality, relationship and memory rows; it
  does not create a second store or rewrite them merely because constitutional
  text changes.
- Existing records lacking newer scope/provenance fields remain subject to the
  current conservative eligibility and migration contracts. Missing metadata
  does not become permission or public scope.
- Existing approvals, grants, STOP state, revocations, writer generations,
  receipts and deletion records retain their Platform meaning. Constitutional
  migration cannot refresh or broaden them.
- V1-era memories and derivatives remain governed by their recorded audience,
  provenance, correction and deletion state. V2 does not retroactively assert
  that unverified records satisfy its evidence rules.
- No schema migration is justified unless a separately reviewed Platform
  implementation proves one is necessary. Any such migration needs independent
  backup, forward/rollback compatibility and canonical-writer fencing.

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

### Rollback execution

1. Apply STOP and drain effects; capture the reason, v2 digest, failing evidence
   and current writer generation.
2. Verify the immutable v1 bytes and trusted v1 digest above, plus the authorized
   rollback receipt. If constitutional signatures are introduced, verify the
   archived v1 activation/rollback authorization under its recorded trust-root
   generation; do not sign old bytes with a new unreviewed key merely to make
   rollback pass.
3. Atomically restore the v1 text/pin/version tuple as a new activation event,
   never by deleting v2 history.
4. Invalidate all v2 projections and caches. Verify every worker reports v1's
   exact version/digest before effects resume.
5. Re-run v1 integrity, identity, authority, STOP, privacy and state-compatibility
   smoke tests. Keep data created under v2 and apply the governing data contract;
   do not restore an older canonical database unless separately authorized.
6. Preserve the rejected v2 artifact, approvals and failure evidence for review;
   revoke its activation authorization if applicable.

## Current blockers

- protected amendment ceremony and approvers are unresolved;
- full issue #131 and #120 bodies/comments remain inaccessible through the API,
  although the owner-supplied controlling requirements are reconciled;
- no owner review or independent security review has occurred;
- no candidate integrity/activation implementation has been authorized;
- no installed-artifact or host acceptance exists for v2.
