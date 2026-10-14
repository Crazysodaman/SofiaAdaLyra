# CA-1208/CA-1203: verified history does not acquire SYSTEM authority

2026-10-14. Existing `ConversationService._build_request` already
restricts retrieval to the authenticated current session and caps
content; that source authorization remains unchanged.

## Finding

The retrieval context wrapper previously combined trusted provenance
explanation and arbitrary original conversation excerpts into a single
`CognitiveRole.SYSTEM` message. An attacker-authored Discord/user
message or retained assistant output could therefore become privileged
model instructions after it was retrieved, despite the textual warning
to treat it as evidence only.

## Production fix

The privileged SYSTEM message now includes **only host-authored retrieval
policy**, explaining source/authentication boundaries. Each eligible
historical row is quoted as structured JSON in a separate lower-trust
`CognitiveRole.USER` message, before the actual current question.
Original role, ID and bounded excerpt remain attributable; special
characters, line breaks and role-looking strings stay serialized within
the JSON field. Source references still target original durable
conversation rows. No new writer, raw-memory projection, privilege
grant, transport or session linkage is created.

The existing continuity/restart acceptance regression now checks
real conversation assembly, quoted JSON and current question ordering.
An additional malicious persisted-history regression proves no
attacker-origin command reaches SYSTEM, while the original source
remains visible only as quoted data.

## Open acceptance

Prompt isolation reduces authority confusion but does not itself
establish injection immunity. Real mobile/Discord hostile messages,
corrected/deleted source exclusion, owner-visible memory-control
UX, independent adversarial evaluations, and final Gate 4 review
remain outstanding.
