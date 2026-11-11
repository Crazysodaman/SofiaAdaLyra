"""Owner-run CLI for local Aegis voice asset activation and testing.

Only explicit 'test' opens an audio output device, and no command opens a mic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .voice_asset import import_round9_medium, load_voice_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.modules.voice.voice_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("import-round9", help="Import owner-approved Round 9 WAV privately")
    install.add_argument("--wav", type=Path, required=True)
    install.add_argument("--round6-json", type=Path, required=True)
    install.add_argument("--profile-dir", type=Path, required=True)
    install.add_argument("--core-id", required=True)
    check = commands.add_parser("verify", help="Check installed profile and SHA-256 without speaking")
    check.add_argument("--profile-dir", type=Path, required=True)
    check.add_argument("--core-id", required=True)
    speak = commands.add_parser("test", help="Explicit, local audio playback; never use unattended")
    speak.add_argument("--profile-dir", type=Path, required=True)
    speak.add_argument("--core-id", required=True)
    speak.add_argument("--text", default="Sofia here. The diagnostics look fine. For once.")
    speak.add_argument("--bite", action="store_true")
    speak.add_argument("--allow-download", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "import-round9":
            profile = import_round9_medium(args.wav, args.round6_json,
                                           args.profile_dir, core_identity_id=args.core_id)
            print("IMPORTED", profile.profile_id, profile.wav_sha256)
        elif args.command == "verify":
            profile = load_voice_profile(args.profile_dir, expected_core_identity_id=args.core_id)
            print(json.dumps({"profile_id": profile.profile_id, "revision": profile.revision,
                              "core_identity_id": profile.core_identity_id,
                              "wav_sha256": profile.wav_sha256, "verified": True}, indent=2))
        else:
            from .qwen_local import QwenLocalBluehourBackend
            from .prosody_matrix import VoiceProsodyProfile
            from .tts import TTSPlaybackState
            backend = QwenLocalBluehourBackend(args.profile_dir, core_identity_id=args.core_id,
                                               allow_model_download=args.allow_download)
            probe = backend.probe()
            if not probe.healthy:
                raise RuntimeError(probe.reason)
            profile = VoiceProsodyProfile(tone_tags=("delivery:bite",) if args.bite else ())
            try:
                receipt = backend.speak(utterance_id="manual:test", text=args.text, profile=profile)
            finally:
                backend.unload()
            print(receipt.state.value)
            return 0 if receipt.state is TTSPlaybackState.SPOKEN else 3
        return 0
    except (OSError, TypeError, ValueError, RuntimeError, PermissionError) as exc:
        print(f"VOICE ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
