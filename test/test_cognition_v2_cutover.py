"""Production cutover checks: one semantic planner and one completed trace."""
from pathlib import Path

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


ROOT = Path(__file__).parent.parent
RETIRED_IMPORTS = (
    "cognition.matrix.classifier",
    "cognition.matrix.coordinator",
    "cognition.matrix.defaults",
    "cognition.matrix.routing_plan",
)


def _configuration(tmp_path):
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["direct"],'
        '"communication_style":"Clear and direct."}',
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=ROOT / "src/sofia/constitution/constitution.md",
        constitution_hash_path=ROOT / "src/sofia/constitution/constitution.sha256",
        identity_path=ROOT / "src/sofia/identity/identity.json",
        personality_path=personality,
        avatar_path=ROOT / "src/sofia/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=ROOT,
    )


def test_live_source_does_not_import_retired_semantic_planners():
    retired_files = {
        "classifier.py", "coordinator.py", "defaults.py", "routing_plan.py",
    }
    offenders = []
    for path in (ROOT / "src/sofia").rglob("*.py"):
        if path.parent.name == "matrix" and path.name in retired_files:
            continue
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in RETIRED_IMPORTS):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
    for filename in retired_files:
        assert not (ROOT / "src/sofia/cognition/matrix" / filename).exists()


def test_application_uses_v2_plan_and_writes_one_completed_trace(tmp_path):
    application = SofiaApplication(_configuration(tmp_path))
    application.start()
    try:
        application.conversation.respond("How are you?")
        assert not hasattr(application.conversation, "_matrix_coordinator")
        assert application.conversation.cognitive_plan is not None
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.turn.schema_version == 2
        assert trace.shadow is False
    finally:
        application.shutdown()
