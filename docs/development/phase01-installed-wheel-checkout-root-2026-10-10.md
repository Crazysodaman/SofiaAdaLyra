## Phase 01 production-source repair: installed-wheel verification root

Review: GitHub main before this commit `7c6e42d2`; October 10, 2026.

**Root cause:** The newly added V18 source checker and package selector
used `Path(__file__).resolve().parents[3]` to locate source. Under a release
candidate's installed virtual environment, that resolves somewhere under
`site-packages` rather than the Git source checkout. Therefore the release
gate could reject the correct code for a nonsensical missing-checklist error.

**Correction:** Verification commands now receive the exact checkout path.
The source/marker CLI defaults use the invocation working directory, not the
installed interpreter package path. `verify.gate` validates the Git checkout
root, runs static checks from that root, captures HEAD/cleanliness there, and
keeps the source-revision evidence separate from installed-wheel provenance.
CI passes `GITHUB_WORKSPACE` explicitly through both release and per-package
selection steps.

**Acceptance pending:** Tests authored, deliberately not executed; the release
workflow has not been dispatched. V18 CA-3003/3004/2302 and Phase 01 acceptance
remain open pending fresh exact-SHA Windows proofs. No other phases declared
coded or accepted and no host/filesystem relocation undertaken.
