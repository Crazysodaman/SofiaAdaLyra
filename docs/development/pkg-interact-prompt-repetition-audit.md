# INTERACT prompt repetition audit (2026-09-21)

**Status: candidate cleanup, not live acceptance.** User-reported Windows checkout at `45d8b67`: 20 focused tests passed in 14.97 s; 274 coordinated interaction/application tests passed in 105.90 s. These results predate the cleanup at `fa08bb2`; never transfer their passing status to later commits.

## Observed A/B results, not assumptions

`python -m sofia.interaction.ab_probe` used qwen3:14b, thinking disabled, num_ctx 20000. Minimal A had 3300–3367 prompt characters; bounded-static B had 21311–23436. The synthetic probe does not use production DB or true live history. Ear, hug and hypothetical replies repeatedly used ears/tail stage directions, physical-body disclaimers and closing questions. A ear answer implied adversarial intent ("testing my boundaries") without evidence. B ear answer claimed comfort not supported by explicit preference. Both hug answers treated a *request* as an impossible physical hug rather than interpreting it as an offer in Sofía's represented world. B hypothetical distinguished discussion from actual execution but presupposed a favorable response. B technical response suggested `sc query <ServiceName>` under PowerShell instead of `sc.exe query <ServiceName>` or `Get-Service`: PowerShell `sc` can be an alias. The A technical response was a long generic checklist. All four A/B pairs were supplied in the new run; no new real CLI transcript was supplied.

## Source diagnosis and targeted change

Three overlapping conversational-instruction sources existed: `personality_expression_guidance()` inside the canonical assembler, a general `CURRENT-TURN EXPRESSION PRIORITY` appendix in `ConversationalContextAssembler`, and a task-specific `interaction_prompt()` or `action_prompt()`. They restated variations of no repeated questions, no generic physical-body disclaimer and concise in-character replies. The full personality profile also emphasizes natural varied expressions. This confirms prompt **instruction overlap**, not the precise cause of repeated model output.

At `09e8778`, removed only the redundant general-purpose appendix from `src/sofia/cognition/conversation_assembler.py`. At `fa08bb2`, updated `test/test_conversational_context_projection.py` to require one canonical personality-expression section, the bounded constitutional projection once, no redundant appendix, and preserved request/interaction-message order. Constitutional file/hash, loaded runtime verification, full-text exceptions, stop and authorization are unchanged. No database, bot, worker or external operation was touched. The task-specific interaction guards remain; do not deduplicate safety semantics simply because the prose overlaps.

## Remaining engineering gates

1. With CLI closed, fast-forward pull feature branch without resetting or stashing user changes. Run focused projection and A/B-construction tests and the coordinated interaction/application subset at the new exact SHA. If either fails, diagnose the first traceback.
2. Run synthetic A/B again if useful, explicitly acknowledging that A lacks B's canonical interaction classification and Constitution, so it is **not** an isolated test of prompt length. Prefer a future controlled probe in which grounding, case-specific facts and generation settings are identical and only one tested context variable changes.
3. Run supervised real `python -m sofia` multi-turn conversation. Examine offer-versus-described hug, neutral head/ear/hand gestures, hypothetical discussion, stop/resume and first diagnostic on Windows. Check actual saved evidence if alleging recorded gestures or preferences. No canned repetitive questions, invented preference, unsupported physical sensation, or unverified delivery claims.
4. Independent CORE/SAFE review of bounded constitutional projection, then complete fresh `pytest -q`, full PR/security/privacy/migration review on copies and separately authorized merge.

**Unresolved:** model may continue generic responses even with nonduplicate instructions; `sc` alias issue proves instruction-following is not deterministic. This cleanup is deliberately not an output-rewriting filter, permission change or model swap. PR #2 stays draft and unmerged.
