# Unified Rust modernization audit and implementation plan

**Status:** planning proposal only; no production code, deployment, protected
state, active Constitution, trusted hash, credentials, or host settings changed

**Audited source:** `main` at
`bb1fd13b6abfabfe6d30c356d06ae8469533deac`

**Planning branch:** `codex/rust-modernization-plan`

**Evidence date:** 2026-11-04 UTC

## 1. Decision summary

Adopt a **hybrid Rust Platform and Python Cognitive Core** by replacing
Platform-owned boundaries in reversible slices. Keep cognition, identity,
personality, relationships, memory interpretation, planning, learning, and
Constitution handling in the Python Core. Build a Rust Platform control plane
around the existing versioned SDK, Core Link, Fleet, SAFE, RUN/ACT, component
generation, and state-facade contracts. Do not introduce parallel authorities.

Use **Tauri 2** for the initial Rust tray, independent Companion, and Workbench.
Run a Platform-owned Rust UI broker as the sole policy and lifecycle owner for
those clients. Slint remains an optional future renderer adapter after the
Tauri acceptance baseline; it is not a second UI policy owner.

Reuse the existing Venus `CORE_LINK + MODULE_HOST` to Artemis `CORE_HOST`
topology. The Rust implementation must be wire-compatible with the Python
contracts before it can replace any endpoint. During migration, the current
Python/Tk UI remains installed and selectable as the fallback.

This modernization is **not a new GO LIVE priority**. G7-A, audit corrections,
and remaining G2 work retain precedence. No Rust component may enter the G7
candidate until its slice has compatibility, negative-security, rollback, and
installed-artifact evidence. G8 remains the physical acceptance gate.

## 2. Evidence vocabulary

- **OBSERVED:** directly inspected source, test, package, workflow, Git history,
  or public GitHub page at the audited SHA.
- **INFERRED:** a design conclusion supported by observed evidence but not yet
  implemented or exercised.
- **UNKNOWN:** evidence was unavailable, incomplete, pending, or requires a
  real host or authenticated GitHub API.

Every major finding below carries one of these labels.

Sections explicitly named **target**, **proposed**, **required**, **decision**,
or **recommendation** are **INFERRED design recommendations** unless a sentence
is separately labeled OBSERVED or UNKNOWN. They are not claims of implemented
behavior.

## 3. Repository, CI, and review baseline

| Finding | Class | Evidence and consequence |
|---|---|---|
| `origin/main` equals the supplied SHA | OBSERVED | Fetch resolved `main` to `bb1fd13b6abfabfe6d30c356d06ae8469533deac`. |
| The repository has no Rust source or manifest | OBSERVED | No `Cargo.toml`, `.rs`, `.slint`, or Tauri configuration was found. Rust begins as a new workspace, not an extension of existing Rust. |
| Python remains the only build root | OBSERVED | `pyproject.toml` builds `sofia-ada-lyra` and exposes `companion-runtime`; component-wheel generation is separately described by `packaging/components.toml`. |
| Eight PRs are open and all are drafts | OBSERVED | Public PR list: #122–#128 and #133. They cover G7-A, G3–G7 audit fixes, and the 700-task ownership plan. The modernization must rebase around, not duplicate, those changes. |
| Exact-SHA package matrix is 15/22 green | OBSERVED | Completed run [`41827400956`](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41827400956) failed `pkg_social`, `pkg_core`, `pkg_ui`, `pkg_know`, `pkg_dev`, `pkg_safe`, and `pkg_integrate`; the other 15 jobs passed. All seven contain the same permission CLI failure: production denied a missing owner secret and returned status 2 while the test still expected `SystemExit`. `pkg_core` and `pkg_safe` also contain the same stale FIDO2-only error-message assertion. This is one shared owner-authentication/test-contract reconciliation blocker, not seven demonstrated package-specific defects. |
| Windows RC, Debian RC, and Manual Verification failed | OBSERVED / INFERRED | Completed Windows run [`41827400858`](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41827400858) failed full verification; Debian run [`41827400887`](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41827400887) failed full installed-wheel verification; Manual run [`41827400879`](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41827400879) failed revision-pinned verification. Public annotations prove the failing steps and skipped downstream keyless jobs, but not their detailed cause. Attribution to the shared package mismatch remains INFERRED pending diagnostic-log review. |
| Current exact-SHA release conclusion | OBSERVED | `bb1fd13b6abfabfe6d30c356d06ae8469533deac` is not release-certified: seven package legs and all three full verification jobs failed, and both RC keyless provenance jobs were skipped downstream. Passing workflows on the SHA do not override these failures. |
| G8 production evidence | UNKNOWN / DEFERRED | Issue #129 says 16 physical acceptance items remain and production GO is not authorized. |

### Audit validation actually executed

- **OBSERVED:** 13 focused existing Python test files covering SDK contracts,
  state facade, Core Link, module-host state/process boundaries, supervisors,
  Windows service specification, UI launchers, screen authority, and remote
  mTLS produced **120 passed and 9 skipped** unique tests.
- **OBSERVED:** the first sandboxed run reported seven local-socket permission
  failures before application assertions. The socket-dependent selection was
  rerun with environment network permission and produced **10 passed**; this
  replaced all seven infrastructure failures.
- **OBSERVED:** no Rust tests were run because no Rust implementation exists and
  this assignment changes planning documents only.
- **OBSERVED:** follow-up capture validation ran the three focused vision files
  and produced **32 passed**. The two owner-authentication regressions were run
  separately and produced the expected **2 failed** diagnostic reproduction;
  they were not counted as a passing validation suite.
- **UNKNOWN:** focused tests do not establish full-suite, installed-artifact,
  Windows-native, Debian RC, or G8 acceptance.

### CI failure diagnosis and GO LIVE relationship

The package evidence is **OBSERVED**. `permissions_cli.main()` intentionally
catches authorization failures, emits a refusal, and returns `2`; the shared
test still asserts that the function raises `SystemExit`. The missing owner
secret was denied before any permission mutation. In `pkg_core` and `pkg_safe`,
the protected-approval test expects the word `FIDO2`, while the current denial
is “level-3+ execution requires freshly verified owner authentication.” A local
two-test reproduction produced **2 failed** with these exact mismatches. This
planning audit does not decide whether CLI compatibility or test expectations
must change.

The correction belongs to existing SAFE/GO LIVE work: reconcile the owner-secret
and FIDO2 contract, document which protected actions require a physical key,
preserve exact-action freshness and one-use binding, and rerun all 22 packages,
both installed-wheel RCs, and Manual Verification on one SHA. No Rust phase may
reinterpret this failure, relax SAFE, or substitute a Rust authentication path.
The RC provenance skips are downstream missing evidence, not signing successes
or independent signing defects.

### Open draft PR inventory

| PR | Head at audit | Scope |
|---|---|---|
| #122 | `92b1d686f56e989a3cf4f0e1265a3e3143555984` | G7-A evidence, learning, SAFE reconciliation |
| #123 | `2c2901a023e2e2b8e52084c22637deb9571aa8ac` | G3 writer fencing |
| #124 | `9fc88ab96a2681dd49b30382cefa4bf91f831f52` | G0/G1 active-release paths |
| #125 | `7a0e4ee1d244e727fcdff0437b5c7a21d86fad71` | G4 Core Link request bounds |
| #126 | `2530ec58c829d8f0ca5757c3ab10c750e80d1c71` | G5 recovery attestations |
| #127 | `817a631c0fe345a21f9938724e5dd712394a3ba4` | G6 signed module health |
| #128 | `4e7aced78ac3275e70efb9e7a5ecd85a8669e87d` | G7 handoff proof hardening |
| #133 | `fe9d3efa50242461830a296a5b8da01b7c3a85f3` | 700-task ownership documentation |

## 4. Existing code reuse matrix

| Existing owner or contract | Observed implementation | Rust use | Must remain authoritative |
|---|---|---|---|
| Platform roles | `PlatformRoleConfiguration`: `CORE_HOST`, `CORE_LINK`, `MODULE_HOST`, `STANDBY` | Parse the same schema and enforce the same role preconditions | Roles describe capability only; they do not install, pair, enroll, grant, or promote |
| Cross-component SDK | `sofia.sdk.contracts` has protocol negotiation, endpoints, authority projection, request envelopes, digests, deadlines, and generations | Generate Rust types and validators from a language-neutral schema | Platform authentication and authority validators |
| Core Link wire model | `sofia.sdk.core_link` plus Platform binding, access, transport, and conversation services | Implement a Rust client first; preserve exact JSON, size, time, identity, generation, and idempotency semantics | Existing paired binding and remote Core identity |
| Fleet transport | `distributed.https_transport`, TLS/PKI, endpoint-bound gateway, durable node identity, revocation | Reuse pinned mTLS topology for remote Platform services; do not create another transport trust root | Fleet identity, endpoint policy, SAFE, STOP, and capability gateway |
| Component worker protocol | `ComponentRequestEnvelope`, generation stores, Core worker controller | Rust supervisor can launch and monitor Python Core workers through a versioned IPC adapter | Python Core and Platform component generation owner |
| Local worker IPC | Core worker uses bounded JSON and component envelopes; research module uses HMAC-authenticated spawned-process IPC | Preserve as compatibility transport, then replace HMAC framing only through a versioned negotiated protocol | Existing component identity, authority, generation, payload digest |
| Component packages | Separate `sofia-sdk`, `sofia-platform`, and `sofia-core` wheels can be built and content-verified | Rust artifacts join the component manifest rather than replacing the Python Core wheel | Signed artifact, release digest, compatibility, rollback |
| State facade | `PlatformSDKStateFacade` exposes scoped canonical JSON projections and compare-and-set | Rust owns the server side only after conformance; Python Core consumes the same facade | State namespace owner, principal/audience scope, expected revision |
| Canonical SQLite policy | canonical-path guard, shared access, state plane, writer fencing | Do not port first. Call the Python owner or expose a narrow broker until a reviewed state slice is proven | One canonical writer and schema-specific owners |
| SAFE/STOP | permissions, exact execution approval, operator STOP, secret broker | Rust may host adapters only after equivalence and independent security review | Existing SAFE decision and STOP state; UI never signs or grants |
| RUN/ACT | work, effects, host-effect attestation, reconciliation, leases, receipts | Rust supervisor and UI broker consume or submit typed requests; no duplicate work ledger | RUN/ACT execution and receipt owners |
| Supervision | component/runtime supervisors, heartbeat, watchdog, Windows/systemd service adapters | Strong early Rust candidate after behavioral conformance | Durable STOP, lease epoch, generation, readiness, uncertain effects |
| Configuration | typed defaults, roles, user settings, reviewed projections, saved/effective revisions | Rust config broker reads/writes through versioned API | Existing config and settings authority, secret references |
| Current UI | Tk desktop, tray, settings, Core Link desktop/tray/control center | Remains fallback and oracle while Rust clients reach parity | Conversation, Core Link, SAFE/RUN, and state owners |
| Screen capture | `ScreenCaptureService` plus `WindowsExactWindowCapture` provide a real one-shot, owner-approved exact-window backend; settings UI still exposes proposal preparation only | Preserve this backend as compatibility oracle and integrate through a broker only after equivalent consent, target, STOP, approval, and receipt checks | SAFE exact scope, owner authentication, local canonical state, STOP, foreground HWND/PID binding, digest-only receipt owner |

## 5. Documentation and code discrepancies

| Finding | Class | Resolution |
|---|---|---|
| Architecture documents describe a long-lived isolated Platform and replaceable Core, but Platform source still imports Core implementation packages in 75 files | OBSERVED | Treat isolation as a target. Define an import-removal ledger and move one boundary per PR. |
| UI is described as a client/module, but 14 `sofia.modules.ui` files import Core cognition, goals, memory, social, emotion, or environment implementations | OBSERVED | Rust UI must consume Platform projections only. First add Python broker projections so both old and new UI can use them. |
| Core Link roles and Core-free desktop paths exist, while the integrated wheel remains the default package | OBSERVED | Retain integrated installation as fallback until component/Rust installers pass G2 installed-artifact acceptance. |
| Component wheels and an isolated import probe exist | OBSERVED | Reuse this packaging evidence; extend it to assert Rust Platform artifacts contain no Core assets and can run with the Python Core wheel absent on `CORE_LINK`. |
| Core worker is process-isolated for cognition, but imports Python Core engines from a Platform-owned module | OBSERVED | Move worker entrypoint and engine factory into the Core package; leave Platform with a protocol client and process supervisor. |
| Core Link conversation service imports Core conversation implementation | OBSERVED | Split server adapter into Core-host composition; keep Core Link client and transport Platform-owned. |
| The settings UI describes broad functionality, but a Core Link control center is presently read-only and only exposes selected settings snapshots | OBSERVED | Do not reproduce direct SQLite panels in Rust. Expand reviewed Platform query/command APIs by use case. |
| Settings UI says it prepares consent without capturing, while a production capture CLI and backend exist | OBSERVED | The gap is UI/broker integration, not pixel acquisition. Never infer capture from the proposal UI; only a post-capture digest receipt can attest a frame. |
| Existing quiet-hours settings govern ACT/outreach | OBSERVED | The approved Companion appearance policy has no quiet-hours restriction. Keep the policies separate rather than disabling ACT quiet hours. |
| No implementation of the new five-per-day appearance cap, DND/lock suppression, or durable manual-hide latch was found | OBSERVED | Implement these in the UI broker, not in Companion rendering code. |
| Documentation contains historical pass counts and older SHAs | OBSERVED | Use it for design provenance only. Current acceptance must bind the implementing SHA and artifacts. |

### 5.1 Screen-capture capability correction

**OBSERVED:** `ScreenCaptureService.capture_once` accepts an original typed
screen journey request and nonempty approval ID. It supports one-shot snapshots
for `LOOK_AT_WINDOW`, `SHOW_CHANGES`, and `NAVIGATE_GUIDANCE`; bounded follow is
rejected. The target is local hostname plus foreground HWND and PID, with
principal `person:sparks` and audience `local:text`. It rechecks STOP, permit
freshness, workstation-clear state, and the foreground tuple around the one-use
`screen.capture_once` execution approval and capture. PNG is bounded to 16 MiB,
digest-verified, retained in memory, and represented in canonical SQLite by a
digest-only receipt with no pixels.

**OBSERVED:** `WindowsExactWindowCapture` uses Win32/GDI `PrintWindow` for one
visible, titled exact HWND/PID after a topmost local YES/NO prompt. It caps the
frame at 12 million pixels, encodes PNG in memory, and fails closed on changed
foreground, hidden/titleless windows, invalid geometry, allocation/GDI failure,
and oversized output. It is a custom confirmation path rather than the Windows
Graphics Capture picker, and does not claim protected, accelerated, DRM, or
black surfaces are readable.

**OBSERVED:** `desktop_control_cli` is the current production composition. It
requires an owner-invoked CLI, pre-inspected exact HWND/PID, owner authentication
through `authorize_exact_action`, local canonical state, and the capture service.
Optional local Ollama interpretation is untrusted and cannot execute tools.
`settings_sections.py` prepares consent only; no tray, Workbench, or Core Link UI
capture invocation was found.

**INFERRED:** a Rust UI broker should call a narrow Platform capture service,
not recreate consent or SAFE. **UNKNOWN:** live Venus behavior, physical
owner-secret/FIDO2 flows, DPI/multi-monitor and focus races, protected surfaces,
lock transitions, model quality, and broker/Workbench integration remain
unverified and become candidate/G8 evidence only when included.

## 6. Target ownership

| Concern | Rust Platform owns | Python Core owns | Shared contract |
|---|---|---|---|
| Identity | authenticated endpoint and stable Core ID routing | Sofía identity, self-model, continuity interpretation | Core ID, generation, constitutional digest projection |
| Cognition | worker admission, resource scheduling, timeouts | reasoning, cognition v2, planning, evidence interpretation | versioned cognition request/response |
| Personality and relationships | scoped delivery and audience enforcement | personality, emotion, relationship choices | audience-scoped expression intent |
| Memory | canonical storage API, fencing, backup/recovery | relevance, autobiographical interpretation, promotion proposals | provenance-bearing state projections |
| Authority | SAFE, STOP, principal authentication, grants | judgment, consent expression, requests/refusals | authority projection and exact action fingerprint |
| Effects | capability gateway, RUN/ACT dispatch and receipts | proposed goals and evaluation of verified outcomes | idempotent request and independent outcome receipt |
| Fleet/Core Link | mTLS, pairing, routing, retries, revocation | Core-host conversation semantics | exact wire schemas and compatibility negotiation |
| Supervision | service/process generations, heartbeats, restart, update/rollback | Core readiness and graceful drain response | component lifecycle protocol |
| Configuration | validation, secret references, saved/effective revisions | Core-specific interpretation of eligible settings | typed setting descriptors and apply receipts |
| UI | broker policy, windows, OS signals, notifications, receipts | content, expression intent, invitation/proposal to appear | UI event/command/receipt schemas |
| Constitution | integrity verification and projection enforcement | active constitutional interpretation | version and digest; v2 remains inactive |

The Rust Platform must never import or embed Sofía's identity, personality,
Constitution text, memory, relationship state, or secrets in generic defaults.

## 7. Target topology

```text
VENUS (Windows)                                  ARTEMIS (Debian VM)

Rust Platform service                           Rust/Python Platform bridge
  roles: CORE_LINK + MODULE_HOST                  role: CORE_HOST
  SAFE/STOP/RUN adapters                          single canonical writer
  Fleet mTLS client             pinned mTLS       Python Cognitive Core
  Core Link client  --------------------------->  Core Link server adapter
  module supervisors                              state facade
        |
        +-- Rust UI broker (one policy owner)
              |-- tray client
              |-- independent Companion
              `-- Workbench

Python/Tk UI fallback remains installable and selectable until acceptance.
```

The topology reuses the existing authenticated relationship. It does not add a
Venus Core, a second conversation owner, a second module host authority, a
shadow state database, or a new approval service.

## 8. Cross-language SDK and compatibility contract

### 8.1 Canonical schema source

Introduce a small `contracts/` tree containing reviewed JSON Schema or
Protocol Buffers definitions plus normative canonicalization fixtures. Prefer
JSON Schema for the first boundary because current messages are canonical JSON
and Python validators already enforce exact fields. Do not adopt protobuf until
unknown-field, canonical-digest, and migration semantics are explicitly
resolved.

Required families:

1. component endpoint, protocol range, authority projection;
2. request/response envelopes and error taxonomy;
3. Core Link request/response, status, conversation, settings;
4. component lifecycle, health, drain, generation, heartbeat;
5. module describe/health/execute/cancel/result;
6. UI broker intent, decision, window, animation, perception, execution receipt;
7. saved/effective configuration and secret reference;
8. state projection and compare-and-set request;
9. Fleet endpoint identity and transport metadata references.

### 8.2 Wire invariants

- exact schema ID and `MAJOR.MINOR` negotiation;
- incompatible major versions fail before effect or state access;
- minor versions add only explicitly ignorable fields negotiated by capability;
- bounded UTF-8 payload and collection sizes;
- canonical JSON for hashing: sorted keys, no NaN/Infinity, defined Unicode and
  timestamp form;
- request ID, correlation ID, idempotency key, creation time, deadline;
- authenticated source/destination Platform, component, Core ID, release digest,
  and generation;
- principal, audience, authority reference, exact scopes, and expiry;
- payload type and digest checked before decode/dispatch;
- unknown, cancelled, timed-out, rejected, failed, and completed remain distinct;
- no language default may turn absent data into permission or success.

### 8.3 Compatibility policy

For every contract release, run the same golden corpus through Python and Rust:

- decode then re-encode produces the canonical bytes;
- both reject every malformed, oversized, extra-field, stale, wrong-generation,
  wrong-audience, expired, and digest-mismatched vector;
- both negotiate the same highest compatible version;
- both compute identical fingerprints and idempotency keys;
- previous supported minor fixtures remain accepted;
- the next incompatible major is rejected without network effect.

Never use an FFI binding into the live Python interpreter as the authority
boundary. Process IPC keeps crash isolation and makes rollback possible.

## 9. UI broker and proactive presence policy

### 9.1 Ownership

The **Rust UI broker** is a Platform component. It owns OS session signals,
window lifecycle, admission policy, daily counters, manual-hide state, and
receipt persistence through Platform APIs. Tray, Companion, and Workbench are
unprivileged clients. Core may propose an appearance or supply an expression;
it cannot open a window directly.

### 9.2 Approved policy encoded exactly

| Event | Broker rule |
|---|---|
| Companion autonomous appearance | Conditional; admit only an eligible Core proposal and all Platform gates |
| Workbench opening | A direct authenticated user launch opens directly; every Core-initiated opening requires explicit permission and cannot be inferred from conversational assent |
| Screen perception | Ask before every capture authority grant; selection must be explicit and scoped |
| Daily autonomous Companion limit | Maximum 5 admitted appearances per local calendar day; manual opens do not consume the autonomous quota |
| Quiet hours | No restriction for this Companion appearance policy |
| Windows lock | Suppress and do not count as an appearance |
| Do Not Disturb | Suppress and do not count as an appearance |
| Manual hide | Set a durable latch; block autonomous reopening until an explicit reset action |
| Receipts | Record proposed, suppressed/denied, window-created, visible, animation-started/completed/cancelled, capture-authorized/captured/failed, execution-dispatched/verified/uncertain separately |

Quota enforcement is a durable broker state machine. In one transaction it
reserves a slot before window creation, keyed by idempotency identity, and counts
`RESERVED`, `VISIBLE`, and `UNCERTAIN` slots so concurrent requests cannot
oversubscribe. A renderer/OS acknowledgment bound to window, session, host, and
broker generation moves it to `VISIBLE`; window creation alone does not. A
failure proven before possible visibility moves it to `RELEASED`. A crash,
timeout, or ambiguous result after creation moves it to `UNCERTAIN` and consumes
quota until reconciliation proves visibility or no effect. Duplicates return
the existing reservation and receipt rather than consume another slot.

The broker reloads and reconciles reservations after restart. Date boundaries
use configured local timezone, last accepted wall-clock boundary, and persisted
monotonic/boot evidence. Clock rollback cannot replenish quota or release
uncertain reservations; forward jumps and timezone changes require auditable
boundary transitions. Suppression proven before reservation consumes no quota.
User-initiated manual opens do not use autonomous quota. Policy and manual-hide
reset are authenticated Platform setting mutations, not renderer callbacks.

### 9.3 Truthful receipts

A window creation call is not proof the window became visible. An animation
request is not a rendered frame. A capture permission is not a captured image.
An execution request is not an effect. Receipts therefore require distinct
producer identities and stages, bind the exact window/animation/capture/action
ID, include host/session/generation and timestamps, and cannot be upgraded by
the Core or UI client.

### 9.4 Independent applications

- **Tray:** connection/health/STOP projection and explicit launch commands;
  never a state or authority owner.
- **Companion:** separately startable, lightweight presentation window; broker
  can create or hide it under policy; it consumes expression and animation
  contracts only.
- **Workbench:** an authenticated user launch is direct. A Core proposal must
  obtain explicit permission for that opening. Protected operations inside it
  still pass SAFE; opening permission grants no action authority.

## 10. Tauri versus Slint

**Decision: Tauri 2 for the initial accepted UI family.**

| Criterion | Tauri 2 | Slint | Decision consequence |
|---|---|---|---|
| Multi-window, tray, deep links, notifications | Mature application-shell fit | Possible, more platform glue | Tauri reduces custom OS lifecycle code |
| Rich Workbench forms, text, tables, accessibility | Web ecosystem is stronger | Native declarative UI is capable but requires more bespoke widgets | Workbench drives the choice |
| Companion animation | Canvas/WebGL/CSS or embedded renderer adapter | Strong lightweight native rendering | Tauri is sufficient initially; benchmark actual idle memory/GPU |
| Shared UI across Windows/Linux | Strong | Strong | Tie |
| Security model | Explicit command allowlist and CSP, but WebView attack surface | Smaller web attack surface | Tauri requires strict IPC allowlist, no remote navigation, CSP, signed assets |
| Existing team/repository code | No current Rust/UI framework | No current Rust/UI framework | Neither has migration advantage |
| One policy owner | Natural with a Rust broker and thin windows | Also possible | Framework must not own policy either way |

Slint may be evaluated later for a Companion renderer only if measured Tauri
idle memory, startup, transparency, input-region, or animation behavior misses
an approved threshold. That experiment must retain the same broker protocol and
must not create a second policy or receipt owner.

## 11. Proposed Rust workspace

```text
rust/
  Cargo.toml                       # workspace only
  rust-toolchain.toml              # exact reviewed channel
  deny.toml                        # license/advisory/source policy
  crates/
    sofia-contracts/               # generated + hand-reviewed invariants
    sofia-contract-fixtures/       # golden/counterexample corpus
    sofia-platform-client/         # authenticated local client
    sofia-core-link/               # Core Link client/server transport adapters
    sofia-fleet-transport/         # pinned mTLS transport, no policy ownership
    sofia-component-supervisor/    # process/service generation lifecycle
    sofia-config-broker/           # typed saved/effective config APIs
    sofia-ui-broker/               # presence/window/perception policy owner
    sofia-platform-service/        # composition root; no Cognitive Core
    sofia-windows-service/         # SCM adapter
    sofia-systemd-service/         # systemd adapter
  apps/
    sofia-tray/                    # Tauri application
    sofia-companion/               # independent Tauri application
    sofia-workbench/               # Tauri application
contracts/
  schemas/
  fixtures/
  compatibility.toml
```

Crate boundaries are compile-time dependency rules, not new runtime owners.
`sofia-contracts` must contain no credentials, state backend, identity seed, or
Sofía-specific personality asset.

## 12. Security and failure-mode analysis

| Failure or threat | Required response |
|---|---|
| Rust/Python contract divergence | Fail negotiation; no state/effect dispatch; preserve fallback |
| Oversized/malformed message | Reject before TLS or worker I/O where possible; bounded diagnostic |
| Stale component generation | Deny and require fresh endpoint observation |
| Duplicate request after timeout | Return/reconcile by idempotency key; never blindly re-execute uncertain effects |
| Rust supervisor crash | OS restarts supervisor; durable STOP and lease/generation prevent resurrection or stale control |
| Python Core crash | Platform remains; Core unavailable is truthful; drain/restart under existing policy |
| UI broker crash | Windows close; manual-hide/quota state survives; no autonomous reopen until policy reevaluation |
| UI client compromise | Client has no DB, signing key, SAFE authority, or raw secret; broker validates every command |
| WebView/navigation injection | Packaged local assets only, strict CSP, no remote navigation, minimal Tauri command allowlist |
| Lock/DND signal unavailable | Fail closed for autonomous appearance; manual launch remains available if authenticated |
| Clock rollback | Do not replenish daily quota; retain last accepted local date and monotonic evidence |
| False visible/rendered receipt | Require OS/window/render-loop producer acknowledgement; preserve requested versus observed stages |
| Capture consent race | Bind grant to selected target, session, expiry, broker generation, and one capture; recheck before pixels |
| Core Link partition | Show disconnected; preserve draft/history references; no identity or endpoint substitution |
| mTLS revocation | Terminate transport and invalidate session; never fall back to unauthenticated HTTP |
| Split writer | External generation/writer fence denies second writer; Rust does not open canonical DB outside owner API |
| State migration corruption | Keep Python owner and rollback; port only after dual-read comparison and independent review |
| Secret leakage | Exchange opaque secret references; use OS-protected broker; redact diagnostics |
| Update ABI mismatch | Dependency graph expands restart scope truthfully; do not hot-swap incompatible binaries |

High-risk migrations—canonical state internals, SAFE cryptography, trust roots,
secret storage, release signing, and writer promotion—are deliberately late and
require separate threat models. Rust memory safety alone is not evidence of
semantic equivalence or authorization safety.

## 13. Independent phases and PR boundaries

Each numbered item is a separate reviewable PR unless explicitly split further.

### Phase 0 — protect current GO LIVE work

1. Land or rebase around G7-A, audit-fix PRs, and remaining G2 changes.
2. Record exact baseline contracts and owners; no Rust code.
3. Define measurable budgets for UI startup, idle RAM/CPU/GPU, transport latency,
   supervisor recovery, and compatibility duration.

**Exit:** current release work has an explicit non-interference decision.

### Phase 1 — contract corpus and Rust skeleton

1. Add schemas, golden fixtures, Rust workspace, pinned toolchain, format/lint,
   dependency policy, SBOM, and reproducible build metadata.
2. Implement `sofia-contracts` without transport or effects.
3. Run bidirectional Python/Rust conformance and fuzz/property tests.

**Rollback:** remove Rust artifacts; Python behavior is untouched.

**Proposed first implementation PR scope:** add only the pinned Rust workspace,
`sofia-contracts`, language-neutral schemas, reviewed types, canonical positive
and negative fixtures, compatibility manifest, build metadata, SBOM/dependency
policy, and Python↔Rust codec/validator harness. Owner authentication is an
opaque typed evidence reference and policy requirement; the PR does not choose,
implement, or bypass owner-secret or FIDO2. It contains no UI, transport,
service/process manager, database access, SAFE decision, STOP writer, capture,
state mutation, installer activation, or production feature flag.

**Phase 1 test matrix:** Windows and Linux; pinned stable Rust; supported Python
versions in current CI; debug/release; fmt, clippy, unit/doc, dependency/license/
advisory checks; bidirectional golden round trips; unknown versions/fields,
malformed encoding, duplicate keys, bounds, oversized payloads, digest mismatch,
deadline/timezone, identity/audience/generation/idempotency confusion; previous
minor acceptance and next-major rejection; deterministic property/fuzz seeds;
Core-asset/secret absence, reproducible digest, and exact-SHA provenance.

### Phase 2 — read-only Core Link client

1. Implement Rust status and conversation-read client against the existing
   Python Core Link server and binding store abstraction.
2. Add pinned mTLS, revocation, wrong identity/generation, payload bounds, and
   offline tests.
3. No settings mutation, conversation send, or module execution initially.

**Rollback:** launch Python Core Link desktop/tray.

### Phase 3 — UI broker plus tray

1. Introduce broker schemas and a Python reference implementation/test oracle.
2. Implement Rust broker read-only health and tray app.
3. Add local authenticated IPC, single-instance behavior, lock/DND observation,
   redacted diagnostics, and truthful window receipts.

**Rollback:** stop Rust tray/broker and restore Python tray startup entry.

### Phase 4 — independent Companion

1. Implement the approved five-per-day, lock/DND, no-quiet-hours, and manual-hide
   policy in the broker.
2. Add Companion renderer consuming typed expression intents.
3. Preserve Python avatar/Desktop paths and compare receipts side by side.

**Rollback:** disable Rust Companion feature flag; broker cannot remove fallback.

### Phase 5 — Workbench

1. Implement explicit ask-before-open flow.
2. Add conversation, status, settings, Fleet/module, and receipt projections in
   slices; never port direct SQLite panels.
3. Add approved mutations only through existing SAFE/RUN/config APIs.

**Rollback:** switch launcher selection to Python desktop/settings.

### Phase 6 — supervision and service management

1. Port process/service observation, generation fencing, heartbeat, drain,
   bounded stop, watchdog lease, Windows SCM, and systemd adapters.
2. Retain Python supervisor behind a mutually exclusive feature/config flag.
3. Prove crash-before/after-ready, stale supervisor, durable STOP, DB-not-ready,
   frozen child, update, and rollback behavior.

**Rollback:** stop Rust service and restore Python service definition without
changing writer generation or state.

### Phase 7 — configuration broker

1. Port schema validation and saved/effective revision APIs.
2. Keep secret values behind the current secret owner; Rust receives references.
3. Prove live/next-operation/restart semantics and transaction compensation.

### Phase 8 — Core Link and Fleet transport service

1. Replace Python client transport only after cross-language parity.
2. Port server transport adapters without moving conversation semantics.
3. Reuse enrolled identities, pinned mTLS, endpoint policy, revocation, and
   existing Venus/Artemis topology.

### Phase 9 — reviewed security/state slices

Candidates: canonical file/path checks, atomic noncanonical files, bounded state
projection codec, content-free metrics. Excluded by default: canonical schema
ownership, writer promotion, Constitution activation, approval signing, secret
roots, and protected migration. Each candidate requires an ADR, independent
security review, shadow comparison, crash injection, and rollback.

### Phase 10 — replacement acceptance

1. Run installed-artifact Windows/Debian RCs with both fallback and Rust modes.
2. Require owner-visible G8 trials on disposable state and real Venus/Artemis.
3. Remove a Python fallback only in a later PR after an explicit acceptance and
   rollback-retention decision.

## 14. Acceptance tests and CI

### Required on every Rust PR

- `cargo fmt --check`, `clippy -D warnings`, unit/doc tests;
- locked dependencies, `cargo deny` advisories/licenses/sources, SBOM;
- Windows and Linux stable Rust, release and debug profiles;
- Python/Rust golden contract corpus and negative corpus;
- deterministic fuzz/property seeds for codecs and policy state machines;
- no Core assets, Constitution, memory, or secret values in Rust Platform/UI
  artifacts;
- provenance/attestation bound to repository, workflow, commit, and digest.

### Boundary suites

| Boundary | Minimum acceptance |
|---|---|
| Core Link | pinned mTLS; wrong CA/host/Core/generation; revocation; deadline; duplicate; oversized; partition/reconnect; history continuity |
| UI broker | atomic 0–5 reservations; concurrent sixth denied; visible acknowledgment; proven-before-effect release; uncertainty reconciliation; duplicate idempotency; restart/date/timezone/clock rollback; manual-hide latch/reset; lock/DND suppression; no quiet-hours gate |
| Workbench | direct user launch; explicit permission for Core-initiated launch; denial; stale answer; broker restart; no direct SAFE/state access; opening grants no protected action |
| Screen | Python exact-window backend remains oracle; no pixels before exact consent; target/session/expiry binding; one-use; cancel; lock; truthful receipt; UI cannot synthesize capture |
| Receipts | request is not visible/rendered/captured/executed; forged/stale/wrong-host/wrong-generation receipts denied |
| Supervision | durable STOP; service stop distinction; stale supervisor cannot kill new generation; frozen/crashed child; DB readiness; bounded shutdown |
| Configuration | schema parity; invalid/unknown field; saved/effective revision; secret reference; compensation; concurrent update |
| State | single writer; compare-and-set; audience/principal scope; crash atomicity; restore and old-writer denial |
| Packaging | Core-free `CORE_LINK + MODULE_HOST`; separately installed Python Core; signed artifacts; upgrade/rollback; Python UI fallback |

### CI integration policy

Do not add Rust jobs to all historical workflows immediately. Start with a
dedicated required compatibility workflow, then add Rust-mode legs to G2/G4/G5
and RC workflows at phase exits. Package matrix selection must make Rust crates
visible without turning optional UI work into a blocker before its declared
gate. Exact-SHA Windows and Debian installed-artifact RCs remain final evidence.

### Rust acceptance gate separation

Rust uses separate gates: **R0** plan approval, **R1** contract conformance,
**R2** read-only client, **R3** broker/tray, **R4** Companion, **R5** Workbench,
**R6** Platform service/transport slices, and **R7** replacement acceptance.
They do not close, replace, or block G0–G7/G7-A or G8 while Rust is outside the
candidate. Once a release explicitly includes a Rust slice, that exact artifact
must repeat every affected GO LIVE gate and later physical G8 case. Historical
Python acceptance cannot certify Rust; Rust planning cannot claim existing items.

## 15. Rollback strategy

1. Every Rust slice ships disabled or side-by-side first.
2. Launcher/service configuration selects one owner per function and records
   the selected implementation and generation.
3. Preserve Python binaries, configuration readers, and UI entrypoints for at
   least one accepted release after Rust promotion.
4. Rollback changes implementation selection, not canonical state or identity.
5. Apply durable STOP before supervisor/transport/state-owner transitions.
6. Drain in-flight work and reconcile uncertain effects before switching.
7. Verify writer generation, binding identity, schema, and artifact digest.
8. Restore the prior signed selection atomically and invalidate stale sessions.
9. Verify conversation, STOP, SAFE, RUN, state, and UI health before resuming.
10. Preserve failure evidence; never erase receipts to simulate success.

If a Rust release needs a state schema that the Python fallback cannot read,
the release is not rollback-safe and must not be promoted without a separately
approved dual-version migration strategy.

## 16. GO LIVE, G8, and Constitution 2.0 impact

### Issue #120

- **OBSERVED:** #120 requires Core/Platform separation, one canonical writer,
  minimum operation independent of optional modules, and exact-SHA release
  evidence.
- **INFERRED:** contract/schema work can help remaining G2 and G4, but an initial
  Rust rewrite would delay higher-priority G7-A and audit fixes.
- **Decision:** only Phase 1 contract work may run opportunistically before the
  current blockers close. Rust UI and service replacement are post-shakedown
  candidates unless they directly close an already-open requirement without
  expanding risk.
- No Rust plan item closes a checklist entry by design alone.
- R-gates remain separate from #120 until an owner-reviewed release candidate
  explicitly includes the corresponding Rust slice.

### Issue #129 / G8

- **OBSERVED:** G8 remains NOT STARTED/NO PRODUCTION GO with 16 physical criteria.
- Rust replacement adds Windows/Linux UI, service, reconnect, rollback, mTLS,
  resource, and real-render/capture acceptance cases; it removes none.
- Until a candidate includes Rust, these are R-gate tests and do not alter the
  16 deferred G8 items.
- Real Venus lock/DND behavior, transparent Companion behavior, notification
  area, display scaling, GPU contention, capture picker, sleep/reboot, and
  Venus-to-Artemis continuity remain G8 evidence.

### Inactive Constitution 2.0 proposal

- **OBSERVED:** the proposal is inactive and its amendment ceremony is deferred.
- The hybrid design is compatible with technology independence, one identity,
  one canonical writer, Core/Platform separation, goals-not-grants, truthful
  receipts, bounded initiative, STOP, and neutral shared infrastructure.
- Generic Rust SDK/Platform crates must not default to Sofía's identity,
  personality, Constitution, memory, administrators, credentials, or lineage.
- Display names cannot key routes, authorization, state, projection, or caches;
  stable Core/principal IDs and lineage/digest must.
- UI presence is expression and operation, not identity or authority. The broker
  enforces permission and receipts; Core retains voluntary expression.
- **UNKNOWN:** Constitution 2.0 exact bytes have no final owner approval,
  protected activation, installed artifact, or G8 acceptance. No Rust phase may
  activate it or change the active trusted hash.

## 17. Unresolved decisions and dependencies

1. Resolve the observed owner-secret/FIDO2/CLI test-contract mismatch and obtain
   green exact-SHA package, Manual, and installed-wheel RC evidence. Decide which
   protected actions require physical FIDO2 versus another fresh owner secret.
   Preserve one-use exact-action binding, SAFE, and STOP; Rust only consumes the
   reconciled contract.
2. **UNKNOWN:** final disposition and merge order for draft PRs #122–#128/#133.
3. Define the local authenticated IPC transport for Rust clients: named pipe on
   Windows, Unix domain socket on Linux, peer credential verification, and
   message-level identity binding.
4. Approve canonical schema tooling and generated-code review policy.
5. Set measured Tauri memory/GPU/startup thresholds and the Slint fallback
   evaluation trigger.
6. Define the authoritative Windows DND API and fail-closed behavior when its
   status is unavailable on supported OS versions.
7. Define exact manual-hide reset UX and authenticated command scope.
8. Define UI broker durable namespace and retention without adding a database.
9. Complete current G2 separation so the Rust Platform does not inherit a false
   claim of already isolated Python composition.
10. Obtain independent security review before porting SAFE, secrets, signing,
    canonical state, or writer fencing internals.
11. Decide supported Rust MSRV/toolchain, WebView2 deployment policy, Linux WebKit
    packaging, code signing, updater, and offline dependency strategy.
12. Establish signed cross-language compatibility manifests and deprecation
    duration before any protocol version is retired.

## 18. Follow-up discrepancy closure

| Required correction | Closure | Remaining evidence |
|---|---|---|
| Capture described as absent | Corrected to the one-shot exact-window service, Windows backend, CLI composition, local assumptions, and UI gap | Live Windows, physical authentication, display/focus edges, integrated UI |
| CI snapshot incomplete | Added completed run links; seven package failures reduce to shared auth test-contract mismatches; RC/Manual failures recorded | RC diagnostic logs needed before common cause is OBSERVED |
| Quota transaction semantics absent | Added reservation, acknowledgment, release, uncertainty, concurrency, restart, and clock rules | Durable namespace and OS visibility probe |
| Workbench always asked | Direct user launch is direct; Core opening requires explicit permission | Authenticated prompt/receipt UX |
| Rust/release gates conflated | Added R0–R7 and explicit candidate-inclusion rule | Future release scope decision |
| Owner authentication implicit | Added owner-secret/FIDO2 reconciliation dependency without changing SAFE/STOP | Security decision and green evidence |

## 19. Recommendation

Approve the architecture direction and Phase 1 only after current GO LIVE work
has an explicit scheduling boundary. The first implementation PR should contain
only the Rust workspace, canonical fixtures, generated contract types, and
cross-language conformance tests. It should contain no UI, service manager,
database access, SAFE logic, or production activation.

Promotion order should be: contracts → read-only Core Link → UI broker/tray →
Companion → Workbench → supervision/service adapters → configuration → transport
→ individually reviewed security/state slices. Each promotion keeps the Python
fallback and one authoritative owner until exact-SHA acceptance proves the
replacement.
