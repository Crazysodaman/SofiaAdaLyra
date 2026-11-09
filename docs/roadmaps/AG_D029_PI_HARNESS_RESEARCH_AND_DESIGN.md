# AG-D029 | Pi Harness Research and Aegis Integration Design

**Research date:** 2026-11-09 (America/Chicago).
**Status:** CAPTURED / RESEARCHED / NOT IMPLEMENTED. This is a design/TODO item, not an installation instruction, implementation approval, a release gate, or a production acceptance certificate.
**Parent:** [AEGIS_DESIGN_TODO.md](AEGIS_DESIGN_TODO.md), existing AG-D029. **Relationship:** AG-D005 Model Manager; AG-D028 Artifact Library; AG-D007 Control Center; [Hardware-neutral Fleet and inference](../sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
**Release fence:** Complete the existing Platform 1.0/AG-D028 host acceptance separately. Pi MUST NOT become a prerequisite for Core-free Platform boot, or silently modify issue #201's 38-row acceptance matrix.
**Proposal:** Evaluate Pi 1.x as an optional, pinned, isolated Aegis agent-execution module (`agent.pi`), initially for explicitly delegated, bounded development tasks. Keep Aegis's existing Core cognition and LLM provider interfaces; optionally connect Pi to Ollama inference for a baseline and to llama.cpp for native local inference. Ollama-only-downloader is an *optional later model-acquisition architecture*, not a working feature or an assumed requirement for Pi.

## 1. Research verdict and terminology

**Recommendation:** PROTOTYPE LATER, NOT REPLACE CORE. Pi solves the agent-loop, tool-calling, session and extensibility portions of a coding/task agent. Pi is **not** the model inference engine. Pi + llama.cpp uses Pi for orchestration and a native inference backend; Pi + Ollama uses Ollama for inference. Neither means Aegis has written its own kernel or owns the upstream Pi implementation.

Current official Pi documentation describes Pi 1.0, `@earendil-works/pi-coding-agent`, TypeScript SDK, CLI and headless JSON RPC, extension hooks, models, and local llama.cpp router support. Historic `@mariozechner/*` examples exist; use the *pinned installed release's* CLI and protocol, not unversioned blog examples. The Pi project advertises MIT licensing; confirm exact shipped source, NOTICE/attribution obligations, transitive dependency licenses, signing and supply chain at adoption.

Pi's experimental "Pi Durable" package is NOT part of the recommended initial adapter. It may provide its own task persistence, but would risk duplicate scheduling/state semantics until explicitly compared with the Platform's canonical job authority.

**Alternatives to measure, not prejudge:**
| Approach | Agent orchestration | Inference | Aegis integration | Main tradeoff |
| --- | --- | --- | --- | --- |
| A: Existing Core + Ollama | Existing Core | Ollama | Current, baseline | No external coding-agent harness |
| B: Pi + Ollama | Pi for delegated jobs | Ollama | Optional `agent.pi` | Fastest experiment; Ollama still serves models |
| C: Pi + llama.cpp | Pi for delegated jobs | llama.cpp native router/server | Optional `agent.pi` + provider adapter | Preferred independence pilot; more packaging/model validation |
| D: Custom Aegis agent harness + native inference | Aegis | native backend | New project | Highest maintenance/verification burden |

Do not rank token speed, quality or engineering savings without same-model/same-hardware measurements. Pi's existence does not establish good structured tool calling from any particular quantized local model.

## 2. Non-negotiable ownership boundaries

| Owner | Allowed responsibilities | Must not own |
| --- | --- | --- |
| Aegis Platform Rust service | Identity, authenticated operator sessions, SAFE/STOP/grants/revocation, approved task admission, module lifecycle, worker supervision, budgets, Fleet routing, protected receipts | A Core's autobiographical memory, personality or opinions |
| Aegis generic agent-executor SDK | Versioned job/cancel/status/result data contract and adapter interface | A second security authority |
| `agent.pi` adapter | Translate admitted task to Pi RPC, relay bounded events, cancel worker, produce untrusted proposals/results | Unrestricted host privileges, signing, installation, secret access, trusted status claims |
| Pi child process | Agent loop, delegated context, restricted tools inside its sandbox, transient job history | Owner authentication, Core identity, canonical Core memory, protected host writes |
| Inference provider (Ollama/llama.cpp/other) | Generate model tokens and tool-call *proposals* | Tool execution, SAFE grants, Core identity |
| Model Manager + Artifact Library | Exact model identity/digest, licensing, approved acquisition and local admission, optional authorized peer distribution | Automatic model switch, shadow model registry, credentials or Core private state |
| Sofía and other Cores | Canonical personality, goals, interpretation of proposals, memory under one writer, discretionary request for approved tasks | Minting Platform permissions or treating Pi session history as Core memory |

**Two distinct workflows:**
1. Ordinary Sofía chat: Core -> existing `CognitiveRequest` / `LLMProvider` -> provider -> `CognitiveResponse` -> one Core writer. **Do not insert Pi as a compulsory second decision-maker**.
2. Delegated agent work: Core or authenticated operator *proposes* a scoped job -> Platform SAFE admission -> generic AgentExecutor -> `agent.pi` -> isolated task workspace + approved model -> untrusted diff/report/tool output -> Platform validation/receipts -> Core may evaluate. No direct trusted patch publication or real-host effect.

Core-free Platform startup must work when no Core, Pi, Node, Ollama, llama.cpp, model or GPU is installed. A Core-free owner may still authorize Pi jobs if the optional module exists. Pi uninstall/deactivation preserves Core and Platform state.

## 3. Integration transport and lifecycle

**Prefer a supervised subprocess running `pi --mode rpc` over embedding Pi's TypeScript SDK into the Rust OS service.** IPC is strictly LF-delimited JSON records on stdin/stdout; diagnostics belong to stderr. The Pi RPC docs require splitting on LF only, not arbitrary Unicode separators; accept optional CRLF. Install the stdout event listener/reader before sending a prompt; drain stdout/stderr concurrently with bounded buffers/backpressure.

A `prompt` response with success/disposition means accepted/queued/handled, **not job completion**. `agent_end` is not final when follow-ups/retries remain. Wait for `agent_settled` for the agent to finish, then independently verify result and any allowed staged effects. Correlate RPC command responses using their request IDs; session events may not carry those IDs, so bind one exclusive task/session to a worker or maintain a tested deterministic mapping. Explicitly handle `disposition=handled` (no run), queued/steered prompts, provider errors and late events.

**Proposed Aegis job states:** CREATED -> ADMISSION_PENDING -> ADMITTED -> STARTING -> RUNNING -> CANCELLING -> SETTLING -> COMPLETED | FAILED | CANCELLED | QUARANTINED. A task is COMPLETED only after Pi settles *and* Platform verifies the output/receipts, never merely on accepted command or child process exit 0.

**Required controls:**
- Signed, exact Pi binary/package version and approved optional extension list; install via Artifact Library when supported. No implicit Pi self-update/package download.
- Version/feature handshake and strict protocol parser (frame sizes, UTF-8, JSON nesting, counts, output rates). Unknown event types fail safely or stay ignorable only when explicitly documented by schema.
- One authenticated Aegis job ID, scope, owner/actor, audience, model digest, worker generation, target sandbox and deadline; SDK protocol negotiation must reuse existing Platform version rules.
- Bounded start, queue, inference, tool, idle, output, total wall-clock deadlines; limit tokens, tool calls, filesystem bytes, CPU, memory, process children and network egress.
- Attempt Pi `abort`, then terminate child/process tree after a bounded grace interval. **Cancellation is not rollback.** Discard/inspect disposable workspaces and never publish late results after STOP, revocation or generation change.
- Restart and replay: idempotent read-only tasks may be explicitly retried; a previously executed side-effecting command MUST NOT be blindly replayed. Lost state reports UNKNOWN/INCOMPLETE with a recovery receipt, not success.
- No direct tool execution from inference replies. Tool candidates must pass the established capability gateway, or be restricted to throwaway workspace effects with separately reviewed scope.
- One canonical Platform job/receipt ledger. Pi session files are optional scoped debug task history and are **not** Core memory or a second durable authority.
- Disabling/uninstalling Pi must revoke admission, settle/kill workers, remove exposed tool capability, and leave the Core's normal provider unaffected.

**Illustrative agent-executor boundary (proposal, not current wire implementation):**
`AgentTaskRequest(v1)` = {request_id, principal_id, audience_id, task_kind, workspace_artifact_digest, model_reference, allowlisted_tools, cpu_ram_disk_network_budgets, deadline, privacy_class, approved_scope, worker_generation}.
`AgentTaskResult(v1)` = {request_id, terminal_state, provenance, model_digest, output_refs, staged_diff_digest, bounded_diagnostics, observed_effect_receipts}. All identities and receipts are verified by Platform, not accepted from Pi as authority.

## 4. Two operating profiles

**Profile R: Proposal / read-only.** For initial experiments. Read a separately prepared and deliberately redacted repository snapshot. Disable all builtin tools and discovery except an exact vetted, restricted tool adapter or run fully tool-free. No canonical repository mounts, external credentials or privileged network. Return a report and optional proposed patch artifact. Treat generated patches as untrusted.

**Profile D: Disposable coding lab.** When explicitly approved. Run entire Pi process and tools inside a disposable VM/container/OS sandbox with an isolated clone/worktree, constrained user, filesystem, shell, network and resource budgets. Test execution is permitted *only within that disposable guest*. Publish a diff/test report, not a direct merge. Apply-to-main, module install, host shell, Fleet actions, Core self-update and signing are separate Aegis-governed operations.

CLI `--no-tools` / `--no-extensions` / `--no-mcp` / `--no-skills` / `--no-context-files` / `--no-approve` are useful **defense-in-depth configuration**, subject to exact-version testing; **they are not a security boundary**. Pi project trust, extensions, direct RPC bash commands, editor commands, indirect child processes, mounted credentials, and network connections require OS-enforced confinement. Extensions run with Pi process privileges. Disable user/project auto-loading and supply only curated signed extension files. Explicitly test what is still reachable, including RPC shell commands.

Windows: compare native restricted process/user with disposable Hyper-V/WSL/VM or container; do not assume Unix UID/GID/cgroup rules translate directly. Debian 12: dedicated service account plus actual namespace/container/VM resource limits; never grant access to canonical SQLite, Aegis owner secrets, Core identity or active installation directories. Host-specific sandbox capability is a hard admission requirement for Profile D.

## 5. Model-provider paths and Ollama-downloader vision

**Phase 0 baseline:** Pi -> configured Ollama inference API, with Aegis existing Ollama provider and Core path kept unchanged. This validates Pi's tool loop separately from model-runtime novelty.

**Phase 1 preferred pilot:** Pi -> localhost/isolated Aegis-managed llama.cpp router or compatible endpoint -> verified GGUF. Official Pi docs support the llama.cpp router and local model selection. The router is a *separately supervised native inference backend*, not a built-in Pi inference engine. Aegis must own model lifecycle/resource authority and avoid a competing uncontrolled model manager.

**Later downloader-only experiment:** Owner approves `ollama pull` or Ollama API acquisition; Aegis Model Manager inspects format, template, tokenization, license, metadata, digest and trusted source; Artifact Library registers immutable locally verified model artifacts; an Aegis-managed importer stages GGUF/model dependencies in a dedicated read-only inference store; llama.cpp loads them. A successful Ollama download does **not** guarantee loader compatibility. Some models require architecture-specific code, chat templates, multimodal projectors or additional assets; unsupported forms fail explicitly. Ollama is not required at Pi runtime *after successful import* but may still be necessary to perform future Ollama pulls. No assumption of an official stable export endpoint for every Ollama model. Respect model publisher and distribution licenses; peer transfers opt-in only.

**Fleet:** Pi job routing and inference placement may be on different enrolled hosts only after approved SAFE/resource assessment and authenticated transport; model identity, classification, expiry and generation bound to request. Discovery is not enrollment. Enforce revocation/STOP midstream; never let Pi pick its own untrusted Fleet host or copy Core private state. Avoid double-counting VM GPU resources on Artemis/Venus hardware inventory.

**Model-quality trial:** At minimum compare the same approved local Qwen model (for example the owner's Qwen3.5:9b where supported) using identical prompts, quantization, context, temperature and hardware. Evaluate tool-schema adherence, patch correctness and context overflow separately from token throughput.

## 6. Candidate module packaging and operator UX (future)

- Tentative optional module ID: `agent.pi`; no Core dependency and no automatic install.
- Expose through existing Aegis module SDK + canonical service management API; no standalone module permission database or signer.
- Control Center / headless CLI/TUI: AVAILABLE, VERIFIED, INSTALLED, ENABLED, WORKER_READY, RUNNING, DEGRADED, QUARANTINED, DISABLED; also show exact Pi version/digest, sandbox profile, model route, available resources, last verified event, tasks and denial reasons.
- Operator controls: inspect, install pinned package, enable, submit approved task, stream sanitized progress, cancel/STOP, inspect staged artifacts, deny, disable, repair, uninstall. Each privileged action is independently approved by existing Aegis authority.
- Artifact Library delivers Pi binaries, signed extension package, reproducible manifests and allowed model assets; shipping Pi/Node libraries must follow actual dependency and license obligations. Pi and optional native inference backend must not become mandatory Platform release prerequisites.
- Protect model prompts, tool outputs, private filesystem content, tokens and Pi histories from logs and Hub replication; keep bounded metadata-level audit under existing Platform privacy rules. Task data retention remains owner/policy scoped.

## 7. Threat model and failure analysis

| Threat/failure | Required mitigation / truth |
| --- | --- |
| Model prompt-injection requests host shell or protected file reads | Real sandbox + explicit broker allowlist; no credentials/mounts; deny and audit |
| Extension bypasses built-in tool hook | Whole-process isolation; pin + review extensions; cannot rely on extension interception alone |
| RPC success interpreted as task complete | Wait for settlement and post-run validated output; exact receipt |
| STOP/revocation during generation or tool effect | Generation fence, deny late events, kill worker; quarantine partial outputs; effects not magically undone |
| Worker crash, stdout flood or malformed JSON | Parser caps, independent drains, deadlines, process-tree cleanup, truthful FAILED/UNKNOWN |
| Rogue subprocess or network egress | OS sandbox isolation, egress denylist/allowlist, restricted user, no canonical mounts |
| Model provenance confused with license/signature | Independent digest verification, publisher/license checks, explicit approval and local admission |
| Unexpected model format or incompatible tool template | Explicit unsupported status, no silent fallback |
| Pi session becomes accidental Core memory | Separate scoped task sessions; no canonical Core writer access; reviewed summary import only |
| Auto-update or package discovery supplies unreviewed code | Pin exact version+digest, disable discovery/network updates, Aegis-controlled signed artifact installation |
| Parallel jobs exhaust VRAM on Venus | Existing Platform resource reservations; explicit affinity and gaming/activity policy |
| Replayed tool call after crash duplicates change | No automatic side-effect replay; idempotence keys and sandbox discard |
| Telemetry leaks prompt, secrets or private repository content | Redact by default; audit metadata only, separately consent content capture |

## 8. Acceptance matrix for future disposable-host pilot

All are **NOT TESTED**, not passed by documentation research. Track exact Pi release SHA/digest, Aegis SHA, model digest, host profile, commands and observed artifacts.

1. **PI-01:** Aegis starts Core-free and without Pi/Node/model/GPU; all existing baseline tests remain healthy.
2. **PI-02:** Signed optional `agent.pi` package installs only after reviewed admission; disabled/uninstall leaves Platform and active Cores healthy.
3. **PI-03:** Rust/Python client parses strict JSONL including LF, CRLF, Unicode U+2028/U+2029 in JSON strings, fragmented records and bounded size.
4. **PI-04:** Prompt-accepted ≠ completed; wait for `agent_settled`, handle `handled`, retries, event ordering and missed-listener race.
5. **PI-05:** Correct request correlation under parallel command responses; one task cannot receive another task's events or workspace.
6. **PI-06:** Timeout, abort, forced kill, unexpected exit and restart leave no live child tools and publish no late successful response.
7. **PI-07:** STOP, owner grant revocation and stale worker generation deny work and quarantine all late outputs.
8. **PI-08:** Unknown caller, untrusted Fleet peer, expired scope and invalid SDK version are independently denied without tool effects.
9. **PI-09:** Tool-free/readonly profile cannot access shell, credentials, private state or filesystem paths outside approved snapshot (including direct RPC paths).
10. **PI-10:** Disposable coding profile cannot modify canonical repo, protected Core DB, Platform install, host service or network outside scope.
11. **PI-11:** Malicious prompt injection, hostile repository files, extension/package discovery and project trust cannot escape sandbox.
12. **PI-12:** Worker CPU/RAM/disk/time/tool count/output budgets and subprocess exhaustion are bounded and accounted for.
13. **PI-13:** Same-model Pi+Ollama baseline, correctness and performance measurements with real model generation.
14. **PI-14:** Pi+llama.cpp real GGUF prompt + streaming + schema tool proposal; test unsupported architecture/template failure truthfully.
15. **PI-15:** Explicit Ollama-only download -> model manifest/digest/license verification -> approved import -> native inference with Ollama inference not serving; or mark capability NOT IMPLEMENTED.
16. **PI-16:** Model residency/VRAM policy, idle unload, concurrent requests and pressure handling on approved hardware.
17. **PI-17:** Remote authorized model worker, Fleet authentication and exact digest routing; no unauthorized model or host swap.
18. **PI-18:** Core delegates a task and receives *proposals/data* only; unchanged identity, personality, canonical writer, protected memory and provider semantics.
19. **PI-19:** Canonical Aegis receipts distinguish accepted, running, settled, verified, denied, cancelled, failed and UNKNOWN; private task content not copied to Hub/telemetry.
20. **PI-20:** Equal-workload comparison with baseline/OpenCode (where available), Windows + Debian sandbox parity, packaging, licensing, rollback and readme evidence.

## 9. Proposed work order (not a scheduled sprint)

**R0 research review:** Pin actual Pi 1.x source/release, license/NOTICE, dependency closure, SDK/RPC schema and support matrix; record any incompatibility. No owner machines touched.

**R1 disposable RPC spike:** Aegis generic `AgentExecutor` contract + one restricted `agent.pi` adapter. Run deterministic fake-provider fixtures, test process supervision, parsing, settled/completed truth and forced cancellation.

**R2 sandbox spike:** Whole-process isolation on disposable Debian and Windows guests, deny-by-default tests including all extensions, project resource loading, RPC bash and network.

**R3 same-model benchmark:** Pi/Ollama baseline vs Pi/llama.cpp vs existing Aegis route with identical model/digest and tool tasks. Measure p50/p95 latency, throughput, memory, code correctness, context overflow, abort time and safety denies. Do not declare a winner without evidence.

**R4 Model Manager integration:** Only after AG-D028 is ready: optional Ollama downloader/importer and immutable model artifact support, reuse existing signed catalog and permissions; no second store or installer.

**R5 governance/adoption decision:** Independent review of PI-01..PI-20, real signed artifact tests, fallback/rollback, user choice of release scope. Explicit owner approval required before general availability or any production Core task delegation.

## 10. Open decisions for later owner review

1. **Task scope:** Start with coding/repository analysis only (recommended), or allow generic research tasks after sandbox parity? Exclude personal chat/Core orchestration initially.
2. **Backend:** Is Pi+Ollama used only for disposable baseline, and Pi+llama.cpp the target? Recommended yes, but model quality and format compatibility must be measured.
3. **First sandbox target:** Disposable Debian 12 guest first for enforceable process and network isolation; independently certify Windows later (recommended).
4. **Session privacy:** No Pi persistence by default; opt-in scoped job logs/metadata and separately reviewed output artifacts.
5. **Distribution:** Vendor exact pinned, signed Pi runtime and permitted dependencies via AG-D028; no auto global npm installs on production hosts.
6. **Agent portability:** Keep a generic provider-independent AgentExecutor protocol, so Pi can later be replaced by another agent harness without migrating Core memory.
7. **Pi Durable:** Defer pending analysis proving it doesn't duplicate Aegis canonical job state or authority.
8. **License and model redistribution:** Confirm both Pi dependency tree and each acquired model license before distributing to peers.

## 11. Primary research sources (checked 2026-11-09)

- Pi official: https://pi.dev/
- Pi 1.0 announcement and experimental Pi Durable: https://earendil.com/posts/pi-1-0/
- Pi RPC protocol and run completion semantics: https://pi.dev/docs/latest/rpc
- Pi RPC command reference: https://pi.dev/docs/latest/rpc-commands
- Pi CLI tool flags and resource discovery: https://pi.dev/docs/latest/cli
- Pi security / project trust / lack of built-in sandbox: https://pi.dev/docs/latest/security
- Pi isolation guide: https://pi.dev/docs/latest/containerization
- Pi extension threat surface: https://pi.dev/docs/latest/extensions
- Pi models / compatible endpoints: https://pi.dev/docs/latest/models
- Pi local llama.cpp router: https://pi.dev/docs/latest/llama-cpp
- Pi NVIDIA RTX/Windows examples: https://pi.dev/docs/latest/nvidia-rtx-llama-cpp
- Pi Windows: https://pi.dev/docs/latest/windows
- Pi SDK (not preferred for Rust integration): https://pi.dev/docs/latest/sdk
- Pi upstream source: https://github.com/earendil-works/pi
- llama.cpp server tool calling: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Ollama model information API: https://github.com/ollama/ollama/blob/main/docs/api.md

## 12. Existing Aegis source seams and status truth

- `src/sofia/sdk/cognition_engine.py` already defines provider-neutral `LLMProvider`; preserve Core request/response behavior.
- `src/sofia/platform/cognition_provider.py` currently constructs test/Ollama providers; do **not** simply identify an agent harness as a synchronous LLM provider, because Pi's autonomous tool loop has different semantics.
- `src/sofia/platform/distributed/inference.py` already enforces bounded wire contracts and reserves tool calls as data.
- `src/sofia/platform/distributed/inference_service.py` currently limits worker provider selection to Ollama. Extend only through a reviewed provider-neutral route if the llama.cpp worker is independently authorized; avoid weakening model allowlists.
- `src/sofia/platform/core_worker/provider_deadline.py` warns that timing out a synchronous provider thread does not stop native/network work; Pi worker supervision must implement real process cancellation.
- AG-D028 requires a verified Artifact Library for Platform 1.0; it explicitly does **not** require real model inference or Ollama for Core-free Platform operation.

**Research completion does not equal implementation or host certification.** This item is a future design TODO until owner schedules a specific experimental scope.
