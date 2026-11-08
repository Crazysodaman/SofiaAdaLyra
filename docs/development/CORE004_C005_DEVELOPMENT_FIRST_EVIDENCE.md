# CORE-004 C-005 | Development-first functional evidence and integration handoff

Date: 2026-11-08. Branch: `chatgpt/core-team4-corelink-20261108`, draft PR #254. No merge, release promotion, Core activation, protected-state migration or personal Discord mutation.

## Executed local evidence (NOT full-repository tests)

Environment: disposable Linux execution container, Python **3.13.5**, Git **2.47.3**. Repo was not mounted.

1. Attempted `git ls-remote https://github.com/Crazysodaman/SofiaAdaLyra.git HEAD` in the isolated shell. **FAILED: Could not resolve host github.com** (DNS/network environment). No checkout or production host access occurred. Repository source was read separately through GitHub connector.
2. Retrieved `src/sofia/sdk/cognition_json.py` from GitHub on draft PR HEAD `0c20dee709addbdece5b9727fee214e9e24b336f`. Its exact Git blob SHA is `f107e51f7bdd34195bca2cddc7bfedf52e8b134f`. Re-created the file in `/mnt/data/core004_local_probe/cognition_json.py`; `git hash-object` locally returned exactly the same blob SHA.
3. Ran Python 3.13.5 direct unit vectors against that EXACT component source:
   - Valid simple JSON ACCEPT
   - Valid nested JSON ACCEPT
   - Duplicate root key REJECT
   - Duplicate nested key REJECT
   - NaN REJECT
   - Infinity REJECT
   - -Infinity REJECT
   **Observed 7 PASS / 0 FAIL.** This proves only the strict parser, not the full HTTP transport, Core or real Ollama.
4. Windows installed-host, full Python package, PyTest runtime, Rust binary, real inference and cross-host mTLS tests **NOT EXECUTED** here. Never mark these as PASS.

## Functional defects corrected on isolated PR candidate (NOT yet executed as full-repo tests)

### CORE4-UX-008: stale transcript after message 100

`CoreLinkDesktopClient.refresh_history` requested only `after=None, limit=100`, never consumed the server's `next_cursor`, and therefore displayed *oldest* 100 messages forever. New implementation walks stable authenticated forward pages with exact session, unique message IDs, monotonically ordered (timestamp, id) and cursor checks, and publishes only the newest 100 after complete validation. It rejects duplicate/replayed pages and malformed cursor without publishing partial history. Test `test/test_core004_history_paging.py` stages 105 messages and verifies the newest 100 and the exact second-page cursor, plus two negative cases.

**Bounded v1 limitation:** the current server only offers forward-from-oldest history; desktop walks a maximum 32 pages/3,200 messages, then explicitly fails instead of silently returning stale data. Platform C and SDK owners should add a versioned seek-latest/reverse-page operation for truly long-lived conversations. Do not claim unlimited history capability.

### CORE4-INF-009: fake inference acceptance from opt-in test

`test/test_core004_real_inference_opt_in.py` previously reran a baseline Core Link test with an Ollama configuration but had no independent proof that Ollama was called, potentially accepting a deterministic output. It now injects a thin observation wrapper around the actual loopback `ollama.Client.chat()`, requires at least one completed model call, enforces the selected exact model and nonblank generated text, and does not record prompts/response contents. The opt-in test changes only its private 20-second baseline client timeout to 120 seconds for real cold-start and preserved the normal CI baseline timeout. The model's 45-second per-I/O timer is **not** a complete wall-clock deadline.

**Not executed**: no installed Ollama/model or full repository available in this container. This is only a stronger opt-in acceptance candidate. Team 2 should independently witness original model requests, model digest and two genuine turns.

## Reproducible commands for a disposable full source worktree

Run from a trusted clone of the EXACT PR #254 HEAD, with its own `SOFIA_STATE_ROOT` outside any protected Core directory:

```bash
python -m pip install -e . pytest
python -m compileall -q src/sofia test
python -m pytest -q \
  test/test_core004_wire_security.py \
  test/test_core004_admission_fence.py \
  test/test_core004_client_deadline.py \
  test/test_core004_history_paging.py \
  test/test_core_link_conversation.py \
  test/test_core_link_binding.py \
  test/test_core_link_desktop.py \
  test/test_platform_roles_and_launcher.py
```

For explicitly isolated local inference ONLY (never personal/production Core or Discord), set `SOFIA_CORE004_REAL_INFERENCE=1`, `SOFIA_CORE004_OLLAMA_MODEL` to an actually installed disposable model, and `SOFIA_CORE004_OLLAMA_ENDPOINT=http://127.0.0.1:11434`; then run `python -m pytest -q -s test/test_core004_real_inference_opt_in.py`. The test is skipped by default.

## Integration/QA routing

- Team 1: generation and single writer; Core/worker restart source of authority and effect fencing.
- Team 2: genuine provider call, model provenance and absolute deadline contract; quality-repair retries are not complete 45-second wall-clock guarantees.
- Team 3: authenticated session/history scope and persistence after restart; tests must not cross audiences.
- Platform C: versioned seek-latest/tail history contract and OFFLINE/RECONNECTING/DEGRADED/READY semantics.
- Team 5: run the exact integrated IG-001 candidate on one isolated Core integration branch; perform independent two-host Windows-to-Debian pinned mTLS, genuine Ollama, restart/reconnect, STOP/revocation and wrong-identity negatives.
- **GitHub CI deferred under coordinator C-005:** do not repeatedly change commits just to requeue the G4/R2/cross-gate jobs. Full exact-SHA CI returns at integrated milestone acceptance, before release or merge certification.

**Current status:** source candidate + 7 local parser vectors; full functional Core, installed two-host inference and G8 acceptance **unverified**. CORE SHAKEDOWN = NO-GO; PRODUCTION GO = NO.
