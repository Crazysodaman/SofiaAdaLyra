# CORE-002 | Ollama-to-Core genuine conversation shakedown

**Date:** 2026-11-08. **Baseline main:** dd7020ce48c06e82684d3439779266de9ea965b4.
**Scope:** disposable personal-Core application test; no production activation, service modification, model pull, fallback authorization, main changes, or release acceptance.

## Audit and implementation evidence

- Platform-owned `GenericOllamaProvider` calls the actual Python `ollama.Client.chat` transport, converts SDK messages and bounded tool proposals, and wraps provider failures in `LLMProviderError`.
- Sofía's `OllamaProvider` adds personal response-quality retry over that transport. `LLMCognitiveEngine` converts the provider error into a `CognitiveEngineError`; `CognitiveSystem` allows fallback only when a fallback engine was explicitly configured.
- Production `ConversationService.respond` enters a serialized turn, durable conversation, bounded context and cognition. `SofiaApplication` is the runtime entry point; `TestCognitiveEngine` is a distinct deterministic implementation.
- **Bug fixed in this draft:** a structurally valid Ollama payload with no meaningful text and no tool calls could enter personal quality repair instead of being classified as an inference failure. The shared provider now rejects it before repair/persistence; the existing valid tool-call-only path remains allowed.
- Pure/mock tests and prior source audits cannot prove a real model inference. Prior Run 1's `llama-server binary not found` message was a runtime incident report, not a currently reproduced host diagnosis.
- Current independent evidence for a sustained REAL-Ollama Core conversation: **NOT RUN / NOT ACCEPTED**. New opt-in integration acceptance test is also **NOT RUN** in this environment.

## Authorized Windows/Venus test (operator-run only)

**Prerequisites:** Owner approval for inference on the selected host; work in a disposable checkout/VM and fresh temporary canonical SQLite. Verify no other canonical Sofía writer is running. Do not start a second personal Core or modify the running Ollama service merely to make the test green.

First, read-only inspection from PowerShell:

```powershell
git rev-parse HEAD
ollama --version
ollama list
Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue
Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 5
```

The existing Ollama service must expose an installed model, e.g. `qwen3.5:9b`. A successful `/api/version` check proves HTTP reachability only, not that `llama-server` or any model works. If no listener exists, record a **FAIL**, do not auto-start one. If the expected model is missing, record a **FAIL**, do not auto-pull it.

When the owner has approved the already-running endpoint for a model-loading test, use the explicit probe (no automated model download or service start):

```powershell
$env:SOFIA_CORE002_LIVE = "1"
$env:SOFIA_OLLAMA_MODEL = "qwen3.5:9b"
$env:SOFIA_OLLAMA_URL = "http://127.0.0.1:11434"
# Set to the independently reviewed exact SHA for this run, not main HEAD.
$env:SOFIA_CORE002_EXPECTED_SHA = "<REVIEWED-EXACT-HEAD-SHA>"
python -m pytest -q -s -m integration test/test_core002_live_ollama_conversation.py
```

This exercises actual `SofiaApplication` -> `ConversationService.respond` -> production cognitive engine -> personal Ollama adapter -> generic transport -> unmodified real `ollama.Client.chat`, then checks multi-turn label retention, topic switch, generated replies and persisted user/assistant messages. The test prints a `CORE002_LIVE_RECEIPT` containing provider, configured model, endpoint, per-call status/latency, per-turn latency and no model output text. A provider wrapper records the actual call and delegates directly to the original transport; it does not simulate a reply. A skip, a replayed fixture, or a check that only calls `/api/version` is **NOT PASS**.

For independent context, run the pre-existing real-model test only when authorized:

```powershell
python -m pytest -q -s -m integration test/test_ollama_integration.py
```

The existing real-model test is a useful focused cognitive-runtime probe, but its direct `runtime.respond(CognitiveRequest)` path alone is not equivalent to a persisted multi-turn application conversation.

## Failure/recovery matrix for Team 2 + Team 5

| Case | Required result | Source of proof |
|---|---|---|
| Real available model | Nonempty model-generated responses through `ConversationService`; persisted turns | Explicit live integration test |
| Ollama server absent/refused | Typed failed inference; no synthetic assistant reply | Host plus negative tests |
| `llama-server binary not found` | Reproduce on isolated host or conclusively disprove with real generation | Host runner logs + exact package/model |
| Configured model missing | Typed failed inference; no auto-download without explicit host policy | Host negative test |
| Blank/whitespace/thinking-only response | `LLMProviderError`, no quality-repair canned reply | New provider regression tests |
| Timeout or interrupted stream | Bounded failure; no transcript of success; one Core instance only | Team 1 timeout/recovery + Team 5 exact-head tests |
| Lost GPU/capacity | Real error and recovery, never assert placement without evidence | Host receipts and Fleet routing tests |
| Provider recovers | Subsequent new turn succeeds without duplicate Core or duplicate writer | Two-boot disposable host run |
| Revoked/stale memory and goals | Contradictory, revoked or wrong-audience evidence never enters factual answer | Team 3 provenance + Team 5 checks |

**Provisional timeout correction in PR #253:** Both the generic and personal Ollama adapters now construct `ollama.Client(host=..., timeout=45.0)`. This is an **HTTP per-I/O timeout**, not a total request deadline. The default Core worker deadline is 120 seconds and lease TTL 180 seconds. Two nominal 45-second attempts leave 30 seconds for overhead, but repeated response transfers, host scheduling and reduced custom worker deadlines can still exceed that budget. The Core worker remains the authoritative wall-clock admission/fencing boundary. Team 1 must independently review and ACK exact deadline/lease alignment before release; no current real-host timeout receipt exists.

## External handoffs

- **Team 1:** certify single-writer lifecycle, startup/stop/restart and end-to-end generation timeout; provide disposable host/worker identifiers, failure and lease evidence.
- **Team 3:** certify scoped identity/personality/goals/retrieval; prove current, revoked and conflicting evidence cannot launder into model facts.
- **Team 4:** verify authenticated desktop/Discord/Core Link requests and response provenance on exactly the same conversation service; no bypass or duplicated Core.
- **Team 5:** independently execute provider negative suite, opt-in REAL conversation test, full persistence/provenance assertions, forced-kill and recovery on exact commit, signing and host receipts.

**Release / overall figures:** keep coordinator planning baseline unchanged at 40% (35-45% range); G8 0/16. No accepted inference, release GO or production rollout until independent real-host evidence exists.


## C-001-T2 historical five-failure reconciliation (not assumed current)

The historical full-project cleanup report explicitly classifies five live Ollama tests as failing when the cloud runner had no Ollama service/model. The relevant exact test names are:

1. `test/test_ollama_integration.py::test_real_ollama_cognitive_path`
2. `test/test_ollama_integration.py::test_real_ollama_receives_sofia_identity_context`
3. `test/test_ollama_integration.py::test_real_ollama_receives_sofia_instance_identity`
4. `test/test_embodiment_prompt_regression.py::test_embodiment_prompt_regression_variants`
5. `test/test_embodiment_prompt_regression.py::test_embodiment_repeated_generation_determinism_probe`

These are historical failures, not current exact-head test outcomes. The last two are experiments requiring multiple real generations, not a quick readiness probe. None of the five has been disabled, weakened or relabeled a pass.

The earlier `llama-server binary not found` Windows incident is distinct from those five no-server cloud failures. A real host should first record Ollama version, model inventory, endpoint version, host/platform, and server log outcome **without starting/restarting the service**; only with explicit owner approval should it run a real model generation. A successful HTTP version response or loaded-model inventory is insufficient to disprove a missing runner. A successful actual model reply at the *same model, host, Ollama build and GPU placement* is evidence the earlier symptom is not currently reproduced; it does not establish root cause for the original incident.

## Exact-head CI proof

The dedicated workflow `.github/workflows/core-002-ollama-boundary.yml` runs Python 3.12 on Windows and Ubuntu, compiles the modified sources, checks installed dependencies, and runs the real repository's non-integration Ollama/provider/conversation regression tests. Its live probe intentionally does not run on shared CI. Only a `success` conclusion on the **exact PR HEAD SHA** counts as this narrow deterministic CI PASS; it does not prove genuine inference.

## Live provider/provenance acceptance

The opt-in test uses **explicitly created temporary identity and personality files plus temporary canonical SQLite**, not `create_default_configuration()`, which may provision normal development state. It runs one `SofiaApplication` with the authoritative `ConversationService`, real routed cognitive engines with both roles using the same user-specified installed Ollama model, disabled verification/fallback/parallel routing, and no independent Core worker. Each turn must actually invoke a successful real `OllamaProvider._respond_once()` (observed by delegating to the original method), persist one user and assistant message, and produce a scoped `ReplyModelOriginStore` receipt tied to the exact saved assistant message. Content stays in the disposable conversation store; logs include SHA-256 hashes and timings rather than raw private conversation text.

The test is not evidence until an approved host executes it and Team 5 independently checks its receipts, installed model/build, transport and source SHA. If the host's full application rejects a turn through a deterministic scope without making the model call, the test fails that *genuine inference* requirement rather than treating a useful deterministic answer as a model generation.

**Team 1 ACK pending:** a 45-second per-I/O HTTP timeout does not guarantee a 45-second total call. Test both ordinary 120-second workers and valid shorter configured deadlines, fault injection, STOP/lease expiry during inference and recovery without a second writer. Never confuse an OS-side timeout with evidence that the model honored the cancellation.

**Team 5 independent QA pending:** capture host receipts, exact SHA, runnable command, provider `ollama`, actual installed model identifier/digest where available, Ollama server version, model runner result, per-call/per-turn latency, reply SHA-256, reply-model-origin kind/steps, failure classification, and restart recovery. Report each historic live test as PASS, FAIL or NOT RUN without conflation.

## C-003-T2 | Worker deadline and Core Link alignment (NOT AGREED)

- Verified in src/sofia/platform/core_worker/process.py: the parent _CoreWorkerProcess.respond() establishes a monotonic deadline, but _serve_provider_request() then calls binding.provider.respond() SYNCHRONOUSLY while holding the parent IPC lock.
- While this blocking provider call is in progress, the parent cannot check its response deadline or promptly quarantine the worker. The eventual deadline check may deny late results but is NOT proof of bounded cancellation.
- Generic and personal Ollama adapters currently use a 45-second PER-I/O HTTP timeout, not a total turn limit. Personal quality repair may issue a second model request. CPU model loading, response transfer and retries need separate wall-clock evidence.
- Team 1 Core worker response deadline defaults to 120 seconds with a 180-second lease TTL, but shorter valid worker deadlines exist. Team 4 Core Link client and server socket timeouts default to 30 seconds. They cannot guarantee synchronous completion of a legitimate slow model turn.
- Proposed cross-team safe contract: on 30-second client expiry retain exact client/session/idempotency identity, mark outcome UNKNOWN, reauthenticate and query conversation.result, never automatically regenerate. STOP, revoked grant, expired lease and generation change must fence late effects and delivery. Requesting cancellation is not proof Ollama stopped.
- Blocking issue sent to Team 1 PR #256 and 30-second reconciliation request to Team 4 PR #254. No deadline agreement, no production change and no certification until two-OS forced-blocking, STOP, late-result and restart receipts are independently reviewed by Team 5.

## C-003-T2 | Strict genuine inference evidence

- The opt-in live probe requires SOFIA_CORE002_EXPECTED_SHA to equal git rev-parse HEAD of the actual checkout. It queries the already-running Ollama model inventory READ ONLY, requires an installed model digest, and records model ID/configuration, provider latency, observed runtime process, local canonical identity UUID and disposable database path.
- Every turn must call the UNMOCKED Ollama client through the real application cognitive path. The final SAVED assistant reply SHA256 must exactly match a successful actual generated Ollama candidate, not merely a canned fallback after a failed attempt.
- Provider request observations require authoritative identity and saved personality context. These are prompt-delivery prerequisites, NOT proof that personality changed model behavior. Reviewer must compare observed replies and grounding separately.
- The local process/core identity/SQLite path is an observed writer receipt; it does NOT certify a verified exclusive RUN lease. No independently hosted two-machine Core shakedown is claimed.

## C-003-T2 | Memory direction P3-LEGACY-01 (disposable only)

- Team 3 PR #252 offers additive opt-in ReviewedMemoryEligibilityV1 and preserves current production composition. It remains unmerged and must not be imported into this branch without a pinned integration review.
- Joint disposable test after that contract is available: compare approved exact-original owner-private reviewed memory (lower-trust retrieval context) against LEGACY_UNATTESTED, revoked, corrected, expired, erased and cross-audience memories. Prove the latter are absent FROM MODEL REQUEST, not just from its final answer.
- Also verify same-writer restart, policy downgrade denial, erasure journal precedence, persona context, generated reply hashes, auditable candidate IDs and no fabricated owner attestation.
- Team 3 supplies exact opt-in composition hook, Team 1 fences writer generation, Team 5 independently runs model and memory evidence. Memory-influenced genuine inference remains NOT RUN.

## C-003-T2 | Negative / recovery verdicts

| Case | Current status |
| --- | --- |
| Blank/whitespace/non-text response | Source-level negative tests staged; CI pending |
| Connection refused, timeout, missing runner exception | Provider propagation negatives staged; actual current host not tested |
| Missing installed Ollama model | Current real-host negative NOT RUN; no auto-pull |
| 30s client timeout and durable unknown outcome | Contract pending Team 4; actual two-host test NOT RUN |
| 120s worker deadline during blocked provider | SOURCE BLOCKER, Team 1 correction pending |
| STOP, cancellation, late completion | NOT RUN; no false stop receipt |
| Restart, one writer, conversation retained | Genuine host acceptance NOT RUN |
| Four real model-generated turns, saved provenance | Strict test committed; NOT RUN |

Historical five real Ollama tests retain NOT-RUN-current status until separately executed. A CI skip or synthetic provider cannot count as real inference.
