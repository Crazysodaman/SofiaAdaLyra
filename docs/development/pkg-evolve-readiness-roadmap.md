# PKG-EVOLVE | branch readiness roadmap

**2026-09-21 | draft PR #19 | baseline head `fa42f02544ba3f8a0097730b3a729b930abb41da`.** Companion `pkg-evolve-amendment-review.md`, original controlled-evolution/Constitution-integrity contract. A model cannot authorize a change to its own safeguards or identity.

## Existing work / evidence

Immutable amendment proposal model includes target identity/Constitution, expected and proposed SHA-256 digests, evidence, reason, expiry and rollback plan; inspector flags source mismatch, expiry/clock uncertainty and explicit review. **24 focused tests passed on equivalent isolated Linux source**. A string containing a digest proves neither actual file content nor approval. There is no sign-off, executor, migration, rollback or protected file mutation API. No live amendment performed.

## Work and acceptance gates

1. Pin actual canonical identity and Constitution files/manifest versions, existing integrity verifier and restore path. Inventory who may propose, independently inspect, authorize and apply protected amendments. Ordinary Git development permission, conversational request or model proposal is insufficient approval.
2. Separate non-protected user preferences and correction workflows in MEM/REL from **protected** identity/constitutional changes. Proposal retains source and immutable before/after digests, human-readable semantic diff, authorized signer/evidence, tests, expiry and rollback. Never let memory override canonical protected facts.
3. Implement any eventual privileged executor separately behind SAFE verified authorization, atomic writes and back-up, integrity check before/after, post-restart validation, full audit and independent rollback. Reject mismatched SHA, forged sign-off, stale clock, partial writes and incompatible version. Do not add a self-approval path.
4. Run exact-branch/Windows tests, negative tamper/replay/race tests and a simulated amendment using a **disposable copy**, preserving production state. Then CORE/SAFE/VERIFY review and a separate explicit decision before any real protected-file change. Verify no model swapping or prompt projection changes the independent canonical identity.

## Decisions requiring explicit review

Who can approve and countersign a protected amendment, key custody and recovery, how disagreements and urgent stop work, compatibility/migration format and rollback approval. These are intentionally unspecified and not inferred from routine repository commit authorization.

**Exit:** offline proposal checks only; actual file-hash attestation, trusted approvals, privileged executor, full-suite/live amendment = NOT RUN. No merge, deploy or protected-state edit.
