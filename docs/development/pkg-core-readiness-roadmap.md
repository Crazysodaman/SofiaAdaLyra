# PKG-CORE | merged-foundation readiness roadmap

**2026-09-21 | documentation belongs to proposed master PR #4, not a new CORE feature branch.** CORE foundations from [PR #1](https://github.com/Crazysodaman/SofiaAdaLyra/pull/1) merged on 2026-09-20. The `main` `ROADMAP.md` header still incorrectly describes #1 as open and the full-suite issue as undiagnosed; this note supplies verified later status while preserving its original 13-package scope.

## Existing facts and evidence

Older Windows full suite on a previous revision: **1,150 passed, 43 failed, 2 skipped**. Shared startup path-type issue diagnosed; two narrow regression fixes committed. The subsequently reported targeted Windows set **17 passed in 125.80 s** on the updated branch. Full-suite rerun deliberately deferred by Sparks until after INTERACT; targeted pass does **not** prove full acceptance. No new tests executed by this roadmap change.

## Current release checkpoint

1. After INTERACT text/headless and live-quality gates, pin actual main + approved change revision and preserve local `state/sofia.db`, timestamped backups and unrelated working-tree edits. Run focused regressions and **fresh** `python -m pytest -q` with actual summary, failures, skips, machine/OS/model, elapsed time and SHA. Do not silently disable or xfail failures.
2. Inspect startup/restart continuity and self-scan with truthful evidence: process gaps versus unknown, grouped meaningful workspace changes without one canned response per file, omit self-generated DB churn, file integrity and actual reason for unexpected stop.
3. Supervised live Ollama/CLI review of canonical identity and constitution integrity, serious technical answer quality, warmth/optional varied gestures, natural refusal/clarification and truthful no-physical-sensor claims. Evaluate matched prompts before/after context projection including latency/VRAM/CPU and groundedness; don't attribute all issues to long prompts without evidence.
4. CORE/SAFE independently review bounded constitutional projection from INTERACT #2 for integrity, tool-bearing/full-text exceptions, actual token limits and long conversation effects. Protected identity and Constitution are not rewritten to improve a model's phrasing.
5. Before merge/release, independently review actual diff, regression failures, state/migration compatibility, backups/rollback and authorization. A merged foundation is not a deployed 24/7 service or an accepted live personality.

## Review decisions

Which real hardware/provider settings and representative live dialogue cases define acceptance; what latency/resource budget is acceptable while gaming; which startup signals are sufficiently reliable for a factual elapsed time. Current timestamp/user-specific observations must come from the host, not inference from memory.

**Status:** foundational code merged; current-revision full-suite and live quality **NOT RUN/NOT ACCEPTED**. No new feature code, deployment or protected-state mutation in this note.
