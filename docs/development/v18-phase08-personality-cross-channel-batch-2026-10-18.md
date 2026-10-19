# V18 Phase 08 | Conversational personality cross-channel regression batch

Branch: `main`  
Tasks: **CA-501, CA-508, CA-506, CA-2508, CA-3805**  
Scope: evidence-grounded conversational style, name-call behavior, small-talk economy, and shared provider quality-repair flow.

## Observed owner-host failures

Discord originally returned identity mirroring (`I am Hru`), implementation prose for `hru`, and disproportionate attachment text for `Sofía?`. Follow-up live Discord observations showed that these initial repairs could still allow verbose generic reciprocal questions and third-person narrated gestures. A malformed outfit question bypassed the canonical AVATAR self-fact path, repaired separately in the preceding batch.

Owner Windows regression run (preceding batch) reported **89 passed** across:
- `test/test_short_contact_channel_quality.py`
- `test/test_response_quality_hardening.py`
- `test/test_avatar_self_fact_query.py`

Those 89 results predate **this new batch** and are not evidence that this new batch passed.

## Implemented in this batch

- Extend the **canonical** `personality_expression_guidance` used by the cognition assembler with first-person, short-turn and fact-priority calibration. Do not introduce a Discord-only identity or personality.
- Extend the common `response_quality_issue` provider gate to identify excessive follow-up questions on a standalone social check-in and third-person narration on minimal name calls.
- Reuse the existing tool-free, one-retry provider repair/fallback boundary for both new error classifications. No new tools, external effects, storage authority, or memory mutation.
- Add deterministic regression cases to `test/test_short_contact_channel_quality.py` and assembler personality guidance contract tests in `test/test_personality_pipeline.py`.

## Outstanding full-task requirements and status

| Task | Reporting level | Open acceptance requirements |
| --- | --- | --- |
| CA-501 | **2 Audited / Partial** | Broader identity and nuanced opinions, skepticism, humor and conversational reciprocity need structured cross-domain live validation; one style patch does not complete the whole task. |
| CA-508 | **2 Audited / Partial** | Authenticated preference persistence and application across audiences, model routes and live response phrasing must be independently exercised. This batch does not change persisted preferences. |
| CA-506 | **2 Audited / Partial** | New focused tests must be executed and reviewed, then live behavior evaluated beyond the sampled patterns, including false-positive controls and repeated interactions. |
| CA-2508 | **2 Audited / Partial** | Paired same-turn Desktop/Discord/voice/avatar evaluation, provenance and renderer receipts are not proven by these provider tests. |
| CA-3805 | **2 Audited / Partial** | Real model swap/device move/channel transitions, identity continuity and fixed behavior matrix remain unverified. |

These are conservative batch-specific assessments, **not** an independent reclassification of the entire authoritative 780-task ledger.

## Local validation still required

Run on a checkout with its declared dependencies:

```powershell
python -m pytest test/test_short_contact_channel_quality.py test/test_response_quality_hardening.py test/test_personality_pipeline.py test/test_personality_expression_g9.py -v
```

Then run relevant full personality/conversation integration tests, check effects on ordinary long-form technical answers and deliberate storytelling, and execute paired supervised owner-host Desktop/Discord dialogue. CI credit requires a passing, revision-pinned workflow.

**Do not promote these tasks to Level 4 solely because test files were authored or a prior 89-test run passed.** This environment has no reachable Git checkout with dependencies for execution; the real Venus tests and CI remain pending.

## Owner-host focused verification update (2026-10-18)

Sparks reported executing on Venus (Windows, Python 3.12.10, pytest 9.1.1):

```powershell
python -m pytest test/test_short_contact_channel_quality.py test/test_response_quality_hardening.py test/test_personality_pipeline.py test/test_personality_expression_g9.py -q
```

**Result: 74 passed in 18.19s, 0 failed.** This is a user-provided live Windows test transcript, not a GitHub Actions CI run. It confirms the newest focused short-contact regression batch passed locally. It does **not** independently establish full task-level integration, Desktop/Discord/voice parity, cross-model/device behavior or CI, nor does it alone promote CA-501, CA-508, CA-506, CA-2508 or CA-3805 to Level 4. Continue with task-specific end-to-end acceptance and evidence collection.

## Superseding 15-task source audit

The Level 2 table above records the earlier five-task focused-regression checkpoint and is preserved as historical evidence. A broader, task-specific production entrypoint audit subsequently assessed eleven of fifteen selected Phase 08 tasks as **Level 3 (production coded)** and four as **Level 2 (partial)**. The current scoped status evidence and outstanding gaps are in docs/development/v18-phase08-15-task-level3-source-audit-2026-10-18.md and docs/development/v18-phase08-personality-status-evidence.json. No new Windows pytest or CI run has been executed for that later coding batch; neither report claims Level 4 or Level 5.
