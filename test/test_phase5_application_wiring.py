from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_ops, pytest.mark.pkg_interact]


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


def test_application_owns_phase5_services_and_world_survives_restart(tmp_path):
    config = configuration(tmp_path)
    first = SofiaApplication(config)
    spaces = first.world.list_spaces("sofia", "local:text")
    assert len(spaces) == 3
    assert first.dependency_registry.get("runtime.python").dependency_id == "runtime.python"
    assert first.creative_store.path == config.state_path
    first.start()
    first.shutdown()

    second = SofiaApplication(config)
    try:
        assert second.world.list_spaces("sofia", "local:text") == spaces
        assert second.preferences.path == config.state_path
        assert second.nicknames.path == config.state_path
        assert second.dependency_evidence.path == config.state_path
    finally:
        second.start()
        second.shutdown()
