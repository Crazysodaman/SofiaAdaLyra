"""Owner/developer read-only MENTOR CLI.

Usage:
  python -m sofia.mentor audit --repo .
  python -m sofia.mentor audit --repo . --output mentor-report.json
  python -m sofia.mentor diff --previous before.json --current after.json
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .audit import MentorAuditError, audit_checkout, compare_reports
from .report import markdown_report
from .bridge import BridgeConfig, MentorBridgeError, SCENARIOS, run_synthetic_dialogue
from .openai_diagnostics import check_openai_model
from .local_bridge import LocalBridgeConfig, run_local_dialogue
from .oracles import get_oracle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.mentor")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Verify 780-task inventory and historical evidence")
    audit.add_argument("--repo", type=Path, default=Path("."))
    audit.add_argument("--output", type=Path, default=None,
                       help="Write a sanitized JSON report; stdout remains a short summary")
    audit.add_argument("--task", default=None, help="Select one known CA/ML/GA task")
    audit.add_argument("--markdown", type=Path, default=None,
                       help="Write an owner-readable quality snapshot")
    diff = sub.add_parser("diff", help="Compare two saved audits")
    diff.add_argument("--previous", type=Path, required=True)
    diff.add_argument("--current", type=Path, required=True)
    api_check = sub.add_parser(
        "check-api", help="Verify API key/model metadata, without inference or Sofía data"
    )
    api_check.add_argument("--external-model", required=True)
    api_check.add_argument("--allow-external", action="store_true",
                           help="Authorize a metadata-only GET to OpenAI")
    local_talk = sub.add_parser(
        "local-converse", help="Free, loopback-only synthetic two-model MENTOR dialogue"
    )
    local_talk.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    local_talk.add_argument("--student-model", required=True)
    local_talk.add_argument("--mentor-model", required=True)
    local_talk.add_argument("--rounds", type=int, default=2)
    local_talk.add_argument("--max-output-tokens", type=int, default=350)
    local_talk.add_argument("--timeout-seconds", type=int, default=60)
    local_talk.add_argument(
        "--preview", action="store_true", help="Show fixture and model plan without calls"
    )
    local_talk.add_argument(
        "--confirm-idle", action="store_true",
        help="Owner confirms Venus is idle, not gaming, and may load local models",
    )
    talk = sub.add_parser(
        "converse", help="Opt-in tool-free synthetic dialogue between Ollama and OpenAI"
    )
    talk.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    talk.add_argument("--local-model", required=True)
    talk.add_argument("--external-model", required=True)
    talk.add_argument("--rounds", type=int, default=2)
    talk.add_argument("--max-output-tokens", type=int, default=350)
    talk.add_argument("--preview", action="store_true",
                      help="Print exact synthetic scenario; make no local or external calls")
    talk.add_argument("--allow-external", action="store_true",
                      help="I authorize sharing this public synthetic fixture and stateless model output")
    try:
        if args := parser.parse_args(argv):
            if args.command == "check-api":
                if not args.allow_external:
                    raise MentorBridgeError("API preflight requires --allow-external")
                print(json.dumps(check_openai_model(
                    args.external_model, os.environ.get("OPENAI_API_KEY", ""),
                ), indent=2))
                return 0
            if args.command == "local-converse":
                cfg = LocalBridgeConfig(
                    student_model=args.student_model,
                    mentor_model=args.mentor_model,
                    max_rounds=args.rounds,
                    max_output_tokens=args.max_output_tokens,
                    timeout_seconds=args.timeout_seconds,
                )
                if args.preview:
                    print(json.dumps({
                        "mode": "local-preview-no-network",
                        "scenario_id": args.scenario,
                        "scenario": SCENARIOS[args.scenario],
                        "evaluation_reference": get_oracle(args.scenario),
                        "student_model": cfg.student_model,
                        "mentor_model": cfg.mentor_model,
                        "rounds": cfg.max_rounds,
                        "external_api_required": False,
                        "keep_alive": 0,
                    }, indent=2, ensure_ascii=False))
                    return 0
                if not args.confirm_idle:
                    raise MentorBridgeError(
                        "local GPU models require --confirm-idle: stop if gaming"
                    )
                print(json.dumps(run_local_dialogue(
                    config=cfg, scenario_id=args.scenario,
                ), indent=2, ensure_ascii=False))
                return 0
            if args.command == "converse":
                cfg = BridgeConfig(
                    local_model=args.local_model,
                    external_model=args.external_model,
                    max_rounds=args.rounds,
                    max_output_tokens=args.max_output_tokens,
                )
                if args.preview:
                    print(json.dumps({
                        "mode": "synthetic-preview-no-network",
                        "scenario_id": args.scenario,
                        "scenario": SCENARIOS[args.scenario],
                        "local_model": cfg.local_model,
                        "external_model": cfg.external_model,
                        "rounds": cfg.max_rounds,
                        "max_output_tokens_per_call": cfg.max_output_tokens,
                        "external_payload_note": (
                            "Real mode additionally shares the generated bounded local model answer."
                        ),
                    }, indent=2, ensure_ascii=False))
                    return 0
                result = run_synthetic_dialogue(
                    config=cfg, scenario_id=args.scenario,
                    allow_external=args.allow_external,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.command == "audit":
                report = audit_checkout(args.repo)
                if args.task:
                    matches = [t for t in report["tasks"] if t["task_id"] == args.task]
                    if not matches:
                        raise MentorAuditError("unknown task id")
                    print(json.dumps(matches[0], indent=2, sort_keys=True))
                    return 0
                if args.output:
                    output = args.output
                    if output.is_symlink() or (output.exists() and not output.is_file()):
                        raise MentorAuditError("report destination is unsafe")
                    output.write_text(
                        json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                if args.markdown:
                    if args.markdown.is_symlink() or (
                        args.markdown.exists() and not args.markdown.is_file()
                    ):
                        raise MentorAuditError("Markdown destination is unsafe")
                    args.markdown.write_text(markdown_report(report), encoding="utf-8")
                print(json.dumps({
                    "source_revision": report["source_revision"],
                    "summary": report["summary"],
                    "findings": report["findings"],
                    "report_written": str(args.output) if args.output else None,
                    "markdown_written": str(args.markdown) if args.markdown else None,
                }, indent=2, sort_keys=True))
                return 1 if report["findings"] else 0
            previous = json.loads(args.previous.read_text(encoding="utf-8"))
            current = json.loads(args.current.read_text(encoding="utf-8"))
            print(json.dumps(compare_reports(previous, current), indent=2, sort_keys=True))
            return 0
    except (MentorAuditError, RuntimeError, FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
        print("MENTOR request refused: " + str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
