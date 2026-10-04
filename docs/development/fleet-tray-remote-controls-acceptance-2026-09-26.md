> Cleanup update: unwired `ui.delivery`, headless `ui.workbench`, remote-chat transport/endpoint/authority and Fleet tray-control prototypes were retired. The desktop and tray remain live; remote-chat settings are accepted only for legacy normalization to local mode. Historical candidate descriptions below are not current wiring. See [UI cleanup report](ui-cleanup-report.md).

# Fleet / Windows tray / remote-client acceptance candidate

**Date:** 2026-09-26  
**Branch:** `feature/fleet-tray-remote-controls`  
**Status:** partial live acceptance on Venus. Tray icon/exit, single-instance ownership, Game Mode On/Off/Auto, Windows startup, Open Sofía, and service-control safety/cancel behavior have passed supervised canaries. Destructive runtime restart/stop remains deferred by Sparks. Remote chat and real Fleet-node deployment remain open.

## Scope

This branch combines four related control-plane slices:

1. **OPS Fleet activity and gaming protection**
   - durable activity observations and manual overrides;
   - Steam-library/local-process game detection;
   - gaming-aware workload placement;
   - cognition-facing OPS placement uses the same evidence.

2. **Fleet agent bootstrap policy**
   - ready / auto-install / ask-operator / reject decisions;
   - automatic installation only through a trusted bootstrap path with explicit or standing authority;
   - exact package/version/SHA-256 verification.

3. **Windows tray and Master Settings**
   - native notification-area process;
   - Open Sofía, Fleet status, Game Mode, LLM controls, runtime controls, settings and diagnostics;
   - separate runtime versus LLM lifecycle;
   - per-user Windows startup;
   - single-instance process lock.

4. **Remote desktop chat**
   - local mode remains supported;
   - pinned mutual-TLS thin client can use an already-running canonical conversation on another host;
   - durable request IDs prevent blind duplicate generation;
   - uncertain send/generation outcomes fail closed rather than retrying automatically;
   - automatic Fleet-authority endpoint publication remains a RUN/OPS integration gate.

## Focused Windows pytest gate

From the repository root:

```powershell
python -m pytest -q `
  test/test_ops_activity.py `
  test/test_ops_activity_capability.py `
  test/test_ops_bootstrap.py `
  test/test_ops_waves3_5_acceptance.py `
  test/test_ui_control_center.py `
  test/test_ui_settings_game_mode.py `
  test/test_ui_remote_client.py `
  test/test_ui_remote_transport.py `
  test/test_ui_remote_pin_validation.py `
  test/test_ui_remote_application.py `
  test/test_ui_service_control.py `
  test/test_ui_windows_tray.py `
  test/test_ui_windows_startup.py `
  test/test_ui_process_lock.py `
  test/test_ui_tray_game_observation.py `
  test/test_ollama_unload.py `
  test/test_ui_desktop_worker.py `
  test/test_ui_desktop.py `
  test/test_ui_application.py
```

Do not record acceptance from test counts produced on another revision.

## Supervised Windows tray canary

First inspect the actual local service names before exercising start/stop controls:

```powershell
Get-Service | Where-Object {
    $_.Name -match 'Sofia|Ollama' -or
    $_.DisplayName -match 'Sofia|Ollama'
} | Format-Table Name,DisplayName,Status,StartType -AutoSize
```

Launch the tray agent in the foreground for the first canary:

```powershell
python -m sofia.ui.tray_agent
```

Verify:

- exactly one Sofía icon appears in the Windows notification area/hidden icons;
- a second launch is refused by the lifetime lock rather than creating a duplicate icon;
- double-click opens the Sofía chat;
- right-click shows Fleet status, Game Mode, LLM Engine, Sofía Runtime, Settings, Diagnostics and Exit;
- runtime service state reflects the real Windows service;
- LLM state is not assumed healthy when the configured service does not exist;
- exiting the tray removes the icon cleanly.

## Game Mode canary

Use the tray to test all three states.

### Manual On

Set **Game Mode → On** and verify the durable OPS override is `gaming`.

### Manual Off

Set **Game Mode → Off** and verify the durable OPS override is `normal`.

### Auto

Set **Game Mode → Auto**.

Start a Steam-library game or a configured executable from `SOFIA_GAME_EXECUTABLES`. Allow the tray sampling interval to run and verify OPS records `gaming`. Exit the game and verify a later sample returns to `normal`.

The initial detector uses local process evidence. Steam Web API access is not required.

## Master Settings canary

Launch directly if desired:

```powershell
python -m sofia.ui.settings_window
```

Verify:

- the master section tabs render;
- Game Mode changes also update the OPS override, not merely UI settings;
- Windows startup enable/disable updates only the current user's Run entry;
- runtime and LLM service names are independently configurable;
- pinned remote mode refuses an empty endpoint.

## LLM/runtime control canary

Do **not** click stop/restart until the configured Windows service names have been verified.

Prove separately:

- Sofía runtime restart targets only the configured Sofía service;
- LLM restart targets only the configured LLM service;
- **Unload model** unloads the configured Ollama model while leaving the Ollama service alive.

If Ollama is not installed as a Windows service, service start/stop/restart is expected to report `not_found` until a correct service target or a process/service adapter is configured. Model unload can still use the Ollama API when it is reachable.

## Remote chat gates

The transport/client source exists on this branch, but a full live remote-chat claim still requires:

1. server and client certificates under the approved CA;
2. mutual TLS;
3. exact client and server public-key SHA-256 pins;
4. the remote-chat server hosted beside the already-running authoritative conversation;
5. a desktop client configured for the pinned endpoint;
6. history retrieval and one successful response;
7. wrong certificate / wrong pin / revoked client denial;
8. interrupted-send test producing `outcome_unknown` with no automatic duplicate generation;
9. later replacement of the temporary `SOFIA_REMOTE_CHAT_ENDPOINT` handoff with RUN/OPS authoritative endpoint publication;
10. reconnection after a supervised runtime move/failover.

## Acceptance boundary

Passing this gate supports merge of the source candidate. It does **not** prove:

- autonomous arbitrary LAN scanning;
- real agent installation on unprovisioned machines;
- real cross-host workload execution;
- automatic primary Sofía migration;
- production remote chat failover;
- multi-day RUN/Fleet soak.

Those remain live OPS/RUN/NET/SAFE/VERIFY gates.


## Fleet Live Node 1 — Artemis

The first real Fleet deployment is intentionally staged before Windows service
installation. Prove the authenticated foreground agent path first, then wrap
the same accepted agent in service supervision.

### Source candidate added

- Fleet agent accepts one JSON configuration file via
  `python -m sofia.distributed.agent_main --config <path>`;
- relative certificate/key/ledger paths resolve from the configuration file;
- existing environment-variable configuration remains supported;
- `--check-config` validates configuration without opening a listener;
- Venus-side `python -m sofia.distributed.fleet_probe` consumes existing
  durable node enrollment, exact endpoint approval and exact active grants;
- identity/capability probes use the existing pinned-mTLS transport;
- remote operations use `DurableRemoteControl` and the durable request ledger;
- Fleet agent advertises read-only `ops.telemetry/latest`;
- Windows telemetry reports CPU load, RAM used/total and aggregate free local
  disk bytes. Unsupported GPU/temperature values remain unknown.

### Local source gate

Run before touching Artemis:

```powershell
python -m pytest -q `
  test/test_distributed_agent_main.py `
  test/test_distributed_fleet_probe.py `
  test/test_ops_local_telemetry.py `
  test/test_distributed_agent_tools_telemetry.py `
  test/test_distributed_authorization.py `
  test/test_distributed_durable.py `
  test/test_distributed_endpoint_policy_durable.py `
  test/test_distributed_identity_durable.py
```

### Artemis live acceptance sequence

1. provision a Fleet CA, Artemis server certificate/key and Venus client
   certificate/key through an operator-controlled path;
2. choose a durable Artemis node UUID and write the Artemis agent JSON config;
3. validate with `--check-config`;
4. start the Artemis Fleet agent in the foreground;
5. on Venus, durably enroll the exact Artemis server certificate and approve
   the exact Artemis hostname/port;
6. authenticate and retrieve advertised capabilities with `fleet_probe`;
7. create only the read-only grants required for the canary;
8. invoke `system.inspect/system`, `system.inspect/hardware` and
   `ops.telemetry/latest`;
9. verify wrong pin/certificate and missing-grant attempts fail closed;
10. only after this gate passes, package the same agent as a supervised Windows
    startup/service unit.

No arbitrary shell, automatic LAN scanning, automatic install, workload
migration or runtime failover is implied by this milestone.
