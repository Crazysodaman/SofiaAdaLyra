# PKG-REL: evidence-based absence appraisal preflight

**Status:** isolated branch candidate, not integrated, Windows-tested, accepted, merged or deployed. Reuse the existing canonical relationship and EmotionalJournal; do not add a competing emotion database.

## Coded slice

`src/sofia/relationships/absence.py` computes a bounded elapsed-time appraisal from a caller-verified last-contact event for the *same authenticated actor*. Unknown, cross-person, future-dated, malformed or absent evidence never creates a known absence or outreach. A verified gap may yield an optional reunion expression candidate. An outreach candidate additionally requires explicit opt-in and a nonquiet/nonbusy period. **No message is sent**, no emotional state is inferred and no claim is made of having thought during shutdown.

**Focused command:** `PYTHONPATH=src python -m pytest -q test/test_relationship_absence.py`. GitHub branch checkout, Windows, CI, full suite and supervised multi-session personality quality **not run at commit time**; record fresh results against the actual branch SHA. Test-only sample actor IDs are not real Discord identifiers.

## Review when REL is reached

- Tie verified actor identity and source event to authentic conversation/MEM records; distinguish an observed last-contact event from user's reported schedule, unavailable periods, process downtime, and unverified wall-clock drift.
- Connect the appraisal to existing `EmotionalJournal` and reviewed relationship preferences rather than inventing actual sadness, loneliness or distress. Allow nuanced but non-guilt-inducing welcome with silence as an option, and correction when the timestamp or relationship inference was wrong.
- ACT/SAFE/RUN separately own outbound eligibility, delivery grants, frequency caps, opt-out, stop, quiet-hours policy, actual execution and acknowledgments. The candidate bool is **never authorization** to notify Sparks. Do not enable spontaneous contact by merging this file.
- Review actual model outputs for warmth, no clinginess, no exclusivity or pressure, no fictional offline processing, variation and natural technical answers. Preserve original CORE → INTERACT → MEM acceptance order and Sparks-only initial release; general multi-user relationships remain deferred.
