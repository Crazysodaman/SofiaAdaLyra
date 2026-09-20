"""Install Batch G3 provider-path tests and Engineering 22C peer knowledge.

Run from SofiaAdaLyra repository root. --check previews without editing.
Creates four NEW files only; no commits, pushes, network access, or state edits.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
from pathlib import Path

REQUIRES = (
    "AGENTS.MD",
    "src/sofia/distributed/model.py",
    "src/sofia/distributed/identity.py",
    "src/sofia/personality/expression.py",
    "test/test_personality_expression_boundary.py",
    "test/test_distributed_identity.py",
)

FILES = {
    "src/sofia/distributed/knowledge.py": '''"""Batch 22C: in-memory, evidence-based knowledge about enrolled peers.

This is NOT network discovery, authentication, liveness, or authorization.
An UNREACHABLE observation records a failed attempt, not an offline host.
Enrollment is a human-supplied identity/key pin, not proof of possession.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from sofia.distributed.identity import NodeEnrollment, NodeIdentityRegistry
from sofia.distributed.model import NodeObservation, NodeReachability


class PeerEvidenceFreshness(str, Enum):
    UNOBSERVED = "unobserved"
    CURRENT = "current"
    STALE = "stale"
    CLOCK_SKEW = "clock_skew"


@dataclass(frozen=True)
class PeerKnowledgeSnapshot:
    """Immutable view; neither reachability nor enrollment confers authority."""

    enrollment: NodeEnrollment
    observation: NodeObservation | None
    freshness: PeerEvidenceFreshness

    @property
    def reachability(self) -> NodeReachability:
        if self.observation is None or self.freshness is not PeerEvidenceFreshness.CURRENT:
            return NodeReachability.UNKNOWN
        return self.observation.reachability


class PeerKnowledge:
    """Records observations only for enrolled node IDs; never performs probes."""

    def __init__(self, max_age: timedelta) -> None:
        if not isinstance(max_age, timedelta):
            raise TypeError("max_age must be a timedelta.")
        if max_age <= timedelta(0):
            raise ValueError("max_age must be positive.")
        self._max_age = max_age
        self._identity = NodeIdentityRegistry()
        self._observations: dict[UUID, NodeObservation] = {}

    def enroll(self, record: NodeEnrollment) -> None:
        self._identity.enroll(record)

    def record(self, observation: NodeObservation) -> None:
        if not isinstance(observation, NodeObservation):
            raise TypeError("observation must be a NodeObservation.")
        if self._identity.get(observation.node_id) is None:
            raise ValueError("Cannot record an observation for an unenrolled node.")
        previous = self._observations.get(observation.node_id)
        if previous is not None:
            if observation.observed_at < previous.observed_at:
                raise ValueError("Older peer evidence cannot replace newer evidence.")
            if observation.observed_at == previous.observed_at:
                if observation == previous:
                    return  # Exact duplicate is idempotent.
                raise ValueError("Conflicting peer evidence has an equal timestamp.")
        self._observations[observation.node_id] = observation

    def snapshot(self, node_id: UUID, *, now: datetime) -> PeerKnowledgeSnapshot | None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID.")
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime.")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")
        enrollment = self._identity.get(node_id)
        if enrollment is None:
            return None
        observation = self._observations.get(node_id)
        if observation is None:
            freshness = PeerEvidenceFreshness.UNOBSERVED
        elif observation.observed_at > now:
            freshness = PeerEvidenceFreshness.CLOCK_SKEW
        elif now - observation.observed_at > self._max_age:
            freshness = PeerEvidenceFreshness.STALE
        else:
            freshness = PeerEvidenceFreshness.CURRENT
        return PeerKnowledgeSnapshot(enrollment, observation, freshness)
''',
    "test/test_distributed_peer_knowledge.py": '''"""Engineering 22C deterministic peer evidence contracts; no network calls."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.knowledge import PeerEvidenceFreshness, PeerKnowledge
from sofia.distributed.model import DistributedNode, NodeObservation, NodeReachability


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def enrolled(name="Artemis"):
    return NodeEnrollment(
        node=DistributedNode(uuid4(), name),
        public_key_sha256=fingerprint_public_key(name.encode()),
        provisioned_at=NOW,
        recorded_by="operator",
    )


def observed(record, when=NOW, reachability=NodeReachability.REACHABLE,
             evidence=("TCP endpoint answered",)):
    return NodeObservation(
        node_id=record.node.node_id,
        observed_at=when,
        source="explicit authorized inspection",
        reachability=reachability,
        evidence=evidence,
    )


def test_unobserved_enrollment_has_unknown_reachability():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    view = peers.snapshot(record.node.node_id, now=NOW)
    assert view.enrollment is record
    assert view.observation is None
    assert view.freshness is PeerEvidenceFreshness.UNOBSERVED
    assert view.reachability is NodeReachability.UNKNOWN
    assert peers.snapshot(uuid4(), now=NOW) is None


def test_recent_observation_is_current_but_not_authority():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    evidence = observed(record)
    peers.record(evidence)
    view = peers.snapshot(record.node.node_id, now=NOW + timedelta(minutes=5))
    assert view.freshness is PeerEvidenceFreshness.CURRENT
    assert view.observation is evidence
    assert view.reachability is NodeReachability.REACHABLE
    assert not hasattr(view, "authorized")
    assert not hasattr(peers, "execute")
    with pytest.raises(FrozenInstanceError):
        view.freshness = PeerEvidenceFreshness.STALE


def test_stale_reachability_falls_back_to_unknown_without_erasing_evidence():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    evidence = observed(record)
    peers.record(evidence)
    view = peers.snapshot(record.node.node_id, now=NOW + timedelta(minutes=5, seconds=1))
    assert view.freshness is PeerEvidenceFreshness.STALE
    assert view.reachability is NodeReachability.UNKNOWN
    assert view.observation is evidence


def test_unreachable_is_not_offline():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    peers.record(observed(record, reachability=NodeReachability.UNREACHABLE,
                          evidence=("TCP timeout",)))
    view = peers.snapshot(record.node.node_id, now=NOW)
    assert view.reachability is NodeReachability.UNREACHABLE
    assert "offline" not in {state.value for state in NodeReachability}


def test_unknown_identity_cannot_insert_observation():
    peers = PeerKnowledge(timedelta(minutes=5))
    with pytest.raises(ValueError, match="unenrolled"):
        peers.record(observed(enrolled()))


def test_old_or_conflicting_observations_cannot_overwrite_latest():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    recent = observed(record, NOW)
    peers.record(recent)
    peers.record(recent)
    with pytest.raises(ValueError, match="Older"):
        peers.record(observed(record, NOW - timedelta(seconds=1)))
    with pytest.raises(ValueError, match="Conflicting"):
        peers.record(observed(record, NOW, NodeReachability.UNREACHABLE, ("fail",)))
    assert peers.snapshot(record.node.node_id, now=NOW).observation is recent


def test_clock_skew_cannot_report_future_evidence_as_current():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    peers.record(observed(record, NOW + timedelta(seconds=5)))
    view = peers.snapshot(record.node.node_id, now=NOW)
    assert view.freshness is PeerEvidenceFreshness.CLOCK_SKEW
    assert view.reachability is NodeReachability.UNKNOWN


@pytest.mark.parametrize("max_age", [timedelta(0), timedelta(seconds=-1), None, 30])
def test_invalid_freshness_window_rejected(max_age):
    with pytest.raises((TypeError, ValueError)):
        PeerKnowledge(max_age)


def test_snapshot_requires_timezone_aware_clock():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    with pytest.raises(ValueError, match="timezone-aware"):
        peers.snapshot(record.node.node_id, now=datetime(2026, 9, 20, 12))


def test_enrollment_conflicts_remain_rejected():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    with pytest.raises(ValueError, match="already enrolled"):
        peers.enroll(record)
''',
    "test/test_personality_provider_path.py": '''"""G3: deterministic assembler-to-LLM-provider evidence, NOT LLM fidelity."""
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.provider import LLMProvider
from sofia.config.model import ProviderConfiguration
from sofia.personality.model import PersonalityProfile


class RecordingProvider(LLMProvider):
    def __init__(self, content="Provider says hello."):
        self.requests = []
        self.content = content

    def respond(self, request):
        self.requests.append(request)
        return CognitiveResponse(content=self.content)


def test_saved_personality_crosses_engine_to_provider_unchanged():
    profile = PersonalityProfile(
        name="Sofía", traits=("curious", "precise"),
        communication_style="Answer concisely.",
        embodiment_guidance="Optional representational fox expression.",
    )
    user = CognitiveMessage(role=CognitiveRole.USER, content="Who are you?")
    source = CognitiveRequest(messages=(user,))
    assembled = CognitiveContextAssembler().assemble(
        CognitiveContext(request=source, personality=profile)
    )
    provider = RecordingProvider()
    engine = LLMCognitiveEngine(
        ProviderConfiguration(provider="test-llm", model="recording"), provider
    )
    result = engine.respond(assembled)
    assert len(provider.requests) == 1
    assert provider.requests[0] is assembled
    assert provider.requests[0].messages[-1] is user
    system = provider.requests[0].messages[0].content
    assert system.count("PERSONALITY EXPRESSION BOUNDARY") == 1
    assert "Traits: curious, precise" in system
    assert "Communication style: Answer concisely." in system
    assert "Embodiment guidance: Optional representational fox expression." in system
    assert result.content == "Provider says hello."


def test_provider_response_is_observed_not_falsely_certified_as_personality():
    profile = PersonalityProfile(name="Sofía", traits=("playful",))
    assembled = CognitiveContextAssembler().assemble(CognitiveContext(
        request=CognitiveRequest(messages=(CognitiveMessage(
            role=CognitiveRole.USER, content="Who are you?"),)),
        personality=profile,
    ))
    provider = RecordingProvider("I am a generic AI assistant.")
    engine = LLMCognitiveEngine(
        ProviderConfiguration(provider="test-llm", model="recording"), provider
    )
    assert engine.respond(assembled).content == "I am a generic AI assistant."
    # This confirms prompt delivery only; model personality fidelity is unverified.
''',
    "docs/development/batch-g3-and-22c.md": '''# Batch G3 and Engineering 22C checkpoint

**Status: implementation delivered for local verification; full batches remain open.**

## G3: actual provider-path evidence

`test/test_personality_provider_path.py` assembles a supplied personality and
uses a recording `LLMProvider` with the actual `LLMCognitiveEngine`. It checks
that the system message and original user message reach the provider intact.
A second case deliberately returns a generic response: it documents that
prompt delivery does **not** establish personality fidelity. Real-model
behavior needs separate, bounded live testing; do not call G complete on the
strength of mocked-provider results.

## 22C: peer knowledge

`sofia.distributed.knowledge.PeerKnowledge` is an in-memory registry of
observations for **already enrolled** nodes. It keeps the most recent immutable
observation and rejects unknown nodes, older evidence, and conflicting records
with identical timestamps. A caller-supplied timezone-aware `now` and
explicit positive `max_age` yield CURRENT, STALE, UNOBSERVED, or CLOCK_SKEW.
Stale, future, and absent observations expose UNKNOWN effective reachability;
original evidence remains inspectable. An observed failed connection does
not prove the machine is offline. Neither enrollment nor observation grants
network access, identity proof, or authorization.

This slice does not yet persist observations, inspect the LAN, discover peers,
verify remote credentials, or execute operations. Those remain later gates.

## Suggested local verification

```powershell
pytest -q test/test_personality.py test/test_personality_embodiment_contract.py test/test_personality_pipeline.py test/test_personality_expression_boundary.py test/test_personality_provider_path.py test/test_distributed_node_contract.py test/test_distributed_identity.py test/test_distributed_peer_knowledge.py
git diff --check
git status --short
```

Run the broader `pytest -q -m "not integration"` at the combined checkpoint;
record actual results and distinguish skipped/deselected live tests. Review
and explicitly stage only intended files, not state databases, logs, or
one-time installer scripts.
''',
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_root_ok() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == Path.cwd().resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify prerequisites; no edits")
    args = parser.parse_args()
    if not _git_root_ok():
        raise SystemExit("Run from the SofiaAdaLyra repository root. No changes made.")
    missing = [name for name in REQUIRES if not Path(name).is_file()]
    if missing:
        raise SystemExit(f"Missing G1/G2 or 22A/22B prerequisites: {missing}. No changes made.")
    collisions = [name for name in FILES if Path(name).exists()]
    if collisions:
        raise SystemExit(f"Target already exists; refusing to overwrite: {collisions}. No changes made.")
    for name, content in FILES.items():
        if name.endswith(".py"):
            ast.parse(content, filename=name)
    print("Preflight OK. Four new files; no existing-file edits:")
    for name in FILES:
        print(f"  {name}")
    if args.check:
        print("--check: no files changed.")
        return
    written: list[Path] = []
    try:
        for name, content in FILES.items():
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as output:
                output.write(content)
            written.append(path)
    except Exception:
        for path in reversed(written):
            path.unlink(missing_ok=True)
        raise
    print("Installed G3 + 22C. No commits, pushes, network calls, or state edits.")


if __name__ == "__main__":
    main()
