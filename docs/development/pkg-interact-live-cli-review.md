# INTERACT: supervised Windows CLI review, 2026-09-20

**Observed revision:** `02a5a25`, user-provided Windows PowerShell transcript. **Outcome: FAILED live quality / false action claims, despite 116 focused tests passed at this revision.** This is not a full-suite result. The user created a timestamped SQLite backup before starting the app. Do not reset or overwrite that backup or their configured state DB.

## Actual observations

- Startup reported one previous runtime and 73 workspace changes, but gave a broad summary rather than specific grounded changes. No evidence in this transcript proves what each change was.
- The user put a technical question, two described gestures, an addressed stop command, another head pat and an addressed resume command **in one CLI message**. Sofía's answer claimed that she had paused and then resumed interactions, despite the exact control parser only accepting a command that occupies the entire user message. It also described the represented ear/hand as though she had no form. The saved stop state was not inspected, so do not infer unrelated previous session controls from this transcript.
- The follow-up combined a head-rub phrase, a hypothetical tail pat and a hypothetical restricted chest rub. Sofía gave a generic no-physical-body answer, failed to distinguish represented anatomy, performed action versus question and restricted policy, and offered a canned topic change.
- The model's style, emotional nuance, and personality quality remain **not accepted**. Pytest cannot certify natural dialogue.

## Patch after this observation (UNVERIFIED on Windows)

- `interaction/live_guard.py` and `InteractiveConversationService.respond`: a turn containing an embedded stop/resume but not constituting an exact stand-alone control takes a deterministic, saved conversation path. No model inference, gesture ledger, control update, or filesystem tools are called for that turn. It explicitly says no action was executed. Exact stand-alone controls still use existing persisted policy.
- `interaction/chat.py`: the accepted gesture projection now explicitly preserves canonical represented fox anatomy, discourages repetitive AI/physical disclaimers, and asks for context-specific, optional, natural expression without fabricating sensations or animations.
- `interaction/body_discussion.py`: narrow read-only hypothetical question projection states no gesture was performed and labels represented tail/head as ordinary versus chest as restricted. It never records a touch or creates a lab.
- Focused regression tests: `test/test_interaction_live_claims.py` and `test/test_interaction_live_discussion.py` cover the supplied transcript patterns and preservation of ordinary-chat behavior. **None of these new tests or the updated code have been run on the user's machine.** No live model output at the patched revision has been seen.

## Gates before acceptance

1. Pull feature branch and run the coordinated focused tests including the two new live regressions and earlier I5–I7 checks. Investigate failures without weakening tests.
2. Run a **short supervised CLI exchange, one action per message**. Confirm ordinary engineering answer first; then an individually addressed left-ear pat, hand pat, exact stop, head pat while stopped, exact resume, new head pat, tail hypothetical, restricted request. The merged-control turn should explicitly say it did not execute anything. Record actual model replies; investigate if a stock AI disclaimer, false animation/stop claim, duplicate affection or fabricated emotion reappears.
3. Review `interaction_evidence`, `interaction_session_controls` and existing emotional-event records with privacy-aware, read-only counts/source IDs when necessary. Do not infer a successful action from a model's narration. A real clickable avatar, wider grammar, global stop and external screen permissions are separate gates.
4. Only after accepting the text/headless checkpoint, execute the agreed coordinated full pytest. PR stays draft until results, diff and merge decision are reviewed. PKG-RUN remains a separate branch.
