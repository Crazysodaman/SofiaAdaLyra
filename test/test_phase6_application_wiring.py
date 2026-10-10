from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.life import SelfDirectedLifeCoordinator


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run]


def configuration(tmp_path):
    project = Path(__file__).resolve().parents[1]
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["witty","warm","skeptical"],'
        '"communication_style":"Direct and evidence-minded."}', encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=project / "src/sofia/constitution/constitution.md",
        constitution_hash_path=project / "src/sofia/constitution/constitution.sha256",
        identity_path=project / "src/sofia/identity/identity.json",
        personality_path=personality,
        avatar_path=project / "src/sofia/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=project,
    )


def test_application_owns_one_project_forge_and_creative_capability(tmp_path):
    config = configuration(tmp_path)
    application = SofiaApplication(config)
    try:
        assert isinstance(application.life, SelfDirectedLifeCoordinator)
        assert application.life.path == config.state_path
        assert application.life.goals is application.goals
        assert application.life.creative_store is application.creative_store
        assert application.life.world is application.world
        assert "creative.artifact.create" in application.runtime.capability_system.capability_names()
        application.start()
        assert "independent_life" in application.background_coordinator._tasks
    finally:
        application.shutdown()


def test_life_state_survives_application_restart_without_second_database(tmp_path):
    config = configuration(tmp_path)
    first = SofiaApplication(config)
    evidence = first.life.record_observation(
        kind="curiosity", source="test:application",
        assertion="A restart-persistent interest observation exists.",
        now=datetime.now(timezone.utc),
    )
    first.life.revise_interest(
        name="restart-continuity", context="research", strength=0.7,
        confidence=0.9, reason="Observed before restart.",
        evidence_refs=(evidence,),
        now=datetime.now(timezone.utc),
    )
    before = first.life.store.experiences(
        audience_id="local:text", include_private=True,
    )
    first.start()
    first.shutdown()

    second = SofiaApplication(config)
    try:
        interests = second.life.store.active_interests(audience_id="local:text")
        assert [item.name for item in interests] == ["restart-continuity"]
        assert second.life.path == second.chat_state_path == config.state_path
        assert second.life.store.experiences(
            audience_id="local:text", include_private=True,
        ) == before
    finally:
        second.start()
        second.shutdown()
