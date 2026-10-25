# Sofía 2.0 optional modules, Batch 7: Household, Analytics, Knowledge, Documents

Date: 2026-10-25. Owner approved four module implementations per batch, `main` only.
All four are **ALPHA**, each at version `0.1.0`. They are independently scoped
module-owned source files, not installed module packages. This is development
and focused unit-test evidence, not full SDK/Platform release certification.

## Capability inventory and effect bounds

| Module | Capability ID | Profile | Function | Resource proposal (CPU m / RAM MiB / GPU MiB) |
|---|---|---|---|---|
| `MOD-HOUSEHOLD` | `household.review_inventory.v1` | ADVISORY | Bounded stock, minimum quantity and dates using opaque IDs | 50 / 32 / 0 |
| `MOD-DATA-ANALYTICS` | `data_analytics.summarize_numeric.v1` | ADVISORY | Aggregates bounded numeric rows; never echoes raw rows | 100 / 64 / 0 |
| `MOD-KNOWLEDGE-LIBRARY` | `knowledge_library.plan_revision_index.v1` | ADVISORY | Diff untrusted document metadata to propose index revisions and tombstones | 75 / 48 / 0 |
| `MOD-DOCUMENTS` | `documents.render_safe_markdown.v1` | SIMULATE | Escaped Markdown generation from plain text, SHA-256 of returned UTF-8 | 75 / 48 / 0 |

All inputs demand exact fields, bounded lengths/cardinality, timezone-aware
snapshot timestamps and explicit `source_ref`. Input source identifiers are not
authentication. No module may assert trusted provenance merely because its
caller supplies a string. In-memory output marks `effect: none`. None opens
files, accesses credentials, sends messages, writes to databases, executes
code, edits records or modifies Core memory.

### Household
Input: `source_ref`, `observed_at`, `items` with `item_id`, `quantity`,
`minimum_quantity`, `expires_on`. Maximum 128 items; no item names, addresses,
account IDs or pricing needed. Output only opaque IDs and counts. Requires a
separate consented inventory source adapter (e.g. Grocy) and Platform scope.
It is **not** a shopping/order or household database client.

### Data Analytics
Input: numeric rows plus 1..8 column identifiers, max 512 rows, missing values
as JSON null. Finite numeric bounds; boolean, NaN and Infinity are rejected.
Aggregate means, medians, ranges and sample standard deviation; no individual
rows are returned or persisted. Very small groups may still disclose sensitive
statistics; authorization, minimum aggregation thresholds, purpose limitation
and private-data handling must be enforced at the Platform boundary before
personal datasets are admitted. This is not a CSV parser or plotting engine.

### Knowledge Library
Input: up to 128 external document IDs and immutable SHA-256 revision digests
with optional indexed digest, plus deletion markers and observed timestamps.
Output: **candidate** index updates or tombstones, unchanged and skipped counts.
No document text is ingested here; real retrieval/indexing, access controls,
source admission, rollback, tombstone execution and durable index state remain
unimplemented. The Core has sole authority over its autobiographical memory;
index suggestions never become conversation memories automatically.

### Documents
Input: bounded plain-text title, section headings and paragraphs. The output
is an in-memory Markdown string with escaped Markdown/HTML punctuation and
SHA-256 digest; it is not a saved document, signed artifact or PDF/Office export.
No pass-through Markdown, embedded HTML, URLs or active formatting execution.
Bounded to 32 sections, 16 paragraphs each and 128 KiB rendered output.

## Owner and Platform responsibilities remaining

- Platform must authenticate the source principal and purpose-scoped consent;
  ACLs, private data retention and privacy class do not come from module fields.
- Real SDK 1.0 broker registration, reviewed execution factory, process
  sandbox, signed immutable package manifest, maintenance profile artifact
  digest and dependency compatibility are not yet verified.
- Profiles: `ADVISORY`, `ADVISORY`, `ADVISORY`, `SIMULATE`. All provisional
  permission ceiling level 1; **no executable authority**.
- Suggested health: schema/admission failure counters, bounded latency,
  freshness rejection counts, periodic self-check; owner-reviewed thresholds
  before admission. Quarantine on repeated invalid source projections and
  do not loop retrying a bad source.
- Suggested maintenance: manual updates only after signature verification,
  reversible version pin and explicit rollback test; disable module without
  affecting Core. Resource envelopes above are estimates, not measured upper
  bounds. Do not issue an immutable maintenance profile with a placeholder
  artifact digest.
- Interoperability: Household source adapter, Analytics data admission,
  Knowledge document index worker, Documents artifact/export worker all require
  independent gateway interfaces, security review, telemetry and failure tests.
- Missing-host, unauthorized principal, invalid manifest, module crash,
  revoked approval and effect timeout cases require real Platform fault tests.

## Local evidence and limitations

Run `PYTHONPATH=src python -m pytest -q test/test_module_batch7.py` in an
isolated workspace with **SDK/Platform test stand-ins** matching the inspected
published contract names. Observed: **74 passed**.
`python -m compileall -q src/sofia/modules` succeeded for this batch.
Static module import review found no socket, subprocess, SQLite, requests,
filesystem execution or host-management imports. This is not a dynamic sandbox
or security audit and not the full repository CI. Cross-version capability
construction must be retested against full real SDK before release.

Readiness: **ALPHA** for all four. No Gate 4/RC/Production Ready claims.
The protected Core, Platform, canonical database, SDK and ownership catalog
remain unmodified in this batch. Future task crosswalk must be reconciled with
the authoritative roadmap before upgrading readiness.
