# CA-1206 production acceptance cross-product, planning evidence

Date: 2026-10-14. All nine original axes are included: model route,
source, principal, audience, modality, permission, busy state, restart
state and failure category. This produces 34,560 bounded and deterministic
combinations with six explicit hand-test scenarios, including gaming
input controls, revoked memory, untrusted Fleet, outage, uncertain action
and screen permit enforcement.

`src/sofia/verify/v18_acceptance_matrix.py` specifies the complete matrix;
`test/test_v18_acceptance_matrix.py` proves complete cross-axis coverage
and stable source-independent case identifiers. It is included in the
Phase 00 dedicated Linux/Windows CI. **Every generated case is marked
not_executed**; the test file validates the planning data structure rather
than executing 34,560 host journeys. CI success on this generator may not
be used as evidence of actual functionality, safety or Gate 4 acceptance.

The original task additionally requires real unit/integration executions
on representative cases, and six manual user journeys must be performed on
actual authorized hosts with pinned-model/source/permission receipts.
Their results must cite an exact revision and specific runner or host. No
host acceptance, canonical ledger mutation or additional background service
is performed by this patch.

## Executed bounded policy regressions (partial acceptance work)

`test/test_v18_acceptance_matrix_functional.py` now exercises production
permission and recovery boundaries rather than checking only that a matrix
row exists. In isolated CI on Windows/Linux it checks:

- Venus input refusal with an observed running game even if the tray says NORMAL;
- no bypass from a manually overridden tray;
- screen receipt denial without independent OS-picker assent, for protected
  surfaces, wrong scope and expired permissions;
- an uncertain Home Assistant or JMRI device command refusing silent replay.

These are safe deterministic tests against production policy functions and
synthetic fixture observations. They **do not** operate an actual Venus
desktop, enroll a host, capture pixels or prove physical effects. They
exercise only a subset of the six manual examples, not the full nine-axis
cross-product. CA-1206 remains open pending all original acceptance
requirements and independent review. CI success is not Gate 4 by itself.
