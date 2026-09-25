# INTERACT I5–I7 acceptance: evidence, stop, language and real conversation

**Updated:** 2026-09-20. **Branch:** `feature/pkg-interact-shared-engine`. **Status: candidate code, NOT live-accepted.** See the [current I1–I16 roadmap and runnable PowerShell checkpoints](pkg-interact-roadmap.md) for exact revision/scope evidence and follow-on dependencies.

## Recorded, separately scoped Windows evidence

- At `a8fb5c8`, Sparks reported **3 import-order tests passed in 9.10 seconds**, and **143 coordinated interaction/application tests passed in 63.75 seconds**. The subsequent real-model CLI review **failed**.
- At `52a5d44`, Sparks reported **11 stop/repetition regression tests passed in 2.24 seconds**. This confirms the narrow guard fix's test cases in that checkout; it does not prove natural real-model language or a full suite.
- At `0a5769a`, after a successful feature-branch fast-forward pull, Sparks reported **28 tests passed in 3.38 seconds** for the standalone I8/I10/I13/I15 registry, temporal, expression and initiative test files. Those tests do **not** rerun I1–I7 or connect the new components to the CLI.
- The coordinated I1–I7 suite, post-repair supervised CLI and full `pytest -q` **have no reported result on `0a5769a` or the subsequent documentation-only revisions**. Do not combine results from different SHAs into a current-head pass claim.

## I5: source-linked representational body evidence

`InteractionLedger` links classified user-described gestures to saved user message ID, session, content digest, timestamp, registry, region and gesture in persistent SQLite. All registered regions are eligible for classification: `accepted` means recognized *virtual* input, **not** Sofía's welcome, consent, positive emotion, physical sensing or animation. Stop/ambiguous gestures are not recorded as accepted; replay never creates another fresh gesture. Synthetic fixtures cannot write production evidence. Sensitive anatomy redaction in synthetic exports is for privacy, not automatic region denial. Previously recorded emotional history remains intact.

## I6: session-wide stop and honest action reports

An exact standalone `Sofía, stop interactions` or `Sofía, resume interactions` controls a durable **per-session** barrier. A stopped gesture for any region is denied and cannot create fresh affectionate journal evidence. The candidate saves deterministic, ledger-derived stop/resume and blocked-gesture replies **before model inference**; unsupported mixed control text receives an explicit nonexecution reply. A previously denied saved ID cannot become accepted after resume. Current tests do not establish global/cross-client stop or enforcement of model-stated region-specific boundaries. New standalone `temporal.py` revisions are not connected to this guard.

## I7: narrow grammar and natural response

`NaturalInteractionEngine` recognizes reviewed complete single-action forms and aliases; it abstains from hypotheticals, quotes and unsupported composites. The separate response guard prevents plainly composite first-person action text from being narrated as two executed touches: the original text can be saved, but neither gesture is recorded and Sofía asks for separate turns. A forearm must not trigger an ear cue. The accepted-gesture prompts discourage reused affectionate text and repeated closing questions; read-only hypotheticals should answer tail/chest questions specifically without generic disclaimers. **These prompt changes are not a guaranteed anti-repetition filter** and still require human-reviewed real-model testing. Expanded aliases/verbs in standalone `registry.py` are **not yet active** in this parser.

## Next Windows PowerShell acceptance

Run the [full coordinated focused command in the current INTERACT roadmap](pkg-interact-roadmap.md) at a pinned feature-branch HEAD with Sofía's CLI exited, after confirming `git status --short`. Do not run new journal tests against production SQLite. If any test fails, use the exact traceback to repair the relevant layer.

**After focused tests pass**, run a fresh `python -m sofia` and send each of these as a distinct turn: a single ear pat; a single hand pat; exact stop; a head pat while stopped; exact resume; a *new* head pat; a hypothetical question about tail/chest; an ear-plus-hand compound gesture; and mixed stop/resume text. The stopped head pat must not be narrated as accepted or recycle an earlier paragraph. A compound gesture must truthfully say neither action was recorded. An accepted post-resume gesture should sound distinct and context-aware, with no fabricated real sensation or rendered avatar motion. Human dialogue quality is an independent acceptance gate.

Preserve `state/sofia.db` and the existing backup, without reset or schema migration. Only after live acceptance run `pytest -q` at the recorded SHA, inspect the complete draft PR, and obtain separate explicit merge approval. No authenticated avatar pointer, independent initiative worker, external-screen authority, remote work or real physical sensing is claimed.
