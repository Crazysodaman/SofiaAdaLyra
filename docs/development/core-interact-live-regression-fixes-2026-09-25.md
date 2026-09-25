# CORE / INTERACT live regression fixes — 2026-09-25

**Source:** supervised local `python -m sofia` run on `main` at `265e6378b03cd4f9367103346d8ea7ac69130275`. Subsequent commits through `2875a0a` changed documentation only, so the runtime findings remain valid for current code.

## Primary ownership

- **PKG-CORE:** authoritative self-grounding, natural personality quality, follow-up coherence, continuity wording.
- **PKG-INTERACT:** virtual/body gesture recognition, colloquial and bilateral anatomy resolution, grounded interaction responses.
- **Supporting system/runtime fixes:** Windows system inspection datetime parsing and deterministic continuity projection.

This is **not** a new package. AVATAR, REL, SOCIAL, RUN and Discord stay out of the repair unless a failing regression proves their code is required.

## Pinned live failures

1. **Windows system inspection**
   - User: “tell me what computer are you on?”
   - Result: system inspection failed on Windows WMI/CIM datetime parsing.
   - Fix: accept the actual PowerShell/CIM datetime representation while preserving timezone-aware evidence.

2. **Tool-failure follow-up coherence**
   - User: “what was the issue?”
   - Result: Sofía answered about unrelated workspace/Git state instead of the immediately preceding inspection failure.
   - Fix: preserve/reproject the preceding tool result/error for short follow-ups.

3. **Contradictory continuity wording**
   - Startup: “workspace change count of 234” followed by “No file changes were observed”.
   - Fix: deterministic continuity summary must not contradict `workspace_change_count` / `has_workspace_changes`.

4. **Canonical embodiment/outfit denial**
   - User asked what outfit Sofía had on or wanted to change.
   - Result: “I do not have an outfit or physical form.”
   - Fix: authoritative self-state must win over generic AI priors. Canonical representational body/clothing already exist on `main`.

5. **Generic affectionate fallback**
   - User said they were in need of cuddles.
   - Result: generic “I can’t provide physical cuddles / emotional support” assistant boilerplate.
   - Fix: answer naturally within representational/relationship context without falsely claiming physical-world contact or sensation.

6. **Bilateral anatomy resolution**
   - “touches your hand” -> generic clarification because `hand` resolves to left/right.
   - “pats thighs” -> generic clarification because plural/group region handling is incomplete.
   - Fix: reviewed bilateral/group semantics that preserve ambiguity when needed without degrading into generic assistant confusion.

7. **Colloquial anatomy routing**
   - “gropes tits” -> raw-model canned refusal because `tits` is not a reviewed anatomy alias even though the intimate-action verb path exists.
   - Fix: reviewed colloquial aliases should remain inside trusted INTERACT routing. No anatomy term, gesture, or sexual wording creates consent, attraction, desire, or a discrete sexual mode.

8. **Canned clarification/refusal quality**
   - Replace generic “I’m not sure what you mean” / “Let’s talk about something else” fallbacks with Sofía-specific, context-grounded responses while preserving independent boundaries.

## Regression acceptance

Use the original live conversation as a pinned supervised regression script after source fixes.

Required:
- existing CORE grounding tests stay green;
- existing INTERACT stop/boundary/ledger/source-attestation tests stay green;
- exact canonical body/clothing cannot be denied by model priors;
- Windows host inspection returns observed host evidence instead of datetime failure;
- short follow-up questions reference the immediately relevant tool outcome;
- bilateral/plural/colloquial gestures remain inside trusted INTERACT semantics;
- no fabricated physical sensation or real-world execution;
- no discrete sexual-mode switch;
- no forced positive/negative response based solely on anatomy;
- CLI and Discord continue to share the same conversation behavior;
- focused tests, surrounding regressions, full suite, then supervised real-model replay must pass before closure.

## Dependency note

After this repair, **PKG-SOCIAL** remains the next major architecture package because authenticated Discord owner identity still is not projected into cognition as Sparks.
