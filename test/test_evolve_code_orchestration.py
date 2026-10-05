from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.application.evolution import SofiaEvolutionService
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.dev.capability import DevToolService
from sofia.evolve.code import CodeEvolutionProposal
from sofia.evolve.lifecycle import EvolutionOutcome, EvolutionProposalStatus
from sofia.evolve.lifecycle import EvolutionLifecycleStore
from sofia.evolve.orchestrator import CodeEvolutionOrchestrator
from sofia.run.release_rollout import ReleaseRolloutJournal, ReleaseRolloutResult
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)


def configuration(tmp_path):
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "state.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
    )


class FakeDevService(DevToolService):
    def __init__(self):
        self.calls = []

    def build(self, parameters):
        self.calls.append(("build", parameters))
        return {
            "proposal_id": parameters["proposal_id"],
            "base_sha": parameters["base_sha"],
            "changed_paths": ("src/sofia/evolve/example.py",),
            "allowed_paths": tuple(parameters["allowed_paths"]),
            "tests_passed": True,
            "patch": "diff --git a/example b/example\n",
        }

    def apply(self, parameters):
        self.calls.append(("apply", parameters))
        return {"proposal_id": parameters["proposal_id"], "changed_paths": ("src/sofia/evolve/example.py",)}

    def commit(self, parameters):
        self.calls.append(("commit", parameters))
        return {"proposal_id": parameters["proposal_id"], "commit_sha": "b" * 40}

    def rollback(self, parameters):
        self.calls.append(("rollback", parameters))
        return {"proposal_id": parameters["proposal_id"], "rolled_back": True}


class FakeVerifier:
    def __init__(self, accepted=True):
        self.accepted = accepted

    def verify(self, *, expected_paths):
        return {
            "phase": "candidate",
            "git_revision": "a" * 40,
            "tracked_tree_clean": False,
            "accepted": self.accepted,
            "commands": [
                {
                    "name": "pytest",
                    "returncode": 0 if self.accepted else 1,
                }
            ],
            "reviewed_changed_paths": list(expected_paths),
        }


def service_with_evidence(tmp_path):
    config = configuration(tmp_path)
    service = SofiaEvolutionService(
        configuration=config,
        state_plane=SQLiteStatePlane(config.state_path),
    )
    service.record_evidence(
        evidence_id="failure-1",
        kind="regression",
        source_ref="test:failure-1",
        summary="A repeated regression was observed.",
        payload={"failed": True},
        observed_at=NOW,
        recorded_at=NOW,
    )
    return service


def propose(service, proposal_id="code-1", allowed_paths=("src/sofia/evolve",)):
    return service.propose_code(
        proposal_id=proposal_id,
        base_sha="a" * 40,
        prompt="Repair the observed regression without widening scope.",
        allowed_paths=allowed_paths,
        tests=("pytest -q test/test_evolve_code_orchestration.py",),
        evidence_ids=("failure-1",),
        reason="The regression has durable reproduction evidence.",
        rollback_plan="Rollback the exact candidate patch.",
        success_metric="Candidate verification gate is accepted.",
        now=NOW,
        ttl=timedelta(days=1),
    )


def test_code_proposal_is_canonical_and_rejects_overlapping_open_scope(tmp_path):
    service = service_with_evidence(tmp_path)
    record = propose(service)
    restored = service.lifecycle.proposal_object(record.proposal_id)

    assert isinstance(restored, CodeEvolutionProposal)
    assert restored.allowed_paths == ("src/sofia/evolve",)
    with pytest.raises(RuntimeError, match="overlaps"):
        propose(
            service,
            proposal_id="code-2",
            allowed_paths=("src/sofia/evolve/lifecycle.py",),
        )


def test_code_candidate_runs_build_verify_commit_activation_and_outcome(tmp_path):
    service = service_with_evidence(tmp_path)
    propose(service)
    dev = FakeDevService()
    orchestrator = CodeEvolutionOrchestrator(
        lifecycle=service.lifecycle,
        dev_service=dev,
        verifier=FakeVerifier(True),
    )

    built = orchestrator.build_candidate("code-1", now=NOW + timedelta(minutes=1))
    assert built["evidence_id"] == "dev-candidate:code-1"
    assert service.proposal("code-1").status is EvolutionProposalStatus.CANDIDATE_BUILT

    orchestrator.apply_candidate(
        "code-1",
        approval_id="apply-approval",
        now=NOW + timedelta(minutes=2),
    )
    verified = orchestrator.verify_candidate("code-1", now=NOW + timedelta(minutes=3))
    assert verified["accepted"] is True
    assert service.proposal("code-1").status is EvolutionProposalStatus.VERIFIED

    committed = orchestrator.commit_candidate(
        "code-1",
        approval_id="commit-approval",
        message="Fix observed regression",
        now=NOW + timedelta(minutes=4),
    )
    assert committed["commit_sha"] == "b" * 40
    assert service.proposal("code-1").status is EvolutionProposalStatus.COMMITTED_PENDING_RELEASE

    ReleaseRolloutJournal(service.state_plane).record(
        ReleaseRolloutResult(
            rollout_id="rollout-pending",
            release_id="release-1",
            manifest_sha256="c" * 64,
            status="canary_accepted",
            events=(),
        ),
        now=NOW + timedelta(minutes=5),
    )
    with pytest.raises(RuntimeError, match="has not completed"):
        service.mark_release_effective(
            "code-1",
            rollout_id="rollout-pending",
            now=NOW + timedelta(minutes=5),
        )

    ReleaseRolloutJournal(service.state_plane).record(
        ReleaseRolloutResult(
            rollout_id="rollout-1",
            release_id="release-1",
            manifest_sha256="c" * 64,
            status="completed",
            events=(),
        ),
        now=NOW + timedelta(minutes=5),
    )
    service.mark_release_effective(
        "code-1",
        rollout_id="rollout-1",
        now=NOW + timedelta(minutes=5),
    )
    service.record_evidence(
        evidence_id="outcome-1",
        kind="post-release-verification",
        source_ref="release:b" + "b" * 39,
        summary="Post-release verification remained accepted.",
        payload={"accepted": True},
        observed_at=NOW + timedelta(minutes=6),
        recorded_at=NOW + timedelta(minutes=6),
    )
    service.record_outcome(
        "code-1",
        outcome=EvolutionOutcome.IMPROVED,
        evidence_id="outcome-1",
        notes="The release met the declared success metric.",
        measured_at=NOW + timedelta(minutes=6),
    )
    assert service.proposal("code-1").status is EvolutionProposalStatus.ACCEPTED
    assert [name for name, _ in dev.calls] == ["build", "apply", "commit"]


def test_failed_candidate_verification_requires_approved_rollback(tmp_path):
    service = service_with_evidence(tmp_path)
    propose(service)
    dev = FakeDevService()
    orchestrator = CodeEvolutionOrchestrator(
        lifecycle=service.lifecycle,
        dev_service=dev,
        verifier=FakeVerifier(False),
    )
    orchestrator.build_candidate("code-1", now=NOW + timedelta(minutes=1))
    orchestrator.apply_candidate(
        "code-1",
        approval_id="apply-approval",
        now=NOW + timedelta(minutes=2),
    )

    evidence = orchestrator.verify_candidate("code-1", now=NOW + timedelta(minutes=3))
    assert evidence["accepted"] is False
    assert service.proposal("code-1").status is EvolutionProposalStatus.ROLLBACK_REQUIRED

    orchestrator.rollback_candidate(
        "code-1",
        approval_id="rollback-approval",
        now=NOW + timedelta(minutes=4),
    )
    assert service.proposal("code-1").status is EvolutionProposalStatus.ROLLED_BACK
    assert [name for name, _ in dev.calls] == ["build", "apply", "rollback"]


def test_lifecycle_migrates_original_two_kind_constraint(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE evolve_proposals (
                proposal_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK(kind IN ('revision','amendment')),
                target TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                proposed_content TEXT NOT NULL,
                success_metric TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                activated_at TEXT
            )
            """
        )
        db.execute(
            "INSERT INTO evolve_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-1",
                "revision",
                "configuration:provider.model",
                "f" * 64,
                "{}",
                '"model"',
                "Existing behavior remains stable.",
                "accepted",
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

    store = EvolutionLifecycleStore(path)
    with sqlite3.connect(path) as db:
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE name='evolve_proposals'"
        ).fetchone()[0]
    assert "'code'" in schema
    assert tuple(item.proposal_id for item in store.list_proposals()) == ("legacy-1",)
