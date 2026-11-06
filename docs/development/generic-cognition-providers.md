# Generic cognition provider boundary

`sofia.platform.cognition_provider.create_generic_llm_provider` explicitly
constructs a neutral model adapter. `test-llm` uses the shared deterministic
provider; `ollama` uses `sofia.platform.core_worker.ollama_transport`.
Unknown providers fail rather than selecting a fallback.

The existing `LocalOllamaInferenceService` factory injection surface accepts this
neutral factory without importing personal Core code. Its default remains the
legacy compatibility provider, now loaded only if selected. Exact node/model/
context/tool policy checks still precede provider construction. This pure service
is not enrollment authority: network callers still require the existing NET
transport authentication and scoped grants.

The Ollama adapter supplies existing host-owned endpoint validation, SDK
message/tool conversion, bounded strict JSON/tool decoding, configuration
budgets, content-free Platform performance instrumentation and provider error
translation. It does not apply an individual Core's personality, embodied
semantics or response repair. Proposals remain non-authoritative: returning a
tool call does not execute it or grant permission.

The existing `create_llm_provider` API and legacy `OllamaProvider` import paths
retain Sofía's existing response policy over the same transport implementation.
They remain compatibility composition, not the neutral API. Generic consumers
must select the neutral factory explicitly. No running composition is migrated.

Shared token budgets now belong to Platform; strict model JSON parsing belongs
to the existing SDK. Core exports remain aliases. The deterministic provider
also keeps its exact legacy class alias and response/error behavior.

Basic SDK/Platform imports and deterministic providers require no optional
Ollama package. Selecting Ollama requires the `ollama` Python dependency (already
required by the integrated distribution); a split wheel environment must install
that optional provider dependency explicitly. Its absence fails without a local
replacement or fabricated model response. Model construction does not perform
enrollment, grant tools or acquire a personal-state writer.

## Evidence and limits

A Core-blocked factory import failure was reproduced before separation. Source
and real installed SDK/Platform-only probes exchange distinct synthetic
Sofía/Roland/John request markers with independent provider instances. They check
exact message forwarding, no extra response policy calls, strict ambiguous-tool
rejection and no personal Core imports. The Ollama probes inject disposable fake clients; they do not demonstrate live
model availability or output quality. Separate checks cover minimal imports
with Ollama unavailable, legacy class identity and existing response-policy,
endpoint, generation-option, tool safety and performance behavior.

This supplies a generic provider construction/transport boundary. It does not
complete generic cognitive orchestration, authoritative personal-state hosting,
signed definition activation, production remote inference admission or full
Core Runtime separation. No protected identity, constitution, memories,
production services or Fleet authority are changed or activated.
