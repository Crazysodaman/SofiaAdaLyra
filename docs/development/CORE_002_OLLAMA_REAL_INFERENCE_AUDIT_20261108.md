# CORE-002 | Ollama-to-Core genuine conversation shakedown

**Date:** 2026-11-08. **Baseline main:** dd7020ce48c06e82684d3439779266de9ea965b4.
**Scope:** disposable personal-Core application test; no production activation, service modification, model pull, fallback authorization, main changes, or release acceptance.

## Audit and implementation evidence

- Platform-owned \`GenericOllamaProvider\` calls the actual Python \`ollama.Client.chat\` transport, converts SDK messages and bounded tool proposals, and wraps provider failures in \`LLMProviderError\`.
- Sofía's \`OllamaProvider\` adds personal response-quality retry over that transport. \`LLMCognitiveEngine\` converts the provider error into a \`CognitiveEngineError\`; \`CognitiveSystem\` allows fallback only when a fallback engine was explicitly configured.
- Production \`ConversationService.respond\` enters a serialized turn, durable conversation, bounded context and cognition. \`SofiaApplication\` is the runtime entry point; \`TestCognitiveEngine\` is a distinct deterministic implementation.
- **Bug fixed in this draft:** a structurally valid Ollama payload with no meaningful text and no tool calls could enter personal quality repair instead of being classified as an inference failure. The shared provider now rejects it before repair/persistence; the existing valid tool-call-only path remains allowed.
- Pure/mock tests and prior source audits cannot prove a real model inference. Prior Run 1's \`llama-server binary not found\` message was a runtime incident report, not a currently reproduced host diagnosis.
- Current independent evidence for a sustained REAL-Ollama Core conversation: **NOT RUN / NOT ACCEPTED**. New opt-in integration acceptance test is also **NOT RUN** in this environment.

## Authorized Windows/Venus test (operator-run only)

**Prerequisites:** Owner approval for inference on the selected host; work in a disposable checkout/VM and fresh temporary canonical SQLite. Verify no other canonical Sofía writer is running. Do not start a second personal Core or modify the running Ollama service merely to make the test green.

First, read-only inspection from PowerShell:

\`\`\`powershell
git rev-parse HEAD
ollama --version
ollama list
Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue
Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 5
\`\`\`

The existing Ollama service must expose an installed model, e.g. \`qwen3.5:9b\`. A successful \`/api/version\` check proves HTTP reachability only, not that \`llama-server\` or any model works. If no listener exists, record a **FAIL**, do not auto-start one. If the expected model is missing, record a **FAIL**, do not auto-pull it.

When the owner has approved the already-running endpoint for a model-loading test, use the explicit probe (no automated model download or service start):

\`\`\`powershell
$env:SOFIA_CORE002_LIVE = "1"
$env:SOFIA_OLLAMA_MODEL = "qwen3.5:9b"
$env:SOFIA_OLLAMA_URL = "http://127.0.0.1:11434"
python -m pytest -q -s -m integration test/test_core002_live_ollama_conversation.py
\`\`\`

This exercises actual \`SofiaApplication\` -> \`ConversationService.respond\` -> production cognitive engine -> personal Ollama adapter -> generic transport -> unmodified real \`ollama.Client.chat\`, then checks multi-turn label retention, topic switch, generated replies and persisted user/assistant messages. The test prints a \`CORE002_LIVE_RECEIPT\` containing provider, configured model, endpoint, per-call status/latency, per-turn latency and no model output text. A provider wrapper records the actual call and delegates directly to the original transport; it does not simulate a reply. A skip, a replayed fixture, or a check that only calls \`/api/version\` is **NOT PASS**.

For independent context, run the pre-existing real-model test only when authorized:

\`\`\`powershell
python -m pytest -q -s -m integration test/test_ollama_integration.py
\`\`\`

The existing real-model test is a useful focused cognitive-runtime probe, but its direct \`runtime.respond(CognitiveRequest)\` path alone is not equivalent to a persisted multi-turn application conversation.

## Failure/recovery matrix for Team 2 + Team 5

| Case | Required result | Source of proof |
|---|---|---|
| Real available model | Nonempty model-generated responses through \`ConversationService\`; persisted turns | Explicit live integration test |
| Ollama server absent/refused | Typed failed inference; no synthetic assistant reply | Host plus negative tests |
| \`llama-server binary not found\` | Reproduce on isolated host or conclusively disprove with real generation | Host runner logs + exact package/model |
| Configured model missing | Typed failed inference; no auto-download without explicit host policy | Host negative test |
| Blank/whitespace/thinking-only response | \`LLMProviderError\`, no quality-repair canned reply | New provider regression tests |
| Timeout or interrupted stream | Bounded failure; no transcript of success; one Core instance only | Team 1 timeout/recovery + Team 5 exact-head tests |
| Lost GPU/capacity | Real error and recovery, never assert placement without evidence | Host receipts and Fleet routing tests |
| Provider recovers | Subsequent new turn succeeds without duplicate Core or duplicate writer | Two-boot disposable host run |
| Revoked/stale memory and goals | Contradictory, revoked or wrong-audience evidence never enters factual answer | Team 3 provenance + Team 5 checks |

**Known gap:** The shared HTTP Ollama client constructor presently does not set an explicit transport timeout in this path; Team 1 must reconcile a bounded end-to-end deadline with Core worker leases and Team 2 before changing it. Absence of a runtime-bound timeout is not a live hang reproduction.

## External handoffs

- **Team 1:** certify single-writer lifecycle, startup/stop/restart and end-to-end generation timeout; provide disposable host/worker identifiers, failure and lease evidence.
- **Team 3:** certify scoped identity/personality/goals/retrieval; prove current, revoked and conflicting evidence cannot launder into model facts.
- **Team 4:** verify authenticated desktop/Discord/Core Link requests and response provenance on exactly the same conversation service; no bypass or duplicated Core.
- **Team 5:** independently execute provider negative suite, opt-in REAL conversation test, full persistence/provenance assertions, forced-kill and recovery on exact commit, signing and host receipts.

**Release / overall figures:** keep coordinator planning baseline unchanged at 40% (35-45% range); G8 0/16. No accepted inference, release GO or production rollout until independent real-host evidence exists.
