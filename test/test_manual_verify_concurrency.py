"""Release verification must preserve started exact-SHA main evidence."""
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "manual-verify.yml"
)


def test_started_main_manual_verification_is_not_cancelled_by_new_push():
    text = WORKFLOW.read_text(encoding="utf-8")
    concurrency = text.split("concurrency:", 1)[1].split("\non:", 1)[0]
    assert "cancel-in-progress: false" in concurrency
    assert "github.event_name == 'workflow_dispatch'" in concurrency
    assert "github.sha || github.ref" in concurrency
    assert "timeout-minutes: 120" in text
    assert "name: Upload verification evidence" in text


def test_aegis_candidate_push_runs_complete_release_verification_before_merge():
    for filename in (
        "manual-verify.yml", "package-tests.yml", "release-candidate.yml",
        "debian-release-candidate.yml", "compatibility.yml", "matrix-tests.yml",
    ):
        text = (WORKFLOW.parent / filename).read_text(encoding="utf-8")
        triggers = text.split("\non:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
        assert "codex/aegis-shakedown" in triggers, filename


def test_candidate_push_does_not_broaden_trusted_keyless_signing_refs():
    for filename in ("release-candidate.yml", "debian-release-candidate.yml"):
        text = (WORKFLOW.parent / filename).read_text(encoding="utf-8")
        attest = text.split("\n  attest:\n", 1)[1]
        condition = attest.split("    if:", 1)[1].split("    runs-on:", 1)[0]
        assert "refs/heads/main" in condition
        assert "refs/heads/chatgpt/go-live-release-env-version" in condition
        assert "codex/aegis-shakedown" not in condition
