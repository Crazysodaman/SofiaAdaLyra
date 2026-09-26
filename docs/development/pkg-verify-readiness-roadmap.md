# PKG-VERIFY | branch readiness roadmap

**2026-09-21 | active draft PR #8 | baseline head `3333890570dbf942f2a97d62eb70def850b0b0ff`.** [Alternative PR #10](https://github.com/Crazysodaman/SofiaAdaLyra/pull/10) was **closed unmerged**, not a second verification authority. Companion `pkg-verify-evidence-review.md`, original VERIFY and shared release contracts.

## Existing work / evidence

Typed revision-specific verification evidence and gate assessment distinguish offline/integration/live, missing or blocked checks, newer-failure precedence and actual-system requirements. **27 focused tests passed on equivalent isolated Linux code**; current GitHub checkout/Windows/CI/full suite and authenticated runner evidence NOT RUN. A caller-supplied `actual_system=True`, revision or `passed` is not independent machine attestation.

## Review and test gates

1. Inspect current VERIFY/test/CI traces, repo test markers, pinned Python/Windows environment and active PRs. Select one evidence schema; reconcile #10's useful coverage only if needed, avoid dual or contradictory gate evaluators.
2. Bind evidence to **actual checked-out commit tree**, signed/trusted runner identity, command, environment, timestamp, source logs/artifact hash and explicit test subset. Capture exit codes and failures/skips even if upstream model or user reports differently. Do not sum isolated fixture counts into a full-suite claim.
3. Specify reviewed `not applicable` exceptions separately from `not run`/`failed`; exceptions require owner, reason, scope and expiry and cannot silently waive a mandatory live/security gate. Older passing results cannot hide later failures. No automatic merge or deployment authority from a green report.
4. Run targeted tests on the actual branch; current Python 3.12.9 Windows coordinated/full pytest after INTERACT checkpoint; add negative CI/evidence tamper, replayed logs, missing files, fake remote/hardware receipts, stale SHA, rerun races, unexpected skip and altered test collection. Report actual failures, timings, hardware and personality/latency checks on live components when available.
5. Establish reproducible package review cards (SHA, exact diff, test commands/outcomes, changed data/schema, authority, privacy/security, rollback, reviewer). Perform independent human release review before merge/deploy.

## Decisions at VERIFY review

Trusted runner/CI host and artifact retention, signature/evidence verification method, which checks are mandatory per package and which can ever be N/A, how long quality/latency baselines remain valid, who signs a final release. The model cannot certify itself.

**Exit:** offline schema/gate tests only, NOT a release decision. Real attestation, Windows/full suite and supervised live acceptance NOT RUN. No merge/deploy.
