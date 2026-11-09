# AG-D029 | Agent harness, inference runtime and model downloader alternatives

**Research date:** 2026-11-09.  
**Status:** RESEARCH ONLY / CANDIDATES IDENTIFIED / NO HARDWARE BENCHMARK OR PRODUCTION ADOPTION.  
**Parent:** [AEGIS_DESIGN_TODO.md](AEGIS_DESIGN_TODO.md), AG-D029; companion [Pi-specific research](AG_D029_PI_HARNESS_RESEARCH_AND_DESIGN.md).  
**Priority/release:** Existing AG-D028 Artifact Library and Platform 1.0 shakedown remain the prerequisite and are not changed by this research. No new #201 release row. No installs, owner-host execution or Fleet enrollment authorized.

## Executive recommendation

Do **not** select a single product to replace both Pi and Ollama. Separate:
1. **Agent execution harness:** Pi and Goose are the two strongest comparative pilot candidates; OpenCode and OpenHands serve as relevant task-specific baselines.
2. **Inference engine:** llama.cpp is the preferred first GGUF CPU/CUDA worker for Aegis Windows + Debian support. Retain Ollama as an existing compatibility provider. vLLM and SGLang are future Linux/high-throughput candidates, NOT assumed faster on a single RTX desktop.
3. **Model acquisition:** make Aegis Model Manager source-agnostic. Prefer an optional Hugging Face snapshot/file downloader for exact-revision GGUF assets; retain Ollama import support for already-installed models, gated on exact format and loader compatibility. The Artifact Library remains the single approved content registry/peer-transfer owner.
4. **Supervision:** keep Rust Aegis Platform ownership for leases, budgets, SAFE/STOP, trust, endpoint access, lifecycle, canonical receipts and Fleet placement. Any external agent runs isolated and untrusted. Sofía and other Cores retain one canonical writer and provider-neutral cognitive contract.
5. **Decision:** no actual performance/security winner until the pilots execute repeatable tests on disposable Windows and Debian hosts. OpenCode already used for Aegis coding remains a comparison baseline, not a compulsory platform dependency.

## A. Agent harness comparison

| Product | Confirmed official integration surface | Positive Aegis fit | Constraints / risks | Verdict for research |
| --- | --- | --- | --- | --- |
| **Pi 1.x** (MIT, TypeScript) | JSONL subprocess RPC, print mode, TS SDK, model providers, extensions | Small, purpose-built replaceable worker; language-independent subprocess; clear agent settlement events | Requires separate runtime; extension tools run as process identity; project trust is not a sandbox; runner/worker needs exact version pinning and real isolation | **Co-primary candidate**, strongest small external worker |
| **Goose** (Apache-2.0, Rust) | Rust crate/provider architecture, CLI/desktop/API, MCP, local/compatible providers | Language alignment with Platform; general-purpose tasks; candidate integration with native on-device inference | A larger agent platform; overlaps Aegis agent, state, tool and resource authority; upstream explicitly recommends isolated VM/container; all API/ABI stability and disable semantics must be measured | **Co-primary candidate**, strongest Rust-oriented pilot |
| **OpenCode** (MIT) | HTTP/OpenAPI 3.1 server and SDK, local models | Mature coding/repo workflow, already familiar in Aegis development; excellent comparative baseline | Explicitly lacks an OS sandbox; broad IDE/server sessions and permissions overlap Platform; code-centric rather than general persona harness | **Baseline** and optional dedicated coding agent |
| **OpenHands Software Agent SDK** (Python/TS/REST) | Python/TypeScript and REST, ephemeral Docker/Kubernetes workspaces through Agent Server | Isolation-oriented dedicated dev-worker model, automation, multi-step repo tasks | Heavier container/service footprint, duplicates Aegis job orchestration if embedded without limits | **Coding-lab alternative**, not Core runtime |
| **Codex CLI** (Rust, Apache-2.0) | CLI/exec, local --oss with Ollama/LM Studio; Rust codebase | Strong code-worker comparison; native Rust ecosystem | Coding-specific; supported local models, task control and native Windows deployment must be checked for pinned release; not general memory/personality infrastructure | **Optional benchmark**, not a platform dependency |

**Goose-specific nuance:** current upstream `goose-providers` exposes `local-inference`, `cuda`, `vulkan` and `mlx` features; the Rust crate references Candle-based local inference. This is a viable experiment, **NOT verified** to load the owner's exact Qwen model or match llama.cpp's architecture coverage, GPU performance, streaming or structured tool calling. Goose's tool shim may route via a separate Ollama model by default if enabled; to achieve Ollama-independent inference, explicitly configure the local backend and test no hidden network/model process dependency.

**Security finding:** Pi security docs state no built-in OS sandbox. OpenCode security docs explicitly call its permission system a UX feature, not isolation. Goose security docs advise VM/container operation against prompt injection and privileged local tooling. Aegis must enforce its own OS sandbox, broker, capability and STOP boundaries for **all** candidates.

## B. Inference engine comparison

| Engine | Key strengths | Deployment fit / limitations | Trial placement |
| --- | --- | --- | --- |
| **llama.cpp** | Native C/C++ GGUF, Windows/Linux, CUDA, mixed CPU/GPU, OpenAI-style API, model/tool/structured generation | Excellent for smaller quantized models on a consumer GPU; confirm GGUF architecture, chat template, multimodal assets and tool calling per model | **Primary engine pilot** |
| **Ollama** | Very convenient pull/serve API, installed ecosystem, existing Aegis adapter | Extra daemon and provider-owned model packaging; model cache not guaranteed drop-in for upstream llama.cpp | **Existing fallback + benchmark baseline** |
| **LM Studio / llmster** | Friendly download/manage UX, `lms` CLI, headless daemon, desktop and server API | Another independently owned runtime/model manager; redistributability/license of complete app must be reviewed | **Operator UX/optional provider comparison** |
| **vLLM** | Production batching/scheduling/concurrency and Linux CUDA ecosystem | Official native Windows unsupported; WSL/Linux required; not necessarily best for a single 12 GB GPU | **Future Linux GPU fleet candidate** |
| **SGLang** | High-throughput serving, prefix caching, parallelism, model/hardware support | Extra complexity and Linux/production focus; verify feature support on the exact GPU/architecture | **Future high-throughput candidate** |
| **LocalAI** | Multiple modalities + pluggable backends under compatible APIs | Adds another model manager/container backend system overlapping Aegis modules | **Optional multimodal provider only** |
| **llama-swap** (Go) | Cross-backend hot swapping/idle unloading API and routing | Risks duplicate model resource scheduler and second authority if independently deployed | **Reference design**, optional isolated comparison |
| **RamaLama** | OCI model/runtime packaging with Podman/Docker; HF/OCI/Ollama transports | Requires container ecosystem; its README warns some Ollama-produced models are not directly llama.cpp-compatible | **Artifact packaging research**, not default runtime |

Do not interpret support for NVIDIA hardware as an actual speed guarantee. Benchmark token throughput, p50/p95 first-token latency, prefill, concurrency, context, KV pressure and tool schema accuracy on actual approved hardware.

## C. Model acquisition (important change to original Option B)

**Better long-term contract:** `aegis.model_source` with adapters for:
- **Hugging Face Hub**: exact revision/snapshot/filename via `hf download` or `huggingface_hub`; direct path to a compatible GGUF and declared dependency files.
- **Ollama**: keep `ollama pull` and existing installed cache as an acquisition option, not the only source; require an explicit importer that verifies actual model bytes and backend-specific compatibility.
- **Approved local bundle / AG-D028 Hub / enrolled peer**: already governed artifact sources; model license and explicit opt-in distribution matter.

**CRITICAL COMPATIBILITY WARNING:** The upstream Ollama repository currently contains a `llama/compat/` layer to translate published Ollama GGUF metadata/tensors into layouts accepted by llama.cpp. Therefore, `ollama pull` does not imply standalone llama.cpp can read its blobs. Prefer source-compatible GGUF files from a pinned Hugging Face revision when available; never fake successful import or silently convert without explicit tested support. Validate quantization, tokenizer, chat template, special tokens, multimodal projectors and licensing. A digest only proves byte identity, not safe provenance or usage rights.

Possible model artifact lifecycle: DISCOVERED -> OWNER_SELECTED -> FETCHED -> HASH_VERIFIED -> POLICY_VERIFIED -> BACKEND_COMPATIBLE -> STAGED -> AVAILABLE -> LOADED -> UNLOADED / QUARANTINED. Acquisition, installation, activation and Fleet export remain distinct approvals and receipts.

## D. Recommended future evaluation matrix (all NOT TESTED)

**D029-A1: agent baseline:** same repo snapshot, same model *digest*, context, sampling, tool schemas, budgets; run Pi, Goose, OpenCode, OpenHands and a Core-only baseline on identical tasks. Record real tests passed/failed, files changed, tool actions, latency, prompt token usage, output validity, and recovery. Avoid claiming apples-to-apples if provider features differ.

**D029-A2: agent isolation:** read-only report, disposable code modification, malicious repo prompts, rogue extensions, direct shell, network attempts, unexpected worker crash, stdout floods, STOP during action, worker lease expiry and owner revocation. All privileged action effects must remain outside the agent's own authority. Pi's `agent_settled` must be respected; Goose/OpenCode/OpenHands use their own verified terminal-event semantics.

**D029-I1: GGUF inference:** CPU and CUDA on approved disposable Windows; Debian CPU; native Windows/WSL constraints; Qwen3.5:9b only if exact quantized build/tool template is supported; measure TTFT, decode throughput, memory, context growth and busy-GPU coexistence. Include an intentionally unsupported model and truthful denial.

**D029-I2: provider portability:** run the same bounded `CognitiveRequest` and `CognitiveResponse` through Ollama and an independent llama.cpp adapter without breaking Core state, memory, tool proposal semantics or Fleet trust. No silent routing changes.

**D029-M1: acquisition:** exact Hugging Face revision -> approved GGUF snapshot -> Aegis Artifact Library verification -> local llama.cpp run; compare Ollama pull -> importer -> explicit compatible/incompatible result; ensure no inference daemon required after successful native import.

**D029-F1: Platform-only regression:** boot without Pi/Goose/LLM/Node/GPU. Verify agent uninstall leaves Platform and protected Core state intact. Full Artifact Library LIB-01..LIB-16 and #201 release gates remain separate and not waived.

**D029-F2: software supply chain:** record exact signed/verified binary revision, license, redistribution and attribution, transitive dependencies, network controls, updates/revocation and rollback. An external agent package never auto-installs, mints grants or silently modifies `main`.

## E. Decision gates and conditional recommendation

1. **If minimizing engineering scope:** choose **Pi + llama.cpp + HF downloader** behind optional modules and existing Platform security.
2. **If Rust-native embedding matters most:** evaluate **Goose + llama.cpp + HF downloader** first, optionally Goose Candle local-inference as a *separate* benchmark. Check Rust crate compatibility, API stability, permissions and resource ownership carefully.
3. **If unattended software development dominates:** keep OpenCode and compare OpenHands's isolated Agent Server; do not force a coding agent into core personal cognition.
4. **If fleet GPU throughput becomes the constraint:** schedule vLLM/SGLang Linux-only evaluation later, behind the same provider contract.
5. **If a flexible model manager is the real objective:** prioritize AG-D028 + a versioned Aegis model-source interface; no need to make Ollama, LM Studio, RamaLama or llama-swap mandatory.

**Current tentative combination:** Aegis Rust Platform (sole authority) + optional `agent.pi` and `agent.goose` (one approved execution backend per job) + optional llama.cpp inference worker + `model_source.huggingface` and `model_source.ollama` adapters + AG-D028 Artifact Library. All names are proposed, **not** registered/installable components.

## F. Primary-source citations (research accessed 2026-11-09)

- Pi official RPC: https://pi.dev/docs/latest/rpc ; security: https://pi.dev/docs/latest/security
- Goose official: https://github.com/aaif-goose/goose ; providers: https://github.com/aaif-goose/goose/blob/main/crates/goose-providers/README.md ; Rust feature flags: https://github.com/aaif-goose/goose/blob/main/crates/goose/Cargo.toml ; security: https://github.com/aaif-goose/goose/security
- OpenCode server/OpenAPI: https://docs.opencode.ai/docs/server/ ; security: https://github.com/anomalyco/opencode/security
- OpenHands Software Agent SDK: https://github.com/OpenHands/software-agent-sdk
- Codex local provider: https://github.com/openai/codex/blob/main/codex-rs/utils/cli/src/shared_options.rs
- llama.cpp: https://github.com/ggml-org/llama.cpp ; API server: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Ollama GGUF compatibility: https://github.com/ollama/ollama/blob/main/llama/compat/README.md ; model pull API: https://github.com/ollama/ollama/blob/main/docs/api.md
- Hugging Face pinned downloads: https://huggingface.co/docs/huggingface_hub/en/guides/cli
- LM Studio: https://lmstudio.ai/docs/developer/core/headless
- vLLM platform: https://docs.vllm.ai/en/latest/getting_started/installation/gpu/
- SGLang: https://github.com/sgl-project/sglang
- LocalAI: https://github.com/mudler/localai
- llama-swap: https://github.com/mostlygeek/llama-swap
- RamaLama: https://github.com/containers/ramalama

**Evidence declaration:** Documentation/source review only. Zero models installed; zero jobs run; zero hardware performance measurements; zero live host acceptance assertions.
