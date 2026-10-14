# V18 Gate 4 evidence-integrity and artifact-objective batch

Date: 2026-10-14. Direct main development only; no live-host changes.

## Baseline and scope

- **CA-2304 / CA-3006 CI dependency:** At SHA `955afc23becfe4819e0471967e06651a69932800`,
  [Actions run 38650361600](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38650361600)
  failed on Ubuntu and Windows with 219 passed, 1 failed each. A frozen
  50-task source snapshot was compared byte-for-byte against an additive
  authoritative ledger. Three new source paths for a Phase 00 task caused
  a false mismatch. The original eleven remained intact.
- **CA-2201:** The independent typed `min_words` validator used
  `visible.split()`, allocating a full list of up to millions of words
  from a verified file as large as 64 MiB.

## Implementation and verified boundaries

- Regression test now requires each historical source path to remain
  present and in relative order in the canonical ledger. New audit paths
  are allowed. It still requires source files to exist and the original
  task text, phase, status, test paths and explicit no-acceptance flag.
- Production word counting now uses `re.finditer(r"\\S+", visible)`
  with `islice` to cap tokens read by the typed minimum. Unicode
  whitespace semantics match `str.split()`. Strict UTF-8, bounded
  objectives, verified hashes/descriptors and UNKNOWN for unsupported
  claims remain unchanged.
- New objective regressions cover Unicode whitespace and 96,000/96,001
  thresholds plus early completion against a long artifact.

## Security / authority / recovery / performance audit

No new capability, SAFE grant, model-written validation, owner approval,
SQLite owner, external execution, host change or persistence is introduced.
Malformed goals continue to abstain, and artifact hashes remain mandatory.
All changes are revertible without a schema migration. The word-count
iterator is memory-bounded by one regex match and exits at the minimum.
The read-only ledger remains the source of truth; this batch does not
claim an original task accepted or that an old CI run proves new code.

## Pending acceptance

Execute focused `test/test_v18_gate4_batch50.py` and
`test/test_life_objective_parser_bounded.py`, then inspect the Ubuntu and
Windows Gate 4 Fifty matrix for the exact new SHA. Broader release, SAFE,
Windows/Artemis host tests and Gate 4 task-specific acceptance remain open.
CA-2201, CA-2304 and CA-3006 are not credited as completed.
