# PKG-CORE | Cognition, identity, continuity and conversational quality

**Branch:** `feature/pkg-core-foundation`, forked from `main` at `2141879`. **Status:** planning plus a narrow, unintegrated startup-evidence helper. Do not confuse this branch with existing mixed-scope CORE/Artemis PR #1. Neither branch is merged or deployed by this roadmap.

## Outcome and current evidence
Keep Sofía Ada Lyra's identity, Constitution, representational embodiment and memory independent of the LLM, host and process. Existing runtime, verified Constitution hash, identity/personality stores, cognitive assembler, CLI and continuity observations are foundations, not a passed release. Earlier 1,195-item Windows run has no verified complete acceptance report here. INTERACT's failed live personality transcript is a cross-package signal, not a CORE pass.

## Implementation slices
1. **C0 source audit:** pin exact target SHA, read full runtime/config/provider/CLI assembly and available acceptance tests. Classify each self-statement as authoritative, observed, inferred, historical or unknown. Identify latency and context sizes with real measurements rather than guesses.
2. **C1 restart evidence:** group file changes into one non-canned, evidence-backed message. Ignore self-generated DB churn where independently verified. Record runtime IDs and observed timestamps, not memories or thoughts while offline. The new `src/sofia/package_foundations/core.py` is a side-effect-free `StartupEvidence` prototype, not live wiring.
3. **C2 context prioritization:** explicitly audit the new INTERACT conversational Constitution projection against the complete verified source and safety obligations. Preserve full source and integrity checking; avoid silent contradictory summaries. Bound history through separately reviewed relevance and original-ID preservation.
4. **C3 personality and model evaluation:** compare identical prompts on current Ollama and candidate engines with pinned settings, warm/cold context and repeated trials. Score *observations* such as generic disclaimers, invented preferences, repetitive questions and Windows diagnostic precision without claiming a model is intrinsically Sofía.
5. **C4 runtime integration:** wire only reviewed components into the composition root; add provider-independent tests for restart evidence, unknown facts, conflict resolution and failure paths. Keep actual tool authorization outside model text.
6. **C5 supervised acceptance:** live startup, repeated affection, serious disclosure, hypothetical, identity, contradiction and diagnostic conversations across restart, with an audited transcript and timing evidence.

## Contract, test and rollback gates
- Source and actor provenance cannot be fabricated. `UNKNOWN` must remain unknown; prior model text cannot override verified identity. A summarized Constitution is a provider projection, not a replacement or enforcement mechanism.
- Run `python -m pytest -q -x test/test_pkg_core_foundation.py` on this branch, then affected runtime/context tests and ultimately the full suite **at its current SHA**. The new tests are not reported as passed yet.
- No state reset, auto-start, model download, Constitution amendment or production migration. Back up and review any future DB migration on a copy. Capture live performance and failure evidence before proposing a merge.
- **Dependencies:** CORE remains separately reviewed; INTERACT, MEM and REL consume its identity/context outputs but cannot import experimental code across unmerged branches. Existing CORE/Artemis PR #1 requires its own reconciliation, not a force-push.

**Release:** independent security/identity review, exact-SHA full tests, supervised live approval and a separate merge decision. This roadmap or prototype alone satisfies none of those gates.
