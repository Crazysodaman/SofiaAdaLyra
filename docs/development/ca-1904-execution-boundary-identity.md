# CA-1904: exact one-time execution authority at SAFE common boundary

Current production consumers already bind an execution approval to the
canonical capability name, the full structured parameters, an expiry,
and a one-time consumption event in `sofia.db`. Several Fleet handlers
additionally checked `approved_by == "Sparks"` after consumption, but
`ExecutionApprovalVerifier` itself did not reject records attributed to a
different actor. A future handler could accidentally treat the resulting
approval object as a valid grant.

The shared SAFE verifier now checks the already-defined owner identity at
record creation **and again at the consumption boundary**, rather than
depending on each downstream executor to remember that rule. The original
canonical SHA-256 request fingerprint also rejects NaN/Infinity and
requests whose serialized structured parameters exceed 64 KiB. Changes
to exact target host, effect or epoch therefore change the approved
fingerprint and cannot borrow a previous one-time receipt. Existing
expiration and audit-chain behavior remain unchanged.

**Security limit:** The `approved_by` string is *not* independent
authentication of a human. The operator-facing CLI currently supplies it as
text. The protected per-user OS session/host authorization chain, fresh
permit for each requested action, privileged executor recheck and signed
operator approval still require CA-1904 follow-through and independent
host acceptance. Do not mistake a literal name equality check for identity
verification or permission to perform a live state cutover.

Source-code regressions were written for nonowner legacy/corrupted rows,
non-finite parameters, oversized requests, changed targets, and one-use
consumption. No tests or live actions were executed. CA-1904 remains
partially wired and unaccepted.
