# MENTOR on the Actual Windows Service (LocalSystem)

**Source created:** October 19, 2026. **Host status:** not yet verified after deploy. **Security:** only two optional service settings, read by the existing Sofía Windows service; no new service, database writer, account, master key or background inference process.

## Evidence from Venus

The owner confirmed:
- `SofiaAdaLyra` Windows service is **Running** as **LocalSystem**.
- Ollama `qwen3:14b` version 0.40.6 passed the synthetic `behavior-smoke` with provisional personality and emotion grades and `runtime_turn_tested:false`.
- The developer PowerShell process has valid `SOFIA_MENTOR_BEHAVIOR_ENABLED=true` and `SOFIA_MENTOR_SOURCE_ROOT`.
- `behavior-status` in that **interactive Windows account** shows zero completed saved reviews.
- None of these proves the current service process has started a MENTOR observer. The service may launch a separately installed, *version-pinned active-release child*. Pulling GitHub `main` into a developer checkout does **not** necessarily deploy a new wheel or make a running Windows service reload Python modules.

## MENTOR service setting contract

The stable `SofiaRuntimeWindowsService.SvcDoRun()` reads two existing pywin32 service custom options on boot:

- `MentorBehaviorEnabled`: boolean string `true` or `false`, default false.
- `MentorSourceRoot`: absolute existing local checkout containing `src/sofia/personality/personality.json` and the MENTOR monitor module.

When enabled, the service host sets the **two allowlisted** `SOFIA_MENTOR_BEHAVIOR_ENABLED` / `SOFIA_MENTOR_SOURCE_ROOT` environment variables in its own process before entering bootstrap or active-release execution. An active-release child inherits this restricted process setting, subject to the active release actually containing the newer MENTOR code. Invalid optional config is ignored with MENTOR disabled; do not affect canonical state or startup. No existing `StatePath`, credentials, principal or FIDO2 policy is changed. This option remains inert until the service host starts with a code version that implements it.

### 1. Non-mutating preflight on Venus

Use the repository's existing virtual environment:

```powershell
git pull --ff-only
python -m sofia.mentor behavior-service --action status
python -m sofia.mentor behavior-service --action plan --source-root .
Get-CimInstance Win32_Service -Filter "Name='SofiaAdaLyra'" |
    Select-Object Name, State, StartName, PathName, ProcessId
```

- `status` reads the pywin32 custom options; it does **not** read the running process's actual environment.
- `plan` checks that the developer checkout exists with a profile and MENTOR source code and prints what a future setting change would target. It does **not** write to the service.
- Windows SCM service and process details are read-only. Do not paste sensitive local usernames, exact file paths, private IP addresses or process command-line secrets into a public report.
- `running_release_has_monitor_code: unknown` is the truthful status until the actual verified installed release is checked.

### 2. Deployment requirements (do not skip)

Before enabling:
1. Confirm the installed stable service host includes `sofia.mentor.windows_service_settings` and the two-option read in `runtime_service.SvcDoRun`. A simple Git pull does not hot-reload an installed Windows service.
2. If active-release mode is in use, confirm the **already approved and activated release** contains `behavior_monitor.py`, `behavior_history.py`, the final-answer hook, idle-coordinator registration, and `SOFIA_MENTOR_SOURCE_ROOT` handling. Use the existing PKG-RUN release verification/deployment process. Do not mutate the canonical release record, invent an active-release ID, or replace the writer to test.
3. Confirm LocalSystem may read the target personality checkout and contact the local loopback Ollama `127.0.0.1:11434`; do not modify Ollama authentication or LAN exposure.
4. Ensure the active machine isn't gaming and all owner STOP/authority controls remain effective.

### 3. Explicit opt-in (only when deployment prerequisites are satisfied)

From an owner-authorized **elevated PowerShell** session:

```powershell
python -m sofia.mentor behavior-service --action enable --source-root . --approve-scm-change
python -m sofia.mentor behavior-service --action status
```

This updates only two optional `SofiaAdaLyra` service custom options and reports `configured_not_restarted`. It does **not** restart services. It does not change service account, startup mode, canonical database ownership or production credentials. Allow settings to take effect through a separately approved, normal service deployment/restart once the active code/release has been verified. Never start a second Sofía instance.

To disable on the next approved restart without changing other options:

```powershell
python -m sofia.mentor behavior-service --action disable --approve-scm-change
```

## Confirm actual behavior

After an approved deployment, service restart, and one consented real conversation:

1. Wait until the foreground host is known idle/normal and conversation idle for at least five minutes. The pending RAM queue expires after 20 minutes at the next admitted check; idle conditions can defer processing.
2. The Windows service running as LocalSystem writes its **own** numeric-only score file. An interactive developer account's `behavior-status` may continue showing zero even while the service records reviews successfully.
3. Obtain `SofiaApplication.mentor_behavior_snapshot` using a **supported authenticated diagnostic**. The property is not yet automatically presented in the tray; do not expose a new unauthenticated debug endpoint.
4. If authorized and needed, inspect the LocalSystem account's local scores using existing Windows administration. Do not move private raw conversations or canonical state databases. Never infer the account's exact home folder from the developer shell.
5. Confirm `reviewed_turns > 0` for the actual service account, zero automatic commands, no public chat/affect uploads, and no load on the GPU during gaming.
6. Independently inspect whether the critic's grades align with real responses; the modeled emotional state does not mean Sofía is sentient or that a real avatar/voice animation was observed.

## Diagnostic map

| Symptom | Next grounded check |
|---|---|
| Smoke test passes but service score count zero | Service code/release, SCM settings, LocalSystem score-account path |
| Settings show true but monitor not attached | Service not restarted, active release missing module, background coordinator activation |
| Pending turns, none reviewed | Known idle/activity gate, conversation idle clock, RAM queue TTL, GPU availability |
| Reviews fail with invalid rubric | Model-output safe failure code, installed Qwen and Ollama versions |
| Reviewer returns 4/4 for expression delivery | Treat as unverified until actual authenticated voice/avatar receipt |
| Disabled/unconfigured | Leave service fully operational; monitoring is optional |

This feature is a strictly observational tool and cannot authorize repairs or change personality, memory, protected owner controls, FIDO2, or canonical application behavior.

## Owner host check: access denied during status + UNC development checkout

An owner run on Venus established:

- `SofiaAdaLyra` is **Running**, principal **LocalSystem**, installed service executable `C:\\Program Files\\SofiaAdaLyra\\Python313\\pythonservice.exe`; the installed host module/release code version was **not** independently verified.
- `behavior-service --action status` originally failed with `pywintypes.error: (5, 'RegCreateKey', 'Access is denied.')`.
- `behavior-service --action plan --source-root .` originally accepted a path resolved to a `\\\\Artemis\\Hestia\\...` **UNC share**, even though it was accessed as an `H:` drive from the owner's interactive shell.
- The earlier synthetic local `behavior-smoke` already **passed** using Qwen3 14B. No evidence of a real production Sofía turn being scored exists yet.

**Cause of the access-denied error:** pywin32's `GetServiceCustomOption` uses `RegCreateKey` even for reads, requesting write/create privilege. This is inappropriate for a read-only status command under a non-elevated account. See [pywin32's current implementation](https://github.com/mhammond/pywin32/blob/main/win32/Lib/win32serviceutil.py).

**Fix in `main`:** `behavior-service --action status` now uses the read-only standard-library `winreg.OpenKey` with `KEY_QUERY_VALUE` on `HKLM\\SYSTEM\\CurrentControlSet\\Services\\SofiaAdaLyra\\Parameters`. Missing optional settings are treated as **disabled** without creating registry keys. If the registry ACL denies even read access, the command reports a sanitized permission error, not a Python traceback containing registry details.

**Source-root correction:** `--action plan` and `--action enable` reject UNC shares and network-mapped drives for the LocalSystem service. LocalSystem does not inherit the owner's mapped drives and may be unable to access or authenticate to their SMB shares. **Never grant broad share rights to LocalSystem to work around this.** This does not change the source location of Sofía's existing canonical database, and it must not trigger moving that database.

### Updated owner preflight (no admin/restart required)

```powershell
git pull --ff-only
python -m sofia.mentor behavior-service --action status
python -m sofia.mentor behavior-service --action plan --source-root .
```

The **second command is expected to refuse your currently network-backed checkout** with a safe error about needing a local source root. That's intentional. Do **not** enable MENTOR against `\\\\Artemis\\Hestia` or the mapped `H:` path.

Before attempting any activation, ensure an owner-approved **locally installed, version-verified checkout or release** exists on Venus, with a complete readable Sofía personality profile and MENTOR module. Its filesystem path should be local and accessible to the actual service identity. Use that path instead of `.` in the `plan` command. Do not copy private `sofia.db`, credentials, or production secrets into a new Git directory, and do not silently update the active release.

**Next deployment evidence still missing:** Which installed module the `pythonservice.exe` host loads; whether Sofía is running an active-release child from the release-runtime directory; whether that release includes the optional MENTOR hook; and whether the LocalSystem process can reach the chosen local profile directory and Ollama. Neither an SCM service executable path nor an interactive git revision answers these questions.

Service-setting updates remain separately owner-approved and do not restart anything. Never install/start a second canonical runtime.
