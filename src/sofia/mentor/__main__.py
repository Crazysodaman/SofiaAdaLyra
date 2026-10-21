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
from ..config.model_catalog import LEGACY_SINGLE_PRESET
from .report import markdown_report
from .bridge import BridgeConfig, MentorBridgeError, SCENARIOS, run_synthetic_dialogue
from .openai_diagnostics import check_openai_model
from .local_bridge import LocalBridgeConfig, run_local_dialogue
from .oracles import get_oracle
from .exchange import write_public_outbox, read_review
from .remote_inbox import MentorReviewConsumer
from .behavior_history import read_counts, default_local_path, public_free_summary
from .behavior_diagnostics import diagnose_behavior
from .windows_service_settings import (
    service_settings_status, configure_custom_service_settings,
    disable_custom_service_settings,
)
from .behavior_monitor import PrivateTurn, evaluate_private_turn
from .system_parts import system_parts_summary
from .personality_review import (
    review_response, publish_public_personality_summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.mentor")
    sub = parser.add_subparsers(dest="command", required=True)
    systems = sub.add_parser(
        "system-status", help="Inspect whole-Sofía source, evidence and personality status"
    )
    systems.add_argument("--repo", type=Path, default=Path("."))

    behavior = sub.add_parser(
        "behavior-status",
        help="Show only locally stored aggregate personality/emotion scores; no transcripts"
    )
    diagnose = sub.add_parser(
        "behavior-diagnose", help="Explain zero local reviews and environment limits without network"
    )
    diagnose.add_argument("--repo", type=Path, default=Path("."))
    diagnose.add_argument("--history", type=Path, default=None,
                          help="Optional authorized local score file from another account")

    svc = sub.add_parser(
        "behavior-service", help="View/prepare opt-in Windows SCM MENTOR settings; no restarts"
    )
    svc.add_argument("--action", choices=("status", "plan", "enable", "disable"),
                     default="status")
    svc.add_argument("--source-root", type=Path, default=None)
    svc.add_argument("--approve-scm-change", action="store_true",
                     help="Owner explicitly authorizes these two optional SCM custom options")

    smoke = sub.add_parser(
        "behavior-smoke", help="Run one synthetic local emotion/personality rubric test"
    )
    smoke.add_argument("--repo", type=Path, default=Path("."))
    smoke.add_argument("--mentor-model", default=LEGACY_SINGLE_PRESET.model)
    smoke.add_argument("--confirm-idle", action="store_true",
                       help="Operator affirms local GPU may be used while not gaming")
    persona = sub.add_parser(
        "personality-review", help="Privately compare one owner-selected Sofía reply with her source profile"
    )
    persona.add_argument("--repo", type=Path, default=Path("."))
    persona.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    persona.add_argument("--response-file", type=Path, required=True)
    persona.add_argument("--mentor-model", required=True)
    persona.add_argument("--source-kind", required=True, choices=[
        "owner-selected-sofia-output", "model-only-synthetic",
    ])
    persona.add_argument("--confirm-idle", action="store_true",
                       help="Explicit confirmation Venus may use GPU locally")
    persona.add_argument("--approve-public-summary", action="store_true",
                       help="Consent to write numeric-only summary into the PUBLIC Git checkout; never raw reply")

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
    publish = sub.add_parser(
        "exchange-export", help="Write safe public Git outbox without committing or pushing"
    )
    publish.add_argument("--repo", type=Path, default=Path("."))
    remote_poll = sub.add_parser(
        "exchange-poll", help="Read public GitHub MENTOR advice, without pulling Git or executing it"
    )
    remote_poll.add_argument(
        "--allow-public-network", action="store_true",
        help="Consent to fetch ONLY the fixed public GitHub inbox"
    )
    incoming = sub.add_parser(
        "exchange-read", help="Inspect text-only Git MENTOR feedback, never execute"
    )
    incoming.add_argument("--repo", type=Path, default=Path("."))
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
            if args.command == "system-status":
                systems = system_parts_summary(args.repo)
                print(json.dumps(systems, indent=2, ensure_ascii=False))
                return 0
            if args.command == "behavior-service":
                if args.action == "status":
                    reply = service_settings_status()
                elif args.action == "plan":
                    if args.source_root is None:
                        raise MentorBridgeError("service plan requires --source-root")
                    reply = configure_custom_service_settings(
                        root=args.source_root, apply=False,
                    )
                elif args.action == "enable":
                    if not args.approve_scm_change or args.source_root is None:
                        raise MentorBridgeError(
                            "SCM enable requires --source-root and --approve-scm-change"
                        )
                    reply = configure_custom_service_settings(
                        root=args.source_root, apply=True,
                    )
                else:
                    if not args.approve_scm_change:
                        raise MentorBridgeError("SCM disable requires --approve-scm-change")
                    reply = disable_custom_service_settings(apply=True)
                print(json.dumps(reply, indent=2, ensure_ascii=False))
                return 0
            if args.command == "behavior-diagnose":
                print(json.dumps(diagnose_behavior(
                    root=args.repo, history_path=args.history,
                ), indent=2, ensure_ascii=False))
                return 0
            if args.command == "behavior-smoke":
                if not args.confirm_idle:
                    raise MentorBridgeError(
                        "synthetic local critic requires --confirm-idle; stop if gaming"
                    )
                from datetime import datetime, timezone
                fixture = PrivateTurn(
                    prompt=(
                        "A synthetic service reports ECONNREFUSED on localhost:9000. "
                        "Its log says listener disabled. What should be tested first?"
                    ),
                    answer=(
                        "Observed: ECONNREFUSED and the synthetic log reports "
                        "listener disabled. A disabled listener is a plausible cause, "
                        "not a verified host finding. Inspect effective listener "
                        "configuration and check the bound port read-only."
                    ),
                    tone="settled", emotions=(), channel="conversation",
                    recorded_at=datetime.now(timezone.utc),
                )
                score = evaluate_private_turn(
                    repo=args.repo, turn=fixture, model=args.mentor_model,
                )
                print(json.dumps({
                    "mode": "synthetic-local-only-no-history-writes",
                    "status": score["status"],
                    "personality_scores": score["personality_scores"],
                    "emotion_scores": score["emotion_scores"],
                    "human_review_required": True,
                    "runtime_turn_tested": False,
                    "commands_executed": 0, "cloud_api_calls": 0,
                }, indent=2, ensure_ascii=False))
                return 0
            if args.command == "behavior-status":
                print(json.dumps(
                    public_free_summary(read_counts(default_local_path())),
                    indent=2, ensure_ascii=False,
                ))
                return 0
            if args.command == "personality-review":
                if not args.confirm_idle:
                    raise MentorBridgeError(
                        "local reviewer requires --confirm-idle; do not compete with gaming"
                    )
                inp = args.response_file
                if inp.is_symlink() or not inp.is_file() or inp.stat().st_size > 5000:
                    raise MentorBridgeError("owner-selected response file invalid or too large")
                text = inp.read_text(encoding="utf-8-sig")
                assessment = review_response(
                    repo=args.repo, scenario_id=args.scenario,
                    response=text, model=args.mentor_model,
                    source_kind=args.source_kind,
                )
                result = {"assessment": assessment, "private": True}
                if args.approve_public_summary:
                    result["published_local_file"] = publish_public_personality_summary(
                        args.repo, assessment,
                    )
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            if args.command == "exchange-export":
                print(json.dumps(write_public_outbox(args.repo), indent=2))
                return 0
            if args.command == "exchange-poll":
                if not args.allow_public_network:
                    raise MentorBridgeError("remote inbox requires --allow-public-network")
                consumer = MentorReviewConsumer()
                status = consumer.poll()
                print(json.dumps({
                    "status": status,
                    "snapshot": consumer.snapshot(),
                }, indent=2, ensure_ascii=False))
                return 0 if status["status"] in ("updated", "unchanged") else 2
            if args.command == "exchange-read":
                review = read_review(args.repo)
                print(json.dumps({
                    "source_revision": review["reviewed_source_revision"],
                    "summary": review["summary"],
                    "recommendations": review["recommendations"],
                    "part_reviews": review.get("part_reviews", []),
                    "limitations": review["limitations"],
                    "advisory_only": True,
                    "automatic_actions_authorized": False,
                }, indent=2, ensure_ascii=False))
                return 0
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
