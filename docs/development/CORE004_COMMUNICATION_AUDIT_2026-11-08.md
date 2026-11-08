# CORE-004 | Authenticated Core Link communication audit (Team 4)

Date: 2026-11-08  
Baseline main: `dd7020ce48c06e82684d3439779266de9ea965b4`  
Scope: disposable source/security work ONLY; no production activation, personal Discord delivery, Core writer migration, or merge.

## Evidence grades

- **S**: implemented source and a corresponding committed test, NOT a passed exact-head test.
- **D**: disposable runtime test with observed result and provenance (none newly executed for this audit).
- **I**: installed-host independent acceptance (none claimed).
- **G8**: accepted real-host G8 row (0/16; no promotion from source).
- **BLOCKED**: pending Team 1/2/3/5 or installed-environment evidence.

### Communication inventory

| Path | Production call site | Source grade | Missing acceptance |
| --- | --- | --- | --- |
| Python Core Link wire contract | `src/sofia/sdk/core_link.py` | S | cross-platform exact-head compatibility |
| mTLS service | `src/sofia/platform/core_link/transport.py`; `src/sofia/platform/application/bootstrap.py` server thread | S | installed Debian/Windows peer; cert and key ACL negatives |
| Authenticated gateway | `src/sofia/platform/core_link/conversation.py`; `access.py` | S | atomic revocation + generation/STOP admission; genuine Ollama answer |
| Remote desktop | `src/sofia/modules/ui/core_link_desktop.py`; `platform/launcher.py` | S | installed Windows startup, failed/reconnecting/ready state machine, clean window and tray shutdown |
| Local desktop / Discord attachment | `src/sofia/modules/ui/desktop_worker.py`; `modules/discord/live.py`; `modules/discord/discordpy.py` | S | runtime owner single-writer proof; safe remote Discord producer design |
| Durable Discord | `modules/discord/{binding,ingress,bridge,delivery,outbound,process_lock}.py` | S | production network reconnect, denied crossover, no duplicate sends |
| Rust Core Link R2 | `rust/crates/sofia-core-link`; draft PR #213 | S (read-only library/probe) | current-main reconciliation and installed integration; NOT a production send replacement |
| Android/mobile remote | `modules/mobile` and separate mobile transport | S (separate channel) | must not be counted as Core Link mTLS proof |

### Actual test inventory inspected on main

- `test/test_core_link_conversation.py`: tests for owner-approved enrollment, revocation, STOP, generation, durable idempotency, role-scoped history, loopback pinned mTLS, desktop send, oversized-frame rejection, post-handshake and post-request revocation.
- `test/test_core_link_binding.py`: private local registry CAS, quarantine, offline selection, symlink/junction, ACL model and revocation tests.
- `test/test_core_link_desktop.py`: uncertain turn reconciliation, invalid history denial, settings, local-only session state.
- `test/test_discord_live.py`: provisioned DM composition, bound session restart, revoked binding denial and background process lock.
- `test/test_platform_roles_and_launcher.py`: Core-free launcher role checks, with fresh-process Core import denial.
- These exist as source tests. This audit did NOT run them and cannot upgrade them to D or I.

### Defects / gaps

**CORE4-SEC-001: duplicate-key/non-finite wire ambiguity.** On main, Python mTLS handler/client used `json.loads` without duplicate-key rejection. This permits differently interpreted wire frames across implementations. Draft branch switches both Core Link inbound and outbound decoding to existing strict parser `sofia.sdk.cognition_json.loads_strict_model_json`, and adds disposable mTLS and client-response negatives in `test/test_core004_wire_security.py`. **Patch staged, not tested.** Verify no byte/body ceiling, TLS pin, or authorization regression before review.

**CORE4-SEC-002: server admission race.** `CoreLinkConversationGateway.dispatch` reauthenticates prior to `service.respond`, but code explicitly acknowledges no atomic lock/transaction spanning revocation, STOP and canonical turn admission. Need a host-owned serialized or transactional admission fence. Coordinate Team 1 (Core lifecycle), Team 3 (canonical principal/scope), Team 5 (independent concurrency tests).

**CORE4-INF-003: “ready” is not inference-ready.** Gateway status returns `state: "ready"` for authenticated, non-stopped gateway without separately proving provider-generated inference succeeds. Team 2 must specify honest readiness evidence. Do not add fake provider health claims or model fallback.

**CORE4-UI-004: incomplete connection-state UX.** Tk remote desktop currently presents “Connecting”, “Connected”, or “Disconnected: error” and has no observed autonomous reconnect cycle or separate terminal failure state. Add offline/reconnecting/ready/failed state model, retry backoff, explicit user cancellation and no stale response presentation.

**CORE4-XHOST-005: installed cross-host acceptance absent.** The main loopback end-to-end mTLS test configures `ProviderConfiguration(provider="test", model="test")`, not Ollama. It confirms real socket and application routing with a fake inference provider. No two-host Venus-like client / Debian Core evidence is claimed.

**CORE4-WIN-006: ACL model is not a Windows installed-token proof.** Unit tests model Windows DACL cases, while production validates Windows owner and DACL. Installed Windows current-user/admin/OWNER RIGHTS, inherited, foreign-reader, junction and effective-access negatives are still needed. Debian private-file/mTLS negative suite needs separate installed-host evidence.

**CORE4-DIS-007: avoid live Discord.** Desktop worker composes the Discord adapter around an existing canonical conversation; Discord process lock, binding and outbox state exist. Do not claim fresh Discord delivery or mutate owner DM. Explicit owner-run shakedown requires a separately approved window.

### New proposed tests

- `test/test_core004_wire_security.py`: ephemeral loopback mTLS host rejects duplicate top-level keys, nested duplicates and NaN without invoking Core; pinned client rejects duplicate-key response. Tests use temporary certificates, no live Core or Discord.
- `test/test_core004_real_inference_opt_in.py`: **skipped by default**; opt-in re-runs the existing real-socket/Core Link/Desktop test with `provider="ollama"` and a named installed model, with temporary `sofia.db`. The inference endpoint is restricted to loopback to prevent unexpected remote access. **Not run, not a real-host G8 acceptance.**

Safe source/test commands from a *disposable cloned worktree* on the proposal branch:

```bash
python -m pytest -q test/test_core004_wire_security.py test/test_core_link_conversation.py test/test_core_link_binding.py test/test_core_link_desktop.py test/test_platform_roles_and_launcher.py test/test_discord_live.py
python -m compileall -q src/sofia test
```

Only after disposable local Ollama availability, use the explicit optional real-inference test (NOT on production Core, and no personal state reuse):

```bash
export SOFIA_CORE004_REAL_INFERENCE=1
export SOFIA_CORE004_OLLAMA_MODEL='qwen3.5:9b'
export SOFIA_CORE004_OLLAMA_ENDPOINT='http://127.0.0.1:11434'
python -m pytest -q -s test/test_core004_real_inference_opt_in.py
```

The opt-in test's recorded output must include exact commit, model, temporary state path, timestamp and provider request/response evidence. A skipped test, stub response or merely a successful TLS handshake is **not** real inference proof.

### Acceptance matrix (no unobserved PASS)

| Scenario | Main test exists | Team 4 exact-head executed | Installed-host proven |
| --- | --- | --- | --- |
| Certificate identity / enroll / scope | Yes | NOT RUN | NO |
| Wrong key, wrong Core, generation | Partial | NOT RUN | NO |
| Expired / revoked / STOP | Yes | NOT RUN | NO |
| Duplicate / replay / uncertain resolution | Yes | NOT RUN | NO |
| Strict wire JSON (new) | New draft | NOT RUN | NO |
| Pinned loopback mTLS conversation | Yes, fake provider | NOT RUN | NO |
| Actual Ollama-generated answer | New opt-in harness | NOT RUN | NO |
| Desktop offline/reconnecting/failed | Partial | NOT RUN | NO |
| Discord DM route / one producer | Local tests | NOT RUN | NO |
| Two physical/VM hosts / restart / latency | No independent evidence | NOT RUN | NO |
| Native Windows ACL / Debian key tests | Partial models | NOT RUN | NO |

### Dependencies / explicit handoff

- **Core Team 1:** canonical worker and generation lifecycle, STOP, shutdown; coordinate atomic admission without duplicate writer.
- **Core Team 2:** real Ollama call and provider readiness proof; no fixture-only promotion.
- **Core Team 3:** audience, identity, principal and session continuity authorization.
- **Core Team 5:** installed-host and negative security certification, exact SHA and separate G8 acceptance.
- **Platform Team C:** status UX contract with existing Control Center; no shadow Platform authority or unapproved management actions.
- **Platform A/B/D/E:** deployed peer identity, signed package, Fleet/mTLS and installer/recovery QA as required; no production cutover.

### Three coordinator status graphs, preliminary planning only

Batch: C01 45, C02 50, C03 40, C04 30, C05 25, C06 35, C07 15.  
Maturity: runtime/inference 45, identity/cognition 55, memory 40, Core Link/mobility 30, safety/auth/recovery 35, channels 35, release QA 20.  
Overall Core engineering **40% (35–45% rough range)**, remaining 60%, existing G8 **0/16 accepted**.

No percentages are revised from planning baseline merely for proposed code or source-level tests. Release GO remains NO-GO.
