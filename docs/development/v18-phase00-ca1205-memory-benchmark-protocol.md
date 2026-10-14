# CA-1205 | Adapted internal temporal/agent memory benchmark protocol

**Status: designed candidate, not independently reviewed or executed.**
Date: 2026-10-14. Original task CA-1205 remains unassessed in canonical
ledger pending owner or independent reviewer, fixture licensing and tests.

## Evaluation arms and source truth

Plan three task families inspired by LongMemEval, LoCoMo and agent-environment
memory. Do not redistribute upstream copyrighted passages or describe
fabricated synthetic records as upstream benchmarks. Begin with
**12 original, self-authored holdout tasks per family** (36 total) and
record the exact committed fixture hash, license and adjudicator version.
Any actual licensed upstream subset is a separate pinned dataset. Store
original source events, correction/revocation chain, timestamps and
audience in fixture-only SQLite with seeded isolated owner principals.
No real private user history, credentials or screenshots.

- **LongMemEval-style (12):** temporal correction, entity identity,
  original-before-after ordering, precise timestamp, stale fact,
  deletion/revocation, unknown answer, conflicting witness, source
  citation, cross-month recall, missing tool evidence and multi-hop.
- **LoCoMo-style (12):** 3-20 session turns with topic changes, indirect
  preference, user corrections, long-gap continuity, narrative constraints,
  user-versus-assistant claims, two-device origin labels, counterevidence,
  quiet hours, relationship timing, ambiguous referents and old project.
- **Agent-environment (12):** approved observed state, inferred vs
  verified distinction, stale telemetry, offline Fleet, reversible job
  receipt, uncertain remote outcome, model outage, private permission,
  active gaming, restart state, repeated request nonce and simulator
  state versus actual hardware.

## Controls, ablations and scoring

Run on one exact revision and one isolated resource budget with a
**no-retrieval** baseline and reviewed-retrieval treatment. Repeat
without episodic history, without long-term source selection, without
corrections and without candidate procedural recall as feature ablations.
Use at least three deterministic seeds where applicable. Freeze same
model route, context/output ceilings and prompts between arms.

A grader independent of model self-assessment records exact cited
source ID, audience, original and correction timestamps, whether
retrieval was authorized, expected answer or required abstention,
actual answer, valid/invalid source support, task-side action receipt
and measured latency/cost. Score answer accuracy, warranted
abstention, temporal precedence, source validity, unauthorized
disclosure rate, evidence hallucination rate, false action-completion
rate and *downstream task outcome improvement*. Include confidence
intervals and per-category errors; do not use model praise as a
validation oracle.

## Stop, privacy and acceptance

Fail/stop on one unauthorized cross-audience retrieval, resurrected
revoked record, unapproved tool action, fabricated success receipt or
protected data disclosure. No promotion from a simulator-only win
without matching isolated production retrieval and authorized
multi-session host journeys. Report sampled/failed/skipped cases,
versioned dataset checksums, CPU/RAM/VRAM/time and exact artifacts.
Until the fixtures, graders and real integration runs exist,
**benchmark executed: no; score: unknown; Gate 4: not earned.**
