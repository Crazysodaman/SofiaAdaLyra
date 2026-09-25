import pytest
from sofia.dev import ChangeProposal, ReviewState, inspect


def proposal(**kw):
    fields = dict(proposal_id="fix-001", base_sha="a" * 40,
                  affected_paths=("src/sofia/interaction/chat.py",),
                  source_evidence_ids=("test-log-12",), description="Fix observed failure",
                  test_plan="Run targeted pytest and full suite", rollback_plan="Revert exact commit")
    fields.update(kw)
    return ChangeProposal(**fields)


def test_ordinary_path_only_requires_review_not_approval():
    r, = inspect(proposal())
    assert r.state is ReviewState.REQUIRES_REVIEW
    assert "human diff" in r.reason


@pytest.mark.parametrize("path", ["src/sofia/constitution/base.py", "src/sofia/identity/name.py", "src/sofia/data/avatar.json", ".git/config", ".env", ".env.local", "state/sofia.db", "backups/db", "secret/token", "secrets/access", "credentials/a", "folder/key.pem", "folder/data.sqlite", "folder/db.sqlite3", "folder/archive.db", "SRC/SOFIA/IDENTITY/model.py"])
def test_protected_path_blocked(path):
    assert inspect(proposal(affected_paths=(path,)))[0].state is ReviewState.BLOCKED_PROTECTED


@pytest.mark.parametrize("path", ["", "../foo", "/etc/passwd", "src/../secrets/a", "a//b", "a/./b", "a/", "C:/a", "a\\b", "a\x00b"])
def test_unsafe_path_cannot_pass(path):
    if path == "":
        with pytest.raises(ValueError):
            proposal(affected_paths=(path,))
    else:
        assert inspect(proposal(affected_paths=(path,)))[0].state is ReviewState.INVALID_PATH


def test_mixed_paths_are_all_reported_not_partially_approved():
    result = inspect(proposal(affected_paths=("src/app.py", "state/sofia.db")))
    assert tuple(item.state for item in result) == (ReviewState.REQUIRES_REVIEW, ReviewState.BLOCKED_PROTECTED)


@pytest.mark.parametrize("bad", [dict(base_sha="branch"), dict(base_sha="A" * 40), dict(base_sha="a" * 39), dict(affected_paths=()), dict(affected_paths=("a", "a")), dict(source_evidence_ids=()), dict(source_evidence_ids=("",)), dict(description=" "), dict(test_plan=""), dict(rollback_plan=""), dict(proposal_id="")])
def test_incomplete_proposals_rejected(bad):
    with pytest.raises(ValueError):
        proposal(**bad)


def test_invalid_proposal_object_rejected():
    with pytest.raises(TypeError):
        inspect("edit everything")


def test_no_mutating_api():
    from sofia import dev
    assert set(dev.__all__) == {"ChangeProposal", "ReviewFinding", "ReviewState", "inspect"}
    assert not hasattr(dev, "execute")
