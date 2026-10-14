# V18 CA-1207 model/provider payload safety batch

Date: 2026-10-14. Reviewed against current `main` provider adapter. No
live model, production host, permission grant or canonical database touched.

## Existing production behavior reused

`OllamaProvider` already translates typed model responses into
`CognitiveResponse` candidates for the caller and blocks unrequested tool
calls. The adapter already validates malformed payload containers, strings
versus objects, missing functions and names, and malformed JSON syntax.
This patch strengthens that exact adapter; there is no parallel dispatcher.

## Remaining source gap fixed

JSON tool arguments were decoded with permissive `json.loads`, silently
accepting duplicate object keys, non-standard `NaN`/`Infinity`, and
native non-JSON objects. Unbounded tool-call lists and massive argument
trees could exceed CPU and RAM expectations before authorization.

The adapter now rejects ambiguous keys and non-finite numbers, validates
native and decoded argument trees, and limits tool candidates to 16 calls,
64 KiB JSON bytes per call, 4096 nodes and nesting depth 16. Rejected
input raises content-free `LLMProviderError`; it cannot reach any tool
executor, model quality retry, conversation persistence or grant path.
Normal bounded nested JSON values remain unchanged.

## Focused acceptance, threat review, and open work

`test/test_ollama_malformed_response_boundary.py` adds valid and invalid
JSON/string and native payload regressions: duplicate keys, NaN/Infinity,
non-string keys, unserializable data, cyclic references, oversized strings,
oversized lists, excessive nesting, fan-out and Unicode. This source batch
is **not accepted** until tests run against the pinned commit on Linux and
Windows and the relevant installed-wheel provider boundary is checked.
Real Ollama server outages/timeouts, verified human-readable background
diagnostics and full CA-1207 integration remain open. No task status was
promoted and no source evidence was rewritten in the shared ledger.

The limits are finite CPU/RAM guardrails, not additional permission. SAFE
authorization remains downstream and cannot be created by any model output.
