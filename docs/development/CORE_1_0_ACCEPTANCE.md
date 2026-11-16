# Sofía Core 1.0 acceptance evidence

**Status: NOT ACCEPTED / NO-GO.** This document describes how Core 1.0
evidence is collected. It is not evidence itself, it does not modify any
authoritative acceptance text, and it does not claim G8 (#129).

Authoritative requirements remain:

- [`docs/sofia2/CORE_1_0_PLAN.md`](../sofia2/CORE_1_0_PLAN.md) — CORE-01..CORE-40 and B00..B08.
- [`docs/development/AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md`](AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md) — POC-C1..POC-C5 overlay.
- [`docs/development/AEGIS_OWNER_ONLY_GO_LIVE_ACCEPTANCE_2026-11-09.md`](AEGIS_OWNER_ONLY_GO_LIVE_ACCEPTANCE_2026-11-09.md) — owner-only GO-LIVE overlay.
- [`docs/development/V18_TASK_STATUS_STANDARD.md`](V18_TASK_STATUS_STANDARD.md) — L1..L5 evidence levels.

## Tool

`tools/aegis_core_acceptance.py` aggregates:

1. an exact-SHA JUnit file from the declared source probes, and
2. an optional explicit receipt bundle.

It emits `aegis.core.acceptance-report.v1` as JSON. It never edits the
authoritative documents, never authorizes production, and never infers
installed/owner-host acceptance from source tests.

## Evidence kinds

| Kind | Meaning |
| --- | --- |
| `source_tests` | Declared repository tests actually ran and passed for the exact SHA. |
| `disposable_process` | An observed disposable process/VM run with negative cases. |
| `installed_artifact` | A signed/verified installed artifact observed on a registered installed host. |
| `remote_conversation` | A real remote client/Core Link conversation with negative cases. |
| `owner_host` | A real owner-controlled host observation with `real_host: true`. |

Each inventory item declares exactly which kinds it needs. `PASS` is emitted
only when **every** declared kind is present and internally valid.

## States

| State | Rule |
| --- | --- |
| `PASS` | Every required kind is present and valid. Source-only PASS is limited to source tests and is never host certification. |
| `FAIL` | A mapped source test failed, or a receipt is mismatched, stale, future-dated, tampered, unregistered or missing a required negative case. |
| `BLOCKED` | Some evidence exists but a required kind/entry is absent or incomplete. |
| `NOT_TESTED` | No usable evidence exists for the item, or the item is the deferred post-Core CORE-34. |

A skipped test is never `PASS`. A missing negative case is never `PASS`.
Receipts older than `--max-age-days` (default 365) are rejected as stale.

## Signed receipt envelope

Receipts are a single JSON object stored beside an `artifacts/` directory.
`artifact_path` is relative to that directory; the collector hashes the actual
bytes and rejects a mismatch. The object must include a real Ed25519
`signature` over the canonical JSON bytes of the same object with `signature`
removed. A self-declared `signers` list is not part of the schema and can never
establish trust.

```json
{
  "schema": "aegis.core.acceptance-receipts.v1",
  "source_sha": "<exact 40-hex SHA>",
  "hosts": {
    "DISPOSABLE-01": {"host_class": "DISPOSABLE"},
    "INSTALLED-01": {"host_class": "INSTALLED"},
    "REMOTE-01": {"host_class": "REMOTE"},
    "OWNER-01": {"host_class": "OWNER"}
  },
  "items": {
    "CORE-01": {
      "source_sha": "<exact 40-hex SHA>",
      "evidence": {
        "disposable_process": {
          "host_id": "DISPOSABLE-01",
          "host_class": "DISPOSABLE",
          "signer_key_id": "<trusted signer key id>",
          "artifact_path": "artifacts/CORE-01-disposable.bin",
          "artifact_sha256": "<64-hex digest of the actual bytes>",
          "application_sha256": "<64-hex application digest>",
          "observed": true,
          "result": "PASS",
          "witnessed_at": "2026-11-15T00:00:00+00:00",
          "negative_cases": ["unauthorized-attempt-denied"]
        }
      }
    }
  },
  "signature": {
    "algorithm": "Ed25519",
    "signer_key_id": "<trusted signer key id>",
    "signature_b64": "<base64 Ed25519 signature>"
  }
}
```

Canonical signed bytes are exactly:

```text
json.dumps(payload, sort_keys=True, separators=(",", ":"),
           ensure_ascii=False, allow_nan=False).encode("utf-8")
```

where `payload` is the receipt object with its `signature` key removed. The
collector verifies the signature with `cryptography` against the caller's
`--trusted-public-key` PEM file, its `--trusted-key-sha256` fingerprint, and
`--signer-key-id`. All three arguments are required whenever `--receipts` or
`--g8-receipt` is supplied. An unsigned, forged, wrong-key or unknown-signer
receipt leaves every receipt-backed item `BLOCKED` and forces
`core_release_verdict` to `NO_GO`.

Exact signing command (development helper; it grants no acceptance authority):

```text
python -m tools.aegis_sign_acceptance_receipt \
  --receipt core-receipts.json \
  --private-key owner-key.pem \
  --signer-key-id owner-key-1 \
  --output core-receipts.signed.json
```

The matching public key fingerprint is the SHA-256 of the exact PEM bytes:

```text
python -c "from hashlib import sha256; print(sha256(open('owner-key.pub.pem','rb').read()).hexdigest())"
```

Validation rejects:

- a missing, malformed, forged, wrong-key or unexpected-signer signature,
- duplicate JSON keys and any unknown top-level/item/host/entry field,
- a top-level or per-item SHA that differs from the exact source SHA,
- an unregistered host or an entry signer that differs from the trusted signer ID,
- a host class that does not match the required kind,
- a missing or unreadable artifact, or a digest mismatch,
- `observed != true`, `result != "PASS"`, or missing negative cases,
- a missing/naive/future/stale `witnessed_at`,
- `owner_host` without `real_host: true`,
- an `owner_host` entry whose host is not registered as `OWNER`.

## G8 is separate

G8 is never an inventory item, is never embedded in the regular receipt bundle,
and is never inferred from disposable evidence. The report always contains
`g8.status` and `g8.certified`, defaulting to `NOT_CERTIFIED`. Certification
requires a distinct signed `aegis.core.g8-real-host-receipt.v1` file supplied
with `--g8-receipt` and containing:

- `real_host: true` and `host_class: "OWNER"`,
- a registered owner host and a distinct registered `REMOTE` client,
- a trusted signature, verified artifact bytes, fresh `witnessed_at` and negative cases,
- `owner_approved: true`.

Disposable fixtures in this repository's tests never certify G8.

## Verdict

`core_release_verdict` is `NO_GO` unless every non-G8 in-scope item is `PASS`.
It becomes `GO` only when all in-scope items are `PASS`; that still does not
certify G8. Receipt-backed items cannot be `PASS` without a valid signature from
the caller-trusted key. `release_accepted` stays `false` unless the distinct G8
receipt is also independently valid. `production_authorized` is always `false`.

No PASS or GO is claimed for the current release by this document.

## Inventory

The inventory contains **55 items**: CORE-01..CORE-40 (CORE-34 is explicitly
deferred and excluded from the GO scope), B00..B08, G7-A, and POC-C1..POC-C5.

Legend: `S` source tests, `D` disposable process, `I` installed artifact,
`R` remote conversation, `O` owner host.

| Item | Evidence | Item | Evidence |
| --- | --- | --- | --- |
| CORE-01 | S D I R O | CORE-21 | S D |
| CORE-02 | S D | CORE-22 | S D |
| CORE-03 | S D | CORE-23 | S D |
| CORE-04 | S D | CORE-24 | S D |
| CORE-05 | S D | CORE-25 | S D |
| CORE-06 | S D | CORE-26 | S D |
| CORE-07 | S D I | CORE-27 | S D |
| CORE-08 | S D | CORE-28 | S D |
| CORE-09 | S D | CORE-29 | S D |
| CORE-10 | S D | CORE-30 | S D |
| CORE-11 | S D I | CORE-31 | S D |
| CORE-12 | S D | CORE-32 | S D |
| CORE-13 | S D | CORE-33 | S D |
| CORE-14 | S D | CORE-34 | S (deferred, out of GO scope) |
| CORE-15 | S D I R | CORE-35 | S D I |
| CORE-16 | S D I | CORE-36 | S D |
| CORE-17 | S D | CORE-37 | S D I |
| CORE-18 | S D | CORE-38 | S D |
| CORE-19 | S D | CORE-39 | S D |
| CORE-20 | S D | CORE-40 | S D |
| B00 | S D | B05 | S D |
| B01 | S D | B06 | S D |
| B02 | S D | B07 | S D |
| B03 | S D | B08 | S D I R O |
| B04 | S D I | G7-A | S D |
| POC-C1 | S D I R O | POC-C4 | S D I |
| POC-C2 | S D I R | POC-C5 | S D I |
| POC-C3 | S D I | | |

The executable source and exact per-item test mapping live in
`tools/aegis_core_acceptance.py`; the machine-readable report is authoritative
for a given run.

## Source-only CI

`.github/workflows/aegis-core-acceptance.yml` runs the declared source probes
at the exact PR head SHA, then emits `core-acceptance-report.json` labelled
`SOURCE_ONLY`. That job cannot produce `GO` because every in-scope item
requires at least one receipt kind it does not supply. Source-only results are
not installed-host, remote-conversation or owner-host proof.

## Example invocation

```text
python -m tools.aegis_core_acceptance \
  --junit core-acceptance-junit.xml \
  --source-sha <exact-40-hex-sha> \
  --receipts <evidence-dir>/core-receipts.json \
  --g8-receipt <evidence-dir>/g8-receipt.json \
  --trusted-public-key owner-key.pub.pem \
  --trusted-key-sha256 <64-hex SHA-256 of owner-key.pub.pem> \
  --signer-key-id owner-key-1 \
  --output core-acceptance-report.json
```

`--g8-receipt` is optional; omitting it leaves G8 `NOT_CERTIFIED` and keeps
`release_accepted` false. The three trust arguments are mandatory for any
receipt input.

List the declared source probes:

```text
python -m tools.aegis_core_acceptance --list-source-tests
```

## Remaining certification blockers

- No real signed installed-artifact receipt exists for the current Core release.
- No remote Venus↔Artemis Core Link conversation receipt exists.
- No owner-host receipt exists for the current release.
- CORE-34 remains post-Core and out of the Core 1.0 release scope.
- G8 (#129) remains **NOT CERTIFIED** and is never satisfied by source,
  disposable, or documentation evidence.

## Parallel campaign checkpoint 2026-11-15

Core workers in this campaign committed C1 `3955739`, C2 `8e35cab`,
C3 `76fe17a`, C4 `81e49e4`, C5 `725a8a3` and C6 `681ec2d`, integrated through
`aegis/platform-core-integration` into main `2a04d7fc`.

Verified on the merged source: a real subprocess synthetic Core backend
(start/observe/stop/crash/restart with one-writer fencing), bounded provider
failover and multi-turn context, canonical memory/audience/backup hardening,
remote conversation idempotency and Rust/Python Core Link fixtures, and
protected Core state/principal boundaries. Cross-domain focused run: 237
passed, 8 skipped; Rust workspace tests and strict Clippy passed.

These are disposable/source results. No signed installed Core, real
Artemis/Venus conversation, owner-host receipt or G8 certification exists.
This checkpoint changes no CORE per-row state and does not raise the
source-only verdict (PASS 0, BLOCKED 54, NOT TESTED 1, G8 NOT CERTIFIED).
