"""Read-only evidence-backed Gate 4 status for CA and ML/GA addenda."""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import subprocess
from sofia.verify.v18_roadmap import (
    LEDGER_RELATIVE, MASTER_RELATIVE, EXPANDED_TABLE_RELATIVE,
    RoadmapIntegrityError, _within,
    validate_repository,
)
from sofia.verify.v18_gate4_review import review_readiness

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_EXTRA_ROW = re.compile(r"^\| ((?:ML|GA)-[0-9]{3}) \| ([0-9]{2}) \| (.*) \|$")
_EXTRA_PROOFS = "docs/development/v18-supplemental-gate4-proofs.json"


def verified_gate_count(root: Path, task: dict) -> int:
    """Unverified code paths and CI associations do not count as passed gates."""
    proofs = task.get("gate4_proofs", [])
    if not isinstance(proofs, list) or len(proofs) > 4:
        raise RoadmapIntegrityError("invalid gate evidence for " + task["id"])
    for index, proof in enumerate(proofs, 1):
        if not isinstance(proof, dict) or proof.get("gate") != index:
            raise RoadmapIntegrityError("out-of-order gate proof for " + task["id"])
        revision, digest, reviewer = (proof.get("revision"), proof.get("sha256"),
                                      proof.get("reviewer"))
        if (not isinstance(revision, str) or not _SHA.fullmatch(revision)
                or not isinstance(digest, str) or not _HASH.fullmatch(digest)
                or not isinstance(reviewer, str) or not reviewer.strip()):
            raise RoadmapIntegrityError("incomplete gate provenance for " + task["id"])
        # Git HEAD holds exact reviewed bytes. A Windows working tree may
        # automatically materialize CRLF even though the committed evidence
        # has canonical LF. Hash the immutable Git blob, never a normalized
        # or silently modified working copy.
        relative = proof.get("evidence_path")
        _within(root, relative)
        reading = subprocess.run(
            ("git", "show", "HEAD:" + relative),
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15, check=False,
        )
        if reading.returncode != 0:
            raise RoadmapIntegrityError("gate evidence is not a HEAD Git blob for " + task["id"])
        if sha256(reading.stdout).hexdigest() != digest:
            raise RoadmapIntegrityError("gate evidence digest mismatch for " + task["id"])
        if index == 4:
            ci = proof.get("ci")
            if (not isinstance(ci, dict)
                    or type(ci.get("run_id")) is not int or ci["run_id"] < 1
                    or ci.get("head_sha") != revision
                    or ci.get("conclusion") != "success"
                    or not isinstance(ci.get("test_ids"), list)
                    or not ci["test_ids"]
                    or any(not isinstance(x, str) or not x.strip()
                           for x in ci["test_ids"])):
                raise RoadmapIntegrityError("missing exact CI test receipt for " + task["id"])
    return len(proofs)


def _kind(line: str) -> str:
    if "[DESIGN/RESEARCH]" in line:
        return "design/research"
    if "[VERIFY]" in line or "[VERIFY / HARDEN]" in line:
        return "verification"
    return "implementation"


def _next(task: dict, gate: int, kind: str) -> str:
    if gate == 4:
        return ("Receipt packet exists, but task acceptance is not independently "
                "authenticated. Recheck original requirements, reviewer, CI and host tests.")
    if gate == 3:
        return "Run task-specific tests and failure cases at an exact revision."
    if gate == 2:
        return "Audit all requirements, permission paths, recovery and resources."
    if gate == 1:
        return "Integrate approved design or real canonical runtime/effect paths."
    if kind == "design/research":
        return "Complete and independently review the research/design deliverable."
    if kind == "verification":
        return "Run the original specified independent verification, with receipts."
    return {
        "unassessed": "Trace the exact original requirement, implement missing code, identify tests.",
        "partial_wiring": "Close the missing end-to-end production path before full tests.",
        "code_present_unverified": "Verify coverage, audit behavior and run focused/integration tests.",
        "accepted": "Reconcile prior acceptance with explicit Gate 1-4 proof.",
    }[task["status"]]


def gate4_snapshot(root: Path, *, ledger: dict | None = None) -> dict:
    root = root.resolve(strict=True)
    validate_repository(root)
    data = ledger if ledger is not None else json.loads(
        _within(root, LEDGER_RELATIVE.as_posix()).read_text(encoding="utf-8"))
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 700:
        raise RoadmapIntegrityError("all 700 original task records are required")
    original = _within(root, MASTER_RELATIVE.as_posix()).read_text(
        encoding="utf-8").splitlines()
    per_phase, counts, output, seen = {}, Counter(), [], set()
    for task in tasks:
        task_id, phase, status = task["id"], task["phase"], task["status"]
        if task_id in seen:
            raise RoadmapIntegrityError("duplicate task " + task_id)
        seen.add(task_id)
        line = original[task["master_line"] - 1]
        if "**" + task_id + " " not in line:
            raise RoadmapIntegrityError("task source mismatch " + task_id)
        gate = verified_gate_count(root, task)
        # A content-bound receipt packet is NOT independent acceptance.
        # Nothing in the present ledger proves an independently authenticated
        # reviewer has covered every original requirement.
        review = review_readiness(task)
        independently_accepted = False
        independent_review_pending = gate == 4
        kind = _kind(line)
        phase_row = per_phase.setdefault(phase, {
            "total": 0, "unassessed": 0, "partial_wiring": 0,
            "code_present_unverified": 0, "accepted": 0, "gate4": 0,
        })
        if status not in phase_row:
            raise RoadmapIntegrityError("invalid task status " + task_id)
        phase_row["total"] += 1
        phase_row[status] += 1
        phase_row["gate4"] += int(independently_accepted)
        counts[status] += 1
        counts["gate4"] += int(independently_accepted)
        gap = ((task.get("phase00_batch30_review") or {}).get("unresolved_requirement")
               or (task.get("audit_observation") or {}).get("missing")
               or (task.get("production_wiring") or {}).get("remaining"))
        output.append({
            "id": task_id, "phase": phase, "kind": kind, "source_status": status,
            "original_requirement": line,
            "gate_with_recorded_proof": gate, "gate4": independently_accepted,
            "review_readiness": review["review_readiness"],
            "independent_review_pending": independent_review_pending,
            "next_gate": min(gate + 1, 4),
            "next_action": _next(task, gate, kind),
            "known_missing": gap if isinstance(gap, str) else None,
            "code_paths": task.get("code_paths", [])[:6],
        })
    ranking = {"code_present_unverified": 0, "partial_wiring": 1,
               "unassessed": 2, "accepted": 3}
    focus = sorted((t for t in output if not t["gate4"]),
                   key=lambda x: (ranking[x["source_status"]], x["phase"]))[:20]
    # The 40 ML and 40 GA addenda remain distinct from the original CA ledger.
    # Their separate proof file is only a receipt overlay, never a new state writer.
    supplemental_proofs = json.loads(_within(root, _EXTRA_PROOFS).read_text(
        encoding="utf-8"))
    if (supplemental_proofs.get("schema") != "sofia.v18-supplemental-gate4-v1"
            or not isinstance(supplemental_proofs.get("tasks"), dict)):
        raise RoadmapIntegrityError("invalid supplemental gate evidence schema")
    extra = []
    for line in _within(root, EXPANDED_TABLE_RELATIVE.as_posix()).read_text(
            encoding="utf-8").splitlines():
        match = _EXTRA_ROW.fullmatch(line)
        if match is None:
            continue
        key, phase, requirement = match.groups()
        passed = verified_gate_count(root, {
            "id": key, "gate4_proofs": supplemental_proofs["tasks"].get(key, []),
        })
        extra.append({
            "id": key, "phase": phase, "kind": "additional planned ML/GA task",
            "original_requirement": requirement, "gate_with_recorded_proof": passed,
            "gate4": False,
            "independent_review_pending": passed == 4,
            "next_gate": min(passed + 1, 4),
            "next_action": ("Independent acceptance needed for every original requirement."
                            if passed == 4 else
                            "Implement and audit planned item; validate original "
                            "ML/GA acceptance and focused tests."),
        })
    if len(extra) != 80 or len({x["id"] for x in extra}) != 80:
        raise RoadmapIntegrityError("expected 40 ML and 40 GA supplemental tasks")
    if set(supplemental_proofs["tasks"]) - {x["id"] for x in extra}:
        raise RoadmapIntegrityError("unknown supplemental task proof")
    extras_at_four = sum(x["gate4"] for x in extra)
    return {
        "schema": "sofia.v18-gate4-evidence-only-v2",
        "target": 4, "deferred": [5, 6], "original_total": 700,
        "planned_total": 780, "supplemental_total": 80,
        "supplemental_gate4_verified": extras_at_four,
        "overall_gate4_verified": counts["gate4"] + extras_at_four,
        "overall_gate4_remaining": 780 - counts["gate4"] - extras_at_four,
        "counts": {**{key: counts[key] for key in
                      ("unassessed", "partial_wiring", "code_present_unverified", "accepted")},
                   "gate4_verified": counts["gate4"],
                   "still_unverified": 700 - counts["gate4"]},
        "phases": per_phase, "focus_next": focus, "tasks": output,
        "supplemental_tasks": extra,
        "warning": "No task has independent Gate 4 acceptance authenticated "
                   "by this verifier. Historical proof entries and green CI "
                   "are not full requirement coverage or reviewer sign-off.",
    }


def markdown_summary(data: dict) -> str:
    c = data["counts"]
    lines = ["# Sofía V18 Gate 4 Progress", "",
             "Development target is all 780 planned tasks (700 CA + 40 ML + 40 GA) through Gate 4. Gates 5-6 deferred.",
             f"**Independently verified Gate 4: {c['gate4_verified']}/700.** "
             f"Still unverified CA tasks: {c['still_unverified']}.",
             f"Overall independently verified: {data['overall_gate4_verified']}/780; "
             f"remaining: {data['overall_gate4_remaining']}.",
             "Historical receipt packets are not counted as completed tasks.",
             f"Source triage: {c['unassessed']} unassessed; "
             f"{c['partial_wiring']} partially wired; "
             f"{c['code_present_unverified']} code present but unverified.", "",
             "| Phase | Total | Unassessed | Partial | Code unverified | Gate4 |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for phase, row in sorted(data["phases"].items()):
        lines.append(f"| {phase} | {row['total']} | {row['unassessed']} | "
                     f"{row['partial_wiring']} | {row['code_present_unverified']} | "
                     f"{row['gate4']} |")
    lines += ["", "## Next 20 candidate tasks", "",
              "| ID | Phase | Source status | Next work |",
              "| --- | --- | --- | --- |"]
    for t in data["focus_next"]:
        lines.append(f"| {t['id']} | {t['phase']} | {t['source_status']} | "
                     + t["next_action"].replace("|", "/") + " |")
    lines.append("")
    lines.append("ML and GA addenda: 80 supplemental planned items, "
                 f"{data['supplemental_gate4_verified']} independently verified.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = gate4_snapshot(args.repo)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(markdown_summary(report), encoding="utf-8")
        print(f"verified_gate4={report['overall_gate4_verified']}/780")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("Gate4 report rejected: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
