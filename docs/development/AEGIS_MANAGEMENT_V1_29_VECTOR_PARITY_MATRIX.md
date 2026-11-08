# Management response v1 | A/C exact-wire 29-vector parity matrix

**Status: REVIEW CANDIDATE, NOT ACCEPTED.** This is a published cross-language
**expected-verdict matrix**, not test output. There is no current-head completed
Rust/Python CI or approved A/C joint freeze at the time this document was added.

Canonical **unchanged** fixture: `contracts/platform/management-response-parity-corpus-v1.json`
(Git blob `b63eeafe40b7895468f7ac8e0060c3bebfababa9`). Test drivers:
`test/test_ui_platform_management_response.py::test_shared_29_case_rust_python_management_wire_corpus`
and `rust/crates/sofia-contracts/src/management.rs::tests::shared_29_case_rust_python_management_wire_corpus`.
Each reads the *same literal wire strings*. Status values below must not be
changed to PASS without a verified exact-head Rust and Python test/JUnit
observation and independent Team E provenance review.

| # | Vector | Expected | Meaning | Python current-head | Rust current-head |
|---:|---|---|---|---|---|
| 1 | `valid_status_explicit_null_denial` | ACCEPT | Explicit null denial on success | **UNEXECUTED** | **UNEXECUTED** |
| 2 | `valid_typed_stop_explicit_null_data` | ACCEPT | Typed denial with null data | **UNEXECUTED** | **UNEXECUTED** |
| 3 | `valid_typed_not_permitted` | ACCEPT | Typed denial with null data | **UNEXECUTED** | **UNEXECUTED** |
| 4 | `valid_typed_revoked` | ACCEPT | Typed denial with null data | **UNEXECUTED** | **UNEXECUTED** |
| 5 | `valid_typed_stale_generation` | ACCEPT | Typed denial with null data | **UNEXECUTED** | **UNEXECUTED** |
| 6 | `valid_typed_expired` | ACCEPT | Typed denial with null data | **UNEXECUTED** | **UNEXECUTED** |
| 7 | `valid_typed_unavailable` | ACCEPT | Typed denial with null data | **UNEXECUTED** | **UNEXECUTED** |
| 8 | `valid_settings_unicode_line_separator` | ACCEPT | U+2028 allowed | **UNEXECUTED** | **UNEXECUTED** |
| 9 | `valid_settings_max_exact_integer` | ACCEPT | 2^53-1 allowed | **UNEXECUTED** | **UNEXECUTED** |
| 10 | `rejected_missing_explicit_denial_field` | REJECT | Missing != explicit null | **UNEXECUTED** | **UNEXECUTED** |
| 11 | `rejected_missing_explicit_data_field` | REJECT | Missing != explicit null | **UNEXECUTED** | **UNEXECUTED** |
| 12 | `rejected_missing_explicit_denial_code` | REJECT | Missing != explicit null | **UNEXECUTED** | **UNEXECUTED** |
| 13 | `rejected_typed_denial_with_data` | REJECT | Denial with data refused | **UNEXECUTED** | **UNEXECUTED** |
| 14 | `rejected_unreviewed_denial_code` | REJECT | Unreviewed denial code refused | **UNEXECUTED** | **UNEXECUTED** |
| 15 | `rejected_wrong_protocol_minor` | REJECT | Exact protocol 1.0 only | **UNEXECUTED** | **UNEXECUTED** |
| 16 | `rejected_wrong_protocol_major` | REJECT | Exact protocol 1.0 only | **UNEXECUTED** | **UNEXECUTED** |
| 17 | `rejected_stale_observation` | REJECT | Observation age/freshness fence | **UNEXECUTED** | **UNEXECUTED** |
| 18 | `rejected_future_observation` | REJECT | No future observation | **UNEXECUTED** | **UNEXECUTED** |
| 19 | `rejected_nine_digit_timestamp` | REJECT | 6-digit fractional second limit | **UNEXECUTED** | **UNEXECUTED** |
| 20 | `rejected_wrong_generation` | REJECT | RUN generation correlation | **UNEXECUTED** | **UNEXECUTED** |
| 21 | `rejected_c1_escaped_u0085` | REJECT | Unicode C1 control refusal | **UNEXECUTED** | **UNEXECUTED** |
| 22 | `rejected_c0_escaped_newline` | REJECT | Unicode C0 control refusal | **UNEXECUTED** | **UNEXECUTED** |
| 23 | `rejected_surrogate_u_d800` | REJECT | Invalid unpaired UTF-16 surrogate | **UNEXECUTED** | **UNEXECUTED** |
| 24 | `rejected_surrogate_u_dfff` | REJECT | Invalid unpaired UTF-16 surrogate | **UNEXECUTED** | **UNEXECUTED** |
| 25 | `rejected_nonascii_key` | REJECT | ASCII projection key | **UNEXECUTED** | **UNEXECUTED** |
| 26 | `rejected_oversized_integer` | REJECT | Portable JSON bound | **UNEXECUTED** | **UNEXECUTED** |
| 27 | `rejected_negative_oversized_integer` | REJECT | Negative portable JSON bound | **UNEXECUTED** | **UNEXECUTED** |
| 28 | `rejected_oversized_float` | REJECT | Finite and bounded numeric | **UNEXECUTED** | **UNEXECUTED** |
| 29 | `rejected_duplicate_key` | REJECT | Strict duplicate-key parser | **UNEXECUTED** | **UNEXECUTED** |

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

**Verdict now: 29 expected cases defined; 0/29 witnessed on exact-head CI;
A/C SIGNOFF HOLD.**
