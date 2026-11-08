# Management response v1 | A/C exact-wire 29-vector parity matrix

**Status: REVIEW CANDIDATE, NOT ACCEPTED.** This is a published cross-language
**expected-verdict matrix** with A-009 locally observed Python verdicts. There is no current-head completed
Rust/Python CI or approved A/C joint freeze at the time this document was added.

Canonical **unchanged** fixture: `contracts/platform/management-response-parity-corpus-v1.json`
(Git blob `b63eeafe40b7895468f7ac8e0060c3bebfababa9`). Test drivers:
`test/test_ui_platform_management_response.py::test_shared_29_case_rust_python_management_wire_corpus`
and `rust/crates/sofia-contracts/src/management.rs::tests::shared_29_case_rust_python_management_wire_corpus`.
Each reads the *same literal wire strings*. Python's A-009 LOCAL results are
observed ACCEPT/REJECT outcomes from exact staged source blobs, not full
repository test runner or GitHub CI PASS. Rust remains UNEXECUTED. Final
contract parity and signed-host GO require Rust execution and independent
Team E provenance review.

| # | Vector | Expected | Meaning | Python current-head | Rust current-head |
|---:|---|---|---|---|---|
| 1 | `valid_status_explicit_null_denial` | ACCEPT | Explicit null denial on success | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 2 | `valid_typed_stop_explicit_null_data` | ACCEPT | Typed denial with null data | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 3 | `valid_typed_not_permitted` | ACCEPT | Typed denial with null data | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 4 | `valid_typed_revoked` | ACCEPT | Typed denial with null data | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 5 | `valid_typed_stale_generation` | ACCEPT | Typed denial with null data | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 6 | `valid_typed_expired` | ACCEPT | Typed denial with null data | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 7 | `valid_typed_unavailable` | ACCEPT | Typed denial with null data | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 8 | `valid_settings_unicode_line_separator` | ACCEPT | U+2028 allowed | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 9 | `valid_settings_max_exact_integer` | ACCEPT | 2^53-1 allowed | **ACCEPT (LOCAL Py3.13)** | **UNEXECUTED** |
| 10 | `rejected_missing_explicit_denial_field` | REJECT | Missing != explicit null | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 11 | `rejected_missing_explicit_data_field` | REJECT | Missing != explicit null | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 12 | `rejected_missing_explicit_denial_code` | REJECT | Missing != explicit null | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 13 | `rejected_typed_denial_with_data` | REJECT | Denial with data refused | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 14 | `rejected_unreviewed_denial_code` | REJECT | Unreviewed denial code refused | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 15 | `rejected_wrong_protocol_minor` | REJECT | Exact protocol 1.0 only | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 16 | `rejected_wrong_protocol_major` | REJECT | Exact protocol 1.0 only | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 17 | `rejected_stale_observation` | REJECT | Observation age/freshness fence | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 18 | `rejected_future_observation` | REJECT | No future observation | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 19 | `rejected_nine_digit_timestamp` | REJECT | 6-digit fractional second limit | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 20 | `rejected_wrong_generation` | REJECT | RUN generation correlation | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 21 | `rejected_c1_escaped_u0085` | REJECT | Unicode C1 control refusal | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 22 | `rejected_c0_escaped_newline` | REJECT | Unicode C0 control refusal | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 23 | `rejected_surrogate_u_d800` | REJECT | Invalid unpaired UTF-16 surrogate | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 24 | `rejected_surrogate_u_dfff` | REJECT | Invalid unpaired UTF-16 surrogate | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 25 | `rejected_nonascii_key` | REJECT | ASCII projection key | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 26 | `rejected_oversized_integer` | REJECT | Portable JSON bound | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 27 | `rejected_negative_oversized_integer` | REJECT | Negative portable JSON bound | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 28 | `rejected_oversized_float` | REJECT | Finite and bounded numeric | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |
| 29 | `rejected_duplicate_key` | REJECT | Strict duplicate-key parser | **REJECT (LOCAL Py3.13)** | **UNEXECUTED** |

## Acceptance and retry policy

`aegis.platform.management.read-response.v1` with `protocol:"1.0"`
is the ONLY candidate wire shape. All eleven outer fields are required, even
where data/denial is explicitly JSON null. Max 32 KiB. Correlation pins
request_id, target Platform, operation and the exact current RUN generation.
Dates must be uppercase RFC3339 `YYYY-MM-DDTHH:mm:ss[.1..6](Z|±HH:mm)`.
Observation is within the original request created_at/deadline, not in the
future, <= 5 seconds stale, with client receipt before deadline.

`OK` requires no denial and the exact typed operation data. `DENIED`
requires null data and one of NOT_PERMITTED, REVOKED, STOPPED,
STALE_GENERATION, EXPIRED, UNAVAILABLE. This JSON is **syntax only** and does
not authenticate sender, owner permission, client, installer or publisher.

An unknown/revoked/never-enrolled local caller gets EOF or native denial,
not a parseable claim of current live Platform state. On service loss,
restart, new generation, STOP, expired request or reconnect, discard prior
live UI state and use a new OS-authenticated session with new request_id
and fresh deadline/current generation; **never retry/replay an old
correlation or trust stale READY**. No protocol downgrade or unauthenticated
version negotiation. A future alternate protocol requires separate written
A/C contract approval and negative vectors.

## Completion evidence checklist

- Rust fmt, Clippy, test and release matrix complete at the exact checked-out
  PR head, not GitHub's synthetic PR-merge commit.
- Python 3.12/3.14 Linux/Windows matrix completed on the **same** pinned head.
- Capture each of 29 actual results as ACCEPT/REJECT, record unexpected
  acceptance/rejection with exact vector and CI log/JUnit line.
- Team C explicitly ACKs this immutable corpus and **same-SHA** management
  source and documents no client bypass, with a written signature/comment.
- Team E independently validates host, checkout SHA and read-only client
  provenance. No implied signed Windows/Debian installed-host acceptance.

## A-009 local execution evidence (independent of queued CI)

**Input/source provenance:** Team A #241 source head at execution:
`5bc8f9c2269ac2ac2b5b0e6c8c9bd1d769cba2a9`.
Immutable wire corpus Git blob `b63eeafe40b7895468f7ac8e0060c3bebfababa9`;
verified with `git hash-object` after staging. Python SDK verbatim source
`platform_management.py` blob `8e18a4f509498ae1dbb53fe251736b73448d8d5b`
and `platform_management_response.py` blob
`69b5a375dc14453572dcca5a7ff6885de3b069d7`.
The two request fixture blob hashes were also confirmed identical:
`adffc68fcfe2e54ab9e962dba601412a7eb31efd` and
`591e2a31ed23d2577fb822d53af24b28c821ac6a`.
The new Linux native client commits later in the PR do not change these blobs.

**Actual command:** `PYTHONPATH=/mnt/data/aegis_a009/src python /mnt/data/aegis_a009/run_29.py`.

**Environment:** Linux 6.18.57 x86_64, Python 3.13.5 (GCC 14.2.0).
The runner invokes the exact `UntrustedManagementRead.parse` and
`UntrustedManagementResponse.parse` source code on each immutable wire
and checks expected versus actual. Every row above contains the observed
Python verdict: **29/29 match**, of which 9 were actual ACCEPT and 20 actual
REJECT. Exit status 0. Local log SHA256
`0103a4ef3dee7ccf4dc852d04e48ce375cca4d797ac493fd49469cc1dcee671a`;
local CSV SHA256 `519244e706ee12eb8be37dfae1e14ed40ec20d36997efadcdb094b5fc35f655b`.

**Not executed:** Rust parser, `cargo fmt`, Clippy, Cargo tests,
Python 3.12/3.14 Windows/Linux matrix, signed installed-host and
full repository pytest. This container has no Rust toolchain and cannot
clone GitHub over the network. No one may translate a local Python match
into Rust parity, an authenticated service, or a release acceptance PASS.

**Verdict: 29/29 local Python wire outcomes matched; 0/29 local Rust
outcomes executed; joint A/C signoff HOLD pending real Rust execution
and native OS evidence.**
