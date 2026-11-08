# CORE-005 | C-010 pinned integrated development revision

Status: **IG-001 NOT EXECUTED, NO-GO**. Coordinator requested direct descendant of previous source checkpoint, **no merge into main** and no production changes.

## Exact freeze
- Parent integrated checkpoint: `652053e62cf715433d1d5fc3d4bf2cb5e4b9a17a`, tree `086b0e90217273c6564c5acb6ee39bb5cde293f8`. This preserves all Team 2 genuine-model and V1 tests staged at the prior SHA.
- Team 1 PR #256 SHA `20bf12a3613f1ad5a4d9b9cc8541651827805f8a`, direct fast-forward from prior input `5990ba2feffda1846ed004ef049f75a87d1e3608`. Delta 10 file paths.
- Team 3 PR #252 SHA `dd1950200d8ddb26c661489ec442b8c1a7f436ca`, direct fast-forward from prior input `7668916409708e48010c3c9f6f80ec4233d61c68`. Delta 4 paths.
- Team 4 PR #254 SHA `36c96442097a1ce45407f4f264ed8d03f894bbc6`, direct fast-forward from prior input `0c20dee709addbdece5b9727fee214e9e24b336f`. Delta 7 paths.
- Integrated revision reuses 21 exact Git blobs; no source paths overlap between the three deltas or with Team 2's previous four-file change. The source PR heads may advance after this freeze; no auto-sync.
- Git source blob SHA1 and commit SHA1 are **not** independently verified release binary SHA256, trust roots or installed-host execution receipts.

## Semantic review and unresolved contracts
- Team 1's `core_worker/process.py` moves synchronous provider calls into bounded daemon threads via `call_with_deadline`, with monotonic deadline rejection. This fences the returned IPC result, **does not cancel the underlying provider thread**. Worker controller must quarantine/fence generation and prove no durable side effect or stale reply leaks after timeout. Actual process-crash SQLite tests are synthetic child writers, not full Sofía Core process restart.
- Team 1's generation-bound heartbeat retains one pinned epoch and refuses fresh READY from a stale worker. It does not prove a distributed writer lock, installed service manager state or genuine model health.
- Team 3's test-only disposable V1 fixture creates an existing canonical identity path, requires `REQUIRE_EXISTING`, and adds whole-application memory correction/restart tests. It is not auto-wired into production. Cross-team compatibility with Team 2's opt-in V1 fixture needs **actual full-checkout execution**.
- Team 4 adds real loopback pinned-mTLS socket reconnect and lost-reply key reconciliation with **fake generated response**, as well as a separate opt-in Ollama-backed Core Link path. The first is a real transport security test, **not genuine inference**. The latter requires an already installed model and explicit authorization and does not by itself demonstrate full Core worker process restart.
- Potential deadline mismatch remains: 30s client deadline, 45s Ollama I/O, 120s worker budget; TEAM 4's opt-in loopback client uses 120s test transport but does not amend the underlying 30s Core Link envelope without separate execution/contract evidence.
- Cross-package semantic conflicts cannot be cleared by disjoint file paths or pure source review; the first full-checkout failure determines engineering owner.

## Commands for disposable Python 3.12 checkout
1. `python -m pip install -e . pytest` on a freshly pinned checkout.
2. `python -m pip check`; verify original pin `git rev-parse HEAD`.
3. `python -m pytest -q -m 'not integration' test/test_core_worker_provider_deadline.py test/test_core001_disposable_writer_restart.py test/test_core_worker_process.py test/test_run_host.py test/test_core_team3_application_v1_hook.py test/test_core_team3_legacy_policy_v1.py test/test_core004_real_mtls_reconnect.py test/test_core004_admission_fence.py test/test_core004_client_deadline.py test/test_core_link_conversation.py test/test_core004_wire_security.py test/test_ollama_malformed_response_boundary.py`
4. After passing and authorization of an **already-running** disposable Ollama endpoint: `SOFIA_CORE002_LIVE=1 SOFIA_CORE002_MEMORY_V1=1 SOFIA_CORE002_EXPECTED_SHA=<exact_commit> SOFIA_OLLAMA_MODEL=<installed_tag> SOFIA_OLLAMA_URL=<approved_url> python -m pytest -q -s -m integration test/test_core002_live_ollama_conversation.py` (on Windows set environment variables in PowerShell instead of POSIX assignment).
5. Team 4 real Core Link inference test requires loopback endpoint, `SOFIA_CORE004_REAL_INFERENCE=1 SOFIA_CORE004_OLLAMA_MODEL=<installed_tag>`, and must be reported separately. This does not prove OS-level worker restart, signed installation, single canonical writer or full remote reconnect.

## Required receipts and prohibitions
- Record exact SHA, Windows/Debian host identity/build, Python version, explicit model+digest, actual command, begin/end UTC, logs/JUnit, artifact SHA256, test PASS/FAIL/SKIP separately, stage and first failed assertion.
- Never run against protected Venus/Artemis state or personal data. No production Core or Discord, no unapproved model downloads, host cutover, second canonical writer, main merge, release cert or G8 acceptance promotion.
- Full exact-SHA GitHub CI is the milestone gate under C-005; pending CI cannot certify. Core 16 scenario acceptance and G8 (16 primary, 118 supplemental) stay separate.
