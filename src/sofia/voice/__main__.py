"""Direct diagnostics for Sofía's local TTS backend."""
from __future__ import annotations

import argparse

from .model import VoiceProsodyProfile
from .sapi import WindowsSapiBackend


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.voice"
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
    )
    parser.add_argument("--voice", default=None)
    parser.add_argument("--say", default=None)
    args = parser.parse_args(argv)

    backend = WindowsSapiBackend()
    probe = backend.probe(
        voice_hint=args.voice
    )

    if args.list_voices:
        if not probe.voices:
            print(
                f"No TTS voices available: {probe.reason}"
            )
            return 1
        for voice in probe.voices:
            marker = (
                "*"
                if voice == probe.selected_voice
                else " "
            )
            print(f"{marker} {voice}")
        return 0

    if args.say is None:
        print(
            f"backend={probe.backend_name} "
            f"available={probe.available} "
            f"healthy={probe.healthy} "
            f"voice={probe.selected_voice or 'none'}"
        )
        return 0 if probe.healthy else 1

    if not probe.healthy:
        print(f"TTS unavailable: {probe.reason}")
        return 1

    receipt = backend.speak(
        utterance_id="manual-test",
        text=args.say,
        profile=VoiceProsodyProfile(),
        voice_hint=args.voice,
    )
    print(
        f"{receipt.state.value}: "
        f"backend={receipt.backend_name} "
        f"voice={receipt.voice_name or 'default'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
