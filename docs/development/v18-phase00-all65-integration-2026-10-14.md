# V18 Phase 00, all 65: source-to-acceptance workstream

**Date:** 2026-10-14. **Scope:** 65 canonical Phase 00 original tasks
CA-001 through CA-5408, according to their source order, not numerical order.
**Status:** production retrieval budget defect repaired; whole-phase exact-
revision audit coded and wired into Ubuntu/Windows CI; all original tasks
retain their existing status and no Gate 1-4 proof is minted.

## Reused existing deliverables and production owners

- COGNITION v2 and its isolated baseline:
  `src/sofia/verify/v18_companion_baseline.py` and
  `docs/development/v18-phase00-baseline-evidence.md`.
- Original 30-item Phase 00 review:
  `src/sofia/verify/v18_phase00_audit.py` and
  `docs/development/v18-phase00-batch30-audit.json`.
- Canonical state/writer separation:
  `docs/development/v18-venus-artemis-topology-decision.md`.
- User-level operating layer and deferred kernel/appliance:
  `docs/development/v18-operating-layer-architecture-decision.md`.
- Source-backed scientific design, external comparisons and verification:
  `docs/development/v18-batch50-science-safety.md`,
  `docs/development/v18-batch50-references-os.md`,
  `docs/development/v18-batch50-verification.md`.
- The only acceptance authority remains
  `docs/development/v18-task-evidence.json`; other audit outputs are
  temporary read-only exact-revision evidence.

## CA-1203 production repair

Actual specific conversation retrieval previously enforced a nominal 2,400
character budget only when **more than one** message was selected. A single
50,000-character message bypassed it, injecting large untrusted text into a
SYSTEM-labeled retrieval excerpt. The existing helper now replaces only its
prompt-visible immutable copy with a clearly marked truncated excerpt. The
original persisted transcript is unchanged and selection still checks
principal/session authorization in its original caller. Source references
still refer to the original message IDs; truncation cannot be presented as
full memory fidelity. New tests cover one huge message, multiple messages,
and user-only role restrictions. This does not settle CA-1203's remaining
episodic/workspace/style/project/factual-evidence token allocation.

## All-65 source checker and CI

`sofia.verify.v18_phase00_full` validates the original fixed V18 source and
all 700 ledger records; checks all 65 Phase 00 IDs/order/task texts and paths;
reads existing Gate 4 proofs rather than counting empty checklist boxes;
rejects commit changes during inspection; emits read-only JSON/Markdown with
per-task status, source paths and remaining evidence. Empty/unassessed source
lists remain missing, not coded. The dedicated CI job runs source and real
retrieval regressions on Ubuntu and Windows at the triggering exact SHA.
It does not run Venus Ollama, live GPU telemetry, owner consent operations,
Artemis migration, VM provisioning or a 7-day soak.

## Remaining work to *actually finish Phase 00*

Design/research items require independent review of the existing research
papers and any needed technical owner decisions. CA-001, CA-002, CA-005,
CA-006, CA-007, CA-1201..1208 and CA-3101..3112 require task-specific
end-to-end evidence, source-to-effect integration, counterfactual/negative
regressions, auth/privacy/safety proof, measurements and pinned CI/host
receipts appropriate to the requirement. Distinguish design approval from
production implementation. The all-65 report enumerates every individual
gap without fabricating completion.

The current Venus canonical writer remains sole writer. No secret keys,
permission grant, production host or Fleet authority is changed. Revert
requires no data migration. The new audit is independent of canonical state.
