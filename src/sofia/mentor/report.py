"""Human-readable, non-promotional MENTOR quality snapshot.

A task-stage record is not a live operational or independently verified CI claim.
"""
from __future__ import annotations

from .audit import MentorAuditError, SCHEMA, STAGES


def markdown_report(report: dict) -> str:
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise MentorAuditError("untrusted report for Markdown rendering")
    summary = report.get("summary")
    if not isinstance(summary, dict) or summary.get("total_tasks") != 780:
        raise MentorAuditError("incomplete report")
    counts = summary.get("stages")
    if not isinstance(counts, dict) or any(type(counts.get(x)) is not int for x in STAGES):
        raise MentorAuditError("invalid stage totals")
    if sum(counts[s] for s in STAGES) != 780:
        raise MentorAuditError("stage counts do not cover 780 tasks")
    lines = [
        "# Sofía MENTOR: Read-only Quality Snapshot",
        "",
        f"**Source revision:** \\u0060{report['source_revision']}\\u0060",
        f"**Generated UTC:** {report['generated_at']}",
        "",
        "This is an evidence-inventory snapshot, **not production certification**.",
        "",
        "## Five-stage development inventory",
        "",
        "| Stage | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {stage} | {counts[stage]} |" for stage in STAGES)
    lines.extend([
        "| **Total** | **780** |",
        "",
        f"- Individually audited task records: **{summary['audited_tasks']} / 780**",
        f"- Not individually classified: **{summary['unassessed_tasks']}**",
        f"- Historical evidence revisions differing from current HEAD: **{summary['historical_revision_records']}**",
        f"- Reference-document problems: **{summary['failed_document_checks']}**",
        "",
        "## Evidence by V18 phase",
        "",
        "| Phase | Unassessed | Coded unfinished | Production coded | Tested locally | Tested CI (recorded) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    phases = report.get("phases")
    if not isinstance(phases, dict) or len(phases) != 17:
        raise MentorAuditError("phase coverage incomplete")
    for phase, row in sorted(phases.items()):
        lines.append("| " + phase + " | " + " | ".join(
            str(row[stage]) for stage in STAGES
        ) + " |")
    lines.extend(["", "## Source integrity findings", ""])
    findings = report.get("findings", [])
    if findings:
        lines.extend(
            f"- **{x['severity']}**: {x['kind']} ({x['subject']})"
            for x in findings
        )
    else:
        lines.append("- No missing-reference or Atlas-ID mismatches detected.")
    lines.extend([
        "",
        "## Engineering priorities",
        "",
        "1. Reconcile unassessed tasks against current production code and the exact original requirements.",
        "2. Review incomplete implementation clauses before promoting any task.",
        "3. Re-run task-specific tests and record exact Git revisions, negative cases and host-dependent results.",
        "4. Verify CI and live host acceptance independently; do not translate this audit into a completion claim.",
        "5. Use both the Technical & MENTOR Reference and the Complete Atlas when diagnosing personality, tools, vision and learning regressions.",
        "",
        "## Limitations",
        "",
    ])
    lines.extend(f"- {value}" for value in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)
