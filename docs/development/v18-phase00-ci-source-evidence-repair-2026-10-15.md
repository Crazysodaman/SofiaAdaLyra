# V18 Phase 00 CI source-evidence repair (2026-10-15)

Reviewed base main: `088f7450c1b165d43fcf5f5c57548ca0d0787861`.

## Observed failures at that exact revision

- V18 Next 50 Review, run 38664972741, Ubuntu job 116194712557 and Windows job 116194712782: two tests fail because the historical review's CA-910 `original_status=unassessed` is compared against the canonical ledger's later `partial_wiring`. This is legitimate ledger progress, not a new acceptance.
- Package Tests and Debian Release Candidate Build: `test_conversation_workspace_projection.py` expects workspace observation text in SYSTEM even though the production assembler now correctly isolates untrusted path/source text in a USER-role JSON source message.
- Other independent CI failures remain open, including LIFE verified-artifact completion receipts. This batch does not relax those predicates.

## Code correction and safety review

`v18_next50_audit.audit_next50` continues to require exact ID, phase, source topic, source paths, design review and no fabricated acceptance. It now treats the review's original status as an immutable historical snapshot. A current canonical status may advance monotonically only when separately recorded source-evidence commits exist; backwards status and unsupported promotion still fail closed. The original CA-910 task remains `partial_wiring` and not accepted.

The provider projection tests assert that observed workspace source text is in USER, not the canonical SYSTEM message, while preserving explicit operational questions and proactive startup evidence. This tests the stronger source/authority separation rather than restoring unsafe SYSTEM inclusion.

## Evidence limits

Prepared changes are not a Gate 1-4 award. Test outcomes and commit CI must be independently checked at the new exact SHA. No Venus/Artemis host access, canonical database mutation, user consent change, external review, or live deployment is claimed.
