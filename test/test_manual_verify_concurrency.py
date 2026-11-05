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
