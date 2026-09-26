# PKG-REL: observed-contact reunion, offline preflight

**Status:** isolated source/tests on a package branch; neither merged nor wired to the real conversation service. No evidence of subjective feeling or actual missed-person experience is implied.

## Implemented

`SingleUserPresence` keeps last observed contact for exactly one configured principal and rejects another principal, replayed message IDs and out-of-order timestamps. It projects an elapsed gap only when a real contact timestamp is supplied; an empty history yields `no_evidence`, clock rollback yields `clock_uncertain`. No generated text, background thought, automatic notifications or implicit permissions. In-memory only, with no user credentials or production database access.

**Test:** `python -m pytest -q test/test_rel_presence.py` using editable install or `PYTHONPATH=src`. Equivalent staged code passed **28 focused offline tests** in a Linux Python container on 2026-09-21. A test of the actual GitHub checkout, Windows, full repo suite and supervised live conversational quality has **not** run.

## At integration review

- Reuse canonical ConversationStore/MEM originals and identity boundary instead of adding a second long-term relationship database. Only a trusted platform/session adapter may assert who spoke, when and which original message ID supports it. Store or restore dedup IDs and last-contact information with reviewed retention and correction rules.
- Distinguish user contact from system restart, synthetic lab and background reflection events; a process restart does not count as contact. Handle clock skew, deletion and device sync. Do not infer emotion, illness, consent, rejection, loneliness or intent from an interval.
- REL/CORE can optionally use elapsed-gap evidence to choose context-sensitive reunion wording; silence is valid. ACT owns separately authorized outreach with quiet hours, frequency caps and stop/mute. No guilt, obligation, escalating check-ins or invented offline thinking.
- Test the actual Sparks-only Discord DM account gate when reached. Multi-user relationship sharing remains deferred; do not confuse a local string ID with authenticated identity.
- Run pinned Windows focused/integration/full tests and human-reviewed real model interactions. Record actual result and source revision in VERIFY. No deployment or Constitution/identity edits in this slice.

**Release order unchanged:** CORE → INTERACT → MEM → Sparks-only Discord → verified RUN 24/7 → separately authorized internet search.
