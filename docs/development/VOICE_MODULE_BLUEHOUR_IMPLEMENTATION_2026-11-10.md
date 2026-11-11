# Aegis Voice module: Sofia's selected Rook Bluehour Round 9 Medium (2026-11-10)

**Status:** Source implementation and CPU/fake-model unit checks complete; **NOT host-certified or production GO**. The actual selected WAV is **not in Git**, is **not included in this patch**, and has **not been activated or played on Venus**. It must be imported explicitly by the owner.

## Selected voice and expression intent

- **Provisional acoustic identity:** `sofia_r9_bluehour_REFERENCE_AIR_medium.wav` (Rook Bluehour, Round 6 original, voiced-upper-air-softmask-v1 medium filtering in Round 9). The exact owner-approved audio is used, not regenerated from prompt text. Its matching Round 9 `.json` and original Round 6 `.json` are mandatory.
- **Personality:** calm, grounded, warm, reflective, with competent technical delivery. Inspiration: primarily Raphtalia-like warmth and secondary Kurisu-like observation in the original Bluehour design; no measured neural character percentages. Cortana-like composure belongs to expression behavior, not imported speech bytes.
- **Optional controlled bite:** Explicit `delivery:bite` tone tag on an already authorized, appropriate utterance. If present the neural generated audio gets a mild pitch-preserving ~7% rate boost. This does not provide Qwen Base with true sarcasm/emotion controls and it never needs to be permanently enabled. Reassurance and safety-critical speech should not be tagged with bite.
- **Breathiness:** Round 9 Medium is already the accepted cleaned reference. New generated sentences are independently synthesized and can remain somewhat breathy. The current backend does **not** apply extra de-air filtering to each new sentence. Another owner listening pass is needed for stronger breath removal; no aggressive unreviewed filter is shipped.

## Architecture

- Extends `src/sofia/modules/voice/` instead of creating a second Core or authority. `tts.py` retains the existing bounded single-worker speech queue and interrupt semantics; the new backend's synthesis is lazy and opt-in. `factory.py` chooses it only on `SOFIA_TTS_BACKEND=qwen3-local-bluehour`.
- `voice_asset.py` validates and privately imports exact Round 9 WAV + JSON metadata and original Round 6 transcript provenance into a Core-scoped, SHA-256-verified profile. The import refuses existing destinations, symlinks, incomplete WAVs and mismatched digests. No voice sample is checked into Git.
- `qwen_local.py` uses Qwen3-TTS 1.7B Base for in-context local voice cloning. Audio samples are played on a local output device with `sounddevice`. `SPOKEN` is emitted only after actual playback; cancelled or failed jobs are never labelled SPOKEN. Production hardware playback must still be proven.
- Model activation requires explicit local TTS enablement, installed audio, dependencies and device; the default environment is SAPI and TTS remains opt-in. Default neural behavior unloads model/clears cache after each utterance to protect VRAM; `AEGIS_VOICE_KEEP_MODEL_WARM=true` allows reduced latency with resident VRAM until service stop. GPU is on Venus; the planned Core VM on Artemis does not need a GPU.
- The Core's metadata cue is non-authoritative. Real isolated Core/Voice operation **must** pass the SDK `aegis.voice.expression.v1` through the Platform's current identity/generation, SAFE/grant/revocation, audience, STOP and owner mute gates, and must bind the requested voice profile and revision to the imported asset. No direct audio endpoint between Artemis and Venus is created by this patch. The existing broker is not an authenticated network listener.
- No streaming STT/voice chat, input capture, enrollments, Fleet deployment, model manager, automatic voice asset transfer or sound card setup is silently activated.

## Local installation and opt-in test on Venus

Install the Aegis Python package in the **same venv as your working Voice Lab/Qwen** or an isolated Aegis venv with compatible free `qwen-tts`, `torch`, `torchaudio`, `numpy`, `sounddevice`, `huggingface_hub`. Keep your existing models and `.venv`; package installation is not performed by this code alone.

From the Aegis source checkout (adjust `E:\...` to your actual Voice Lab directory), PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
$lab = 'E:\Downloads\Aegis_Sofia_Voice_Lab_v1_2\aegis_voice_audition'
$profile = "$env:LOCALAPPDATA\Aegis\private\voice\sofia-bluehour"
# Set to the Platform-registered, owner-authorized Sofia Core identity.
$coreId = 'identity:sofia'
python -m sofia.modules.voice.voice_cli import-round9 `
  --wav "$lab\outputs\round9\sofia_r9_bluehour_REFERENCE_AIR_medium.wav" `
  --round6-json "$lab\outputs\round6\sofia_03_rook_bluehour.json" `
  --profile-dir "$profile" --core-id "$coreId"
python -m sofia.modules.voice.voice_cli verify --profile-dir "$profile" --core-id "$coreId"
# Explicit owner audition on local speakers, loads Qwen Base from cache:
python -m sofia.modules.voice.voice_cli test --profile-dir "$profile" --core-id "$coreId"
# Test occasional bite separately, for an appropriate short technical line:
python -m sofia.modules.voice.voice_cli test --profile-dir "$profile" --core-id "$coreId" --bite --text 'That log contradicts itself. Impressive.'
```

The Core ID example MUST be replaced if the installed Platform uses a different canonical identity. For voice modules deployed through Platform, the setting must come from trusted Platform state, **not an unauthenticated caller or an untrusted Core-supplied string**.

To opt in to existing local runtime output on an explicitly authorized output host:

```powershell
$env:SOFIA_TTS_BACKEND = 'qwen3-local-bluehour'
$env:SOFIA_TTS_ENABLED = 'true'
$env:AEGIS_VOICE_PROFILE_DIR = $profile
$env:AEGIS_VOICE_CORE_ID = $coreId
# Optional only if first-time weights are not already cached:
# $env:AEGIS_VOICE_ALLOW_DOWNLOAD = 'true'
# Optional, uses idle VRAM: $env:AEGIS_VOICE_KEEP_MODEL_WARM = 'true'
```

**Stop/mute:** stop the existing TTS queue via `TextToSpeechService.interrupt()`; `settings.voice_muted` overrides even `SOFIA_TTS_ENABLED=true`. Do not turn on speech without owner device approval. Optional PortAudio `sounddevice` might require a valid Windows audio output configuration. `flash-attn` and SoX are NOT needed by this backend (uses PyTorch SDPA); `sounddevice` is needed for actual output.

## Verification gaps before voice module GO

1. Import owner's exact selected WAV/metadata; record its SHA and license/provenance for owner-only use. No audio bytes are in the repo.
2. On Venus: verify voice matches owner listening preference, clean consonants, warmth and audible breaths; test low VRAM, no GPU, no output device, model-cache offline resolution.
3. Test real Windows PortAudio playback, cancellation during generation and playback, STOP/mute while long GPU work is running, controlled zero-speaker/no-network behavior and actual receipts.
4. Wire owner-authenticated Platform worker IPC and module lifecycle; ensure current SAFE/revocation/mute checks immediately before playback, profile ID/revision enforcement, no spoofed Core identity, persistent replay claim.
5. Validate resource budgets/VRAM unloads on Venus and remote Fleet binding to Artemis VM; do not call Core-free Platform shakedown complete on the basis of this patch.
6. If desired, evaluate breath attenuation of *generated* audio separately. The current selected medium reference is not a guarantee that every generated output is equally de-aired.

## Tests run locally with this source slice

- `pytest` six CPU/fake-Qwen checks: matching Round 6/9 provenance, byte hash and Core binding, no overwrite, tamper refusal, broken provenance refusal, symlink refusal, fake-model speech/playback, pre-load cancellation, and explicit pitch-preserving bite processing.
- `compileall` on added Python sources.
- Repo-wide suite / actual Qwen CUDA playback **not executed in this environment**. Existing TTS/voice handoff tests require real full checkout and normal CI later.
