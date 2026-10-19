"""Owner/developer read-only MENTOR CLI.

Usage:
  python -m sofia.mentor audit --repo .
  python -m sofia.mentor audit --repo . --output mentor-report.json
  python -m sofia.mentor diff --previous before.json --current after.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .audit import MentorAuditError, audit_checkout, compare_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.mentor")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Verify 780-task inventory and historical evidence")
    audit.add_argument("--repo", type=Path, default=Path("."))
    audit.add_argument("--output", type=Path, default=None,
                       help="Write a sanitized JSON report; stdout remains a short summary")
    audit.add_argument("--task", default=None, help="Select one known CA/ML/GA task")
    diff = sub.add_parser("diff", help="Compare two saved audits")
    diff.add_argument("--previous", type=Path, required=True)
    diff.add_argument("--current", type=Path, required=True)
    try:
        if args := parser.parse_args(argv):
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
                print(json.dumps({
                    "source_revision": report["source_revision"],
                    "summary": report["summary"],
                    "findings": report["findings"],
                    "report_written": str(args.output) if args.output else None,
                }, indent=2, sort_keys=True))
                return 1 if report["findings"] else 0
            previous = json.loads(args.previous.read_text(encoding="utf-8"))
            current = json.loads(args.current.read_text(encoding="utf-8"))
            print(json.dumps(compare_reports(previous, current), indent=2, sort_keys=True))
            return 0
    except (MentorAuditError, FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
        print("MENTOR audit refused: " + str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
