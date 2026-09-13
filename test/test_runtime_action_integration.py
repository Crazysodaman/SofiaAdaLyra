from sofia.action.executor import TestActionExecutor
from sofia.action.system import ActionSystem
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.composition.root import compose


def test_composed_runtime_contains_action_system(tmp_path):
    constitution_path = tmp_path / "constitution.md"
    constitution_hash_path = tmp_path / "constitution.sha256"
    identity_path = tmp_path / "identity.json"
    personality_path = tmp_path / "personality.json"
    avatar_path = tmp_path / "avatar.json"
    state_path = tmp_path / "state.db"

    constitution_content = "Test constitution."
    constitution_path.write_text(
        constitution_content,
        encoding="utf-8",
    )

    import hashlib

    constitution_hash_path.write_text(
        hashlib.sha256(
            constitution_content.encode("utf-8")
        ).hexdigest().upper(),
        encoding="utf-8",
    )

    identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )

    personality_path.write_text(
        "{}",
        encoding="utf-8",
    )

    avatar_path.write_text(
        "{}",
        encoding="utf-8",
    )

    configuration = SofiaConfiguration(
        constitution_path=constitution_path,
        constitution_hash_path=constitution_hash_path,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=avatar_path,
        state_path=state_path,
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
    )

    runtime = compose(configuration)

    try:
        cognitive_system = runtime.cognitive_system

        assert cognitive_system.action_system is not None
        assert isinstance(
            cognitive_system.action_system,
            ActionSystem,
        )
        assert isinstance(
            cognitive_system.action_system.executor,
            TestActionExecutor,
        )
    finally:
        runtime.shutdown = lambda: None