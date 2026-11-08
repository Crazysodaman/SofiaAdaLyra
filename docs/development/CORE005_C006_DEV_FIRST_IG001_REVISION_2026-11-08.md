# CORE-005 | C-006 development-first integration revision (NO-GO)

## Authority and checkpoint preservation
- Previous draft PR #257 source checkpoint: `cf149b584f168f249cd11776c2e819879ca905e7` (unchanged ancestor and parent of this revision). Main untouched; no team PR merge.
- C-006 exact pinned inputs:
  * Team 1: `5990ba2feffda1846ed004ef049f75a87d1e3608`
  * Team 2: `d6e533bdb341d3352d31cc4a1170ef9951929baa`
  * Team 3: `7668916409708e48010c3c9f6f80ec4233d61c68`
  * Team 4: `0c20dee709addbdece5b9727fee214e9e24b336f`
- Integration mechanism: 31 exact Git blob objects from **fast-forward** old input SHA..C-006 source SHA ranges on the pinned integration base tree. No cross-team overlapping paths. No protected state or production enrollment.
- The source team PRs continued committing after the pin. Later heads are NOT silently incorporated.
- Source and workflow file SHA1 hashes are Git identities, not independent installed artifact SHA256, signing receipts or host acceptance.

## Functional reconciliation summary
- Team 1 now requires a fresh positive local generation, current lease, no STOP, process lock, and exact child startup token before claiming readiness. A local RUN lease is NOT cross-host writer exclusivity. PROCESS_READY, CORE_READY and INFERENCE_READY remain distinct.
- Team 2 real probe now requires exact checkout SHA and actual Ollama model digest, model-derived output attribution and persisted turn hashes. No auto model downloads. Ollama 45-second **per-I/O** timeout is not a global 30-second client deadline.
- Team 3 includes an **opt-in disposable-only** V1 eligibility policy, actual original re-review and restart continuity probe. It is not production-wired. Legacy PROMOTED-without-review must never be counted as accepted reviewed memory; test the V1 exclusions and backup restore downgrade.
- Team 4 now preserves uncertain Core Link idempotency key through client timeout and reconnect, with a scripted negative test. A scripted transport is not a two-host pinned mTLS real-inference demonstration. 30s client vs 45s I/O vs 120s worker must be reconciled with Teams 1/2/4 before acceptance.
- Zero overlapping changed paths. **Potential semantic conflicts:** Core Link status 'ready' differs from genuine inference readiness; local lock vs distributed lease; canonical memory policy opt-in not automatically consumed by genuine provider request; 30s transport uncertain reconciliation vs potentially longer worker turn.
- STOP/revocation after an already admitted operation: deny unauthorized response delivery AND negative-test durable model/tool effects or retained sensitive data. Atomic pre-admission gate alone is insufficient for full safety.

## Actual Team 5 disposable QA execution, restricted environment
- Host: ephemeral Linux x86_64, kernel 6.18.57, Python 3.13.5, pytest 9.0.2; **not** repository's required Python 3.12 Windows/Debian installed hosts.
- Executed: `cd /mnt/data/core005_local_probe && python -m pytest -q test_authority_contract.py test_ollama_response_extract.py --junitxml=/mnt/data/CORE005_C006_local_source_contracts.xml`
- Result: **31 PASS, 0 FAIL, 0 SKIP** in 0.09 seconds, exit 0. This is an extracted-source *logic probe with QA dependency doubles*, not a full checkout, real Core or inference. The actual Team 1 runtime authority file Git blob matches `54df07984b6d3d8fba0c965068c59105193cf018`. Extracted Ollama boundary is a manually copied method with simplified tool-call handling; it is not a full provider test.
- Local repo checkout blocker: `git ls-remote https://github.com/Crazysodaman/SofiaAdaLyra.git HEAD` returns `Could not resolve host: github.com` on this executor. No unrun full-checkout command is labeled successful.
- Integration candidate CI only at acceptance checkpoint per C-005. Pending/queued/cancelled CI is **never** a local test pass.

## First functional stage and next executable work
- IG-001 stage 0 FULL CHECKOUT/installed disposable test host: **BLOCKED ENVIRONMENT** on Team 5 executor. Therefore stage 1 authorized Core startup = **NOT EXECUTED**; there is no observed Core application failure and no live model response.
- Required integration smoke on an authorized disposable Windows/Debian host:
  ```bash
  git clone https://github.com/Crazysodaman/SofiaAdaLyra.git
  cd SofiaAdaLyra
  git checkout --detach <exact-integration-head>
  python3.12 -m venv .venv
  . .venv/bin/activate
  python -m pip install -e . pytest
  python -m pytest -q -m "not integration" test/test_run_release_process.py test/test_run_runtime_child.py test/test_run_runtime_authority.py test/test_run_host.py test/test_ollama_malformed_response_boundary.py test/test_core_team3_disposable_continuity.py test/test_core_team3_legacy_policy_v1.py test/test_core_team3_application_v1_hook.py test/test_core004_wire_security.py test/test_core004_admission_fence.py test/test_core004_client_deadline.py test/test_core_link_conversation.py
  ```
  The operator must explicitly approve an isolated already-running Ollama endpoint/model for the genuine test. Opt-in: `SOFIA_CORE002_LIVE=1 SOFIA_OLLAMA_MODEL=<installed_tag> SOFIA_CORE002_EXPECTED_SHA=<exact-integration-head> python -m pytest -q -s -m integration test/test_core002_live_ollama_conversation.py`. A skipped probe is not inference. A real provider turn is not automatically a restarted authenticated mTLS Core.
- Implement an actual installed-host IG-001 harness with signed artifact digests and receipts, then execute the complete startup → real inference → reviewed synthetic memory correction → real OS process restart → authenticated pinned Core Link reconnect. Require STOP, revoked peer, wrong identity, duplicate writer, stale READY, timeout/late result, erased-memory restored backup, and network disconnect negatives. First observed failing stage must produce an actual log, not a guess.
- Platform A/E and Team 1 own Debian #240 VM first-ready cause and verified first/second boot; previous successful comparison does not establish root cause.

## Acceptance accounting (no promotion)
Core QA 0/16 accepted; six blocked, ten untested. G8 primary 0/16; supplemental 0/118. No merge, no production Core, no protected-state migration, no release certification.
