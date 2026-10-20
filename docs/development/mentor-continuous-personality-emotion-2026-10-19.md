# MENTOR Continuous Personality + Modeled Emotion QA

**Date:** 2026-10-19  
**Purpose:** Monitor Sofía's genuine completed replies for personality fidelity, conversational naturalness, and proportional emotional expression, without creating a second conversation system, exporting private user dialogue or blocking the user.
**Scope:** Source-wired, local-only, owner opt-in; physical Venus service acceptance must still be performed.

## Why the previous command failed

The original `personality-review --response-file "$env:TEMP\sofia_personality_sample.txt"` **does not create that file**. The file must exist, be regular and fit the input limit. The new always-on, opt-in production hook removes the need to manually prepare one response file for normal reviews.

## How MENTOR now attaches to real Sofía

1. The existing `EmotionalConversationService.respond()` produces and persists a settled response.
2. Its existing emotion appraisal, audience processing and expression decision complete first.
3. Only then does the optional `_mentor_behavior_monitor.observe()` hook receive the final answer, recent user turn, source-modeled emotional tone/active intensity and channel. **This happens after successful reply, not during generation.** A replayed canonical turn is never counted twice.
4. The hook is passive and quick. It queues at most **four** 3,500-character owner/private samples **in process memory only**. Overlarge turns are skipped, not truncated into misleading partial context. Pending samples older than twenty minutes are not eligible for review and are discarded at the next admitted review; memory is fully cleared when the process exits. A busy/game/unknown activity gate can delay that cleanup, so do not assume a precise 20-minute RAM destruction deadline.
5. The existing `ApplicationBackgroundCoordinator` admits at most one review each scheduled 300-second tick, only under known `normal` or `idle` activity and after a further 300 seconds of conversational idleness. It reuses the existing application worker, not a new timer or brain.
6. The local `qwen3:14b` reviewer uses Ollama `127.0.0.1:11434`, `think:false`, `tools:[]`, `keep_alive:0`, JSON output and bounded input/output. It is never given credentials, external model access or authority.
7. Its 14 dimensions are scored 0–4 with brief rationales and an uncertainty note: seven personality traits and seven natural-emotion dimensions. A missing genuine speech/avatar receipt is **unverified** (nullable coherence criterion), not a guessed match.
8. Raw conversation text and the critic's freeform reasons are discarded after the review. Only counts and numeric aggregates are written to an **outside-Git local** score cache. No `sofia.db` writes, no action execution, no automatic Git commit, no cloud upload.
9. Failures in MENTOR cannot change, retry or block Sofía's response. Owner is still the authority for protected actions. A critic's 4/4 does not prove good real behavior.

### Dimensions

**Personality:** factual grounding; skeptical reasoning; direct actionable answer; natural personality expression; respectful warmth; authority boundaries; correction/uncertainty.

**Emotion:** matches conversational context; continuity with actual modeled state; intensity and restraint; natural rather than performative tone; evidence-bound affect; appropriateness to seriousness; expression coherence (**unknown without real audio/avatar receipts**).

A subdued, serious answer can score highly. **Neither warmth, sass, fox banter, teasing, nor affection is compulsory**. Mechanical repetitions, invented emotion, inappropriate excitement, unsupported intimacy, or aggressive skepticism should be questioned. User affect inference is not mind-reading.

## Enable local QA on Venus

From an interactive **PowerShell process that starts Sofía itself**, set:

```powershell
git pull --ff-only
$env:SOFIA_MENTOR_BEHAVIOR_ENABLED = "true"
$env:SOFIA_MENTOR_SOURCE_ROOT = (Get-Location).Path
ollama list
```

Then start Sofía through the **existing supported launcher from the same environment**, not by starting a second canonical runtime. The bridge is installed by `SofiaApplication.start()`; it does not need a new `local-converse` command to record ordinary replies.

If Sofía is running as a Windows service, these interactive `$env:` values **will not automatically reach that existing service**. They must be configured in the service's supported deployment environment and applied via an owner-approved normal restart. Do not change the canonical database, service account, FIDO2 credentials, or host identity to test QA. On Debian/Artemis, use the existing service's environment override instead.

`SOFIA_MENTOR_SOURCE_ROOT` must point to the actual repository checkout containing `src/sofia/personality/personality.json`. Local model `qwen3:14b` must already be installed. No GPU reviewer call occurs until admitted by idle/activity gates. If host activity is UNKNOWN, busy, DND, or gaming, it refuses.

**Privacy:** Leave `SOFIA_MENTOR_BEHAVIOR_ENABLED` absent/false to disable monitoring entirely. When true, owner prompts and replies are briefly held **only in memory** and sent to a separately loaded local Ollama model on the same machine. Avoid enabling on shared/public machines without the appropriate participant consent.

### See results locally (no private text)

```powershell
python -m sofia.mentor behavior-status
```

On Windows, score-only totals are saved under `%LOCALAPPDATA%\Sofia\mentor\behavior_scores.json` for the service user account. On Linux, the default is `~/.local/state/Sofia/mentor/behavior_scores.json` or the XDG state directory. Each account has its own local score file. This file contains dimension sums/counts, no raw response, turn hashes, principal IDs, personal memory, individual timestamps or reviewer descriptions.

The running `SofiaApplication.mentor_behavior_snapshot` provides in-memory counts and the last scores for authorized UI integration; it never returns text of the queued conversation. It is currently a developer-facing property, not yet a separate visible dashboard in the tray.

## Operational evidence still required

- Boot the real Venus application with the opt-in enabled and confirm the observer attaches.
- Test one genuine authenticated desktop reply and one emotionally appropriate casual reply.
- After five minutes idle and non-gaming, confirm a nonzero local `behavior-status` count.
- Test gaming denial, busy and unknown activity, normal service restart and recovery.
- Compare critic ratings with real owner labels on balanced serious, technical, friendly and corrective prompts.
- Verify actual audio/2D avatar receipts separately; text-only evaluation never proves expression delivery.
- Confirm no raw dialogue enters the public Git outbox and no duplicate turn is reviewed on retry.

## Development references

- `src/sofia/mentor/behavior_monitor.py`, `behavior_history.py`
- `src/sofia/application/emotional_conversation.py` (settled-turn hook)
- `src/sofia/application/background_runtime.py` (existing idle coordinator)
- `src/sofia/application/bootstrap.py` (opt-in activation and snapshot)
- `test/test_mentor_behavior_monitor.py`, `test/test_mentor_behavior_history.py`, `test/test_emotional_conversation_mentor_hook.py`
- `.github/workflows/mentor-readonly-audit.yml` (automated regressions)

This is real runtime-wired source plus unit/CI evidence, not proof that the opt-in Windows service has yet been exercised on your machine.

## Zero reviews or all null grades: runtime troubleshooting

`behavior-status` reports numeric local history **for the account running the CLI**, not whether Sofía's running process has registered its monitor. `total_local_reviews: 0` is a valid, unscored state. A `null` expression-coherence score is expected until real audio/2D avatar delivery receipts can be verified, even if other rubric scores are available.

Run these commands from the checkout with the same venv:

```powershell
git pull --ff-only
python -m sofia.mentor behavior-diagnose --repo .
python -m sofia.mentor behavior-status
```

`behavior-diagnose` makes **no network request** and changes no configuration. It reports whether the current shell has the correct enable flag and source root, whether the chosen profile exists, and whether the current account has any saved reviews. Its `runtime_service_environment_verified` value is intentionally false: a separate Windows service cannot be diagnosed simply by reading the shell's environment.

To distinguish a local 14B critic failure from missing live integration, while Venus is idle and not gaming:

```powershell
python -m sofia.mentor behavior-smoke --repo . --mentor-model qwen3:14b --confirm-idle
```

This makes **one local Ollama model call** on a hardcoded **synthetic** question. It produces temporary numeric scores on screen only, **does not** increment the production review history, and does not establish that a real Sofía response was observed. If it fails, the issue is the model/format/local provider, not the running app's capture hook.

For a Windows Service Control Manager installation, use the actual service name `SofiaAdaLyra` (from `src/sofia/run/windows_service_spec.py`) to check **without restarting**:

```powershell
Get-CimInstance Win32_Service -Filter "Name='SofiaAdaLyra'" |
  Select-Object Name, State, StartName
```

The service may run under another account with a separate `%LOCALAPPDATA%` or released wheel and could lack the opt-in environment variable. Do not assume the developer shell's `$env:` is inherited by the service, or that `git pull` automatically updates a verified active release. Determine its actual startup environment and deployment version using your approved service-management workflow; only then make a supervised configuration change and normal restart. **Do not launch a competing second canonical Sofía instance.**

Normal live acceptance, with permission from conversation participants:
1. Enable the monitor in the *actual* application process, including an accessible source root, and start through existing deployment controls.
2. Have a genuine completed desktop/Discord conversation. Avoid sensitive content while testing optional local quality analysis.
3. Let the machine remain in a known `idle` or `normal` activity state and conversationally idle at least five minutes. Wait for the existing background coordinator to admit a review subject to STOP and budget.
4. Inspect `SofiaApplication.mentor_behavior_snapshot` through an authorized application diagnostic. `observed_turns`, `pending_private_turns`, `failed_reviews`, and `last_error_kind` distinguish capture, idle scheduling and critic issues.
5. Read the local history from the **same service account** (or through authorized administration) and confirm at least one `reviewed_turns` count; do not copy private runtime paths/IDs into public Git.

This diagnostic feature does not read the running service's memory, send screenshots, change production settings, or discover private transcripts.
