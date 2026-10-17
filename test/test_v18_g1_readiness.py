"""Gate-1 design candidate checking must never self-award an accepted task."""
from pathlib import Path

import pytest

from sofia.verify.v18_g1_readiness import (
    G1SubmissionError, inspect_g1_submissions,
)

pytestmark = pytest.mark.pkg_verify


def prepare(tmp_path: Path, *, original=None, second_packet=False):
    roadmap = tmp_path / "docs/roadmaps"
    roadmap.mkdir(parents=True)
    original = original or "- [ ] **CA-1 P0 [DESIGN/RESEARCH]** Original task."
    roadmap.joinpath(
        "Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md"
    ).write_text(
        original + "\n" + "\n".join(
            f"- [ ] **CA-{n} [DESIGN/RESEARCH]** Other item."
            for n in range(2, 701)
        ) + "\n",
        encoding="utf-8",
    )
    review = tmp_path / "docs/development"
    review.mkdir(parents=True)
    filename = review / "review.md"
    filename.write_text(
        "# Review\n\n"
        "## CA-1: Test candidate\n\n"
        "**Original:** **CA-1 P0 [DESIGN/RESEARCH]** Original task.\n\n"
        "**Decision:** Source-independent review is still pending.\n\n"
        "**Source references:** Repo tests and original roadmap.\n\n"
        "**G1 acceptance:** OPEN, independent review required.\n",
        encoding="utf-8",
    )
    paths = ("docs/development/review.md",)
    if second_packet:
        duplicate = review / "duplicate.md"
        duplicate.write_text(filename.read_text(encoding="utf-8"), encoding="utf-8")
        paths += ("docs/development/duplicate.md",)
    return paths


def test_one_candidate_matches_exact_original_without_self_awarding_gate(tmp_path):
    paths = prepare(tmp_path)
    report = inspect_g1_submissions(tmp_path, packet_paths=paths)
    assert report["total_submissions"] == 1
    assert report["unique_submissions"] == 1
    assert report["independently_accepted_gate1"] == 0
    assert report["tasks"][0]["id"] == "CA-1"
    assert report["tasks"][0]["gate1_accepted"] is False
    assert report["tasks"][0]["packet_sha256"]
    assert report["tasks"][0]["original_requirement_sha256"]


def test_drift_from_original_requirement_is_rejected(tmp_path):
    paths = prepare(tmp_path)
    packet = tmp_path / "docs/development/review.md"
    packet.write_text(
        packet.read_text().replace("Original task.", "Changed criteria."),
        encoding="utf-8",
    )
    with pytest.raises(G1SubmissionError, match="requirement drift"):
        inspect_g1_submissions(tmp_path, packet_paths=paths)


def test_duplicate_candidate_across_files_is_rejected(tmp_path):
    paths = prepare(tmp_path, second_packet=True)
    with pytest.raises(G1SubmissionError, match="duplicate G1"):
        inspect_g1_submissions(tmp_path, packet_paths=paths)


def test_draft_missing_independent_review_state_is_rejected(tmp_path):
    paths = prepare(tmp_path)
    packet = tmp_path / "docs/development/review.md"
    packet.write_text(packet.read_text().replace(
        "**G1 acceptance:** OPEN, independent review required.",
        "**G1 acceptance:** PASSED, self-approved."
    ), encoding="utf-8")
    with pytest.raises(G1SubmissionError, match="pending review"):
        inspect_g1_submissions(tmp_path, packet_paths=paths)


def test_path_escape_and_symlinked_packets_are_rejected(tmp_path):
    prepare(tmp_path)
    with pytest.raises(G1SubmissionError, match="unsafe"):
        inspect_g1_submissions(tmp_path, packet_paths=("../escape.md",))
    parent = tmp_path / "docs/development"
    other = tmp_path / "file.md"
    other.write_text("anything", encoding="utf-8")
    link = parent / "link.md"
    try:
        link.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("host lacks symlink privilege")
    with pytest.raises(G1SubmissionError, match="symlinked"):
        inspect_g1_submissions(tmp_path, packet_paths=("docs/development/link.md",))


def test_live_20_submission_packets_match_original_roadmap():
    """Real, tracked source review candidates have 20 unique original IDs."""
    report = inspect_g1_submissions(Path(__file__).resolve().parents[1])
    assert report["total_submissions"] == 20
    assert report["unique_submissions"] == 20
    assert report["independently_accepted_gate1"] == 0
    assert all(row["submission_status"] == "draft_for_independent_review"
               for row in report["tasks"])
