# Upstream package status — 2026-09-23

PKG-INTERACT was accepted by Sparks and merged into `main` through PR #2 at merge commit `d6658d05c43ea6b7f86dad9c1949217c6832e557`.

## Verified closure evidence

- 97 focused Windows tests passed on the final behavioral candidate.
- A disposable real-application `qwen3:14b` four-turn probe passed with two provider calls, including a reviewed hug offer, a no-inference ambiguous-question clarification, and synthetic source-attested boundary blocking.
- Qualified repository regression: **1665 passed, 2 skipped, 1 deselected**. The deselected test was Sparks's unrelated local Ollama expectation mismatch (`context_size=18000` while expecting `num_ctx=32768`); that local edit was never merged.
- Final closure audit at `db40d58`: **60 passed**, including both deterministic SQLite writer orders, source attestation, boundary revocation, restart-persistent interaction state, live stop behavior, authorization, external authentication and cognitive-tool authority.
- PR #2 was made mergeable after the stale root roadmap was synchronized to the current 19-package roadmap.

## Upstream contract now available

Downstream branches may treat merged INTERACT as the shared text/avatar interaction foundation. They must not reinterpret that merge as renderer completion, physical sensing, Discord deployment, 24/7 operation, or broader authority.

Staged social-offer routing remains **off by default**. Optional interaction-policy tables are intentionally not auto-provisioned in production; enabling that opt-in later requires a separately reviewed production schema migration.

## Dependency order

The active dependency gate after INTERACT is **PKG-MEM**, followed by the minimum Sparks-only SOCIAL principal/audience boundary, then Discord D0-D4 through NET + UI + SAFE, then OPS/RUN deployment gates. General web/search remains later and separately authorized.

This note updates upstream status only. It does not certify, merge, deploy, or broaden the authority of the package branch containing it.
