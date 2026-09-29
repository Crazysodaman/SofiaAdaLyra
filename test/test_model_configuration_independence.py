from pathlib import Path

from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import (
    CognitiveRoutingConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.config.model_catalog import (
    DEFAULT_PROVIDER_MODEL,
    RECOMMENDED_PRIMARY_MODEL,
    RECOMMENDED_SECONDARY_MODEL,
    known_local_model_names,
)
from sofia.config.user_settings import RuntimeUserSettings


PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_ROOT = PROJECT_ROOT / "src" / "sofia"
CATALOG_PATH = SOURCE_ROOT / "config" / "model_catalog.py"


def test_known_model_literals_are_centralized_in_model_catalog():
    literals = set(known_local_model_names())
    offenders = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if path == CATALOG_PATH:
            continue
        text = path.read_text(encoding="utf-8-sig")
        for literal in literals:
            if literal in text:
                offenders.append((str(path.relative_to(PROJECT_ROOT)), literal))

    assert offenders == []


def test_model_catalog_is_suggestions_not_an_allow_list():
    settings = RuntimeUserSettings(
        provider_model="vendor/custom-main:11b",
        cognitive_primary_model="vendor/custom-primary:17b",
        cognitive_secondary_model="vendor/custom-open:3b",
    )

    assert settings.provider_model == "vendor/custom-main:11b"
    assert settings.cognitive_primary_model == "vendor/custom-primary:17b"
    assert settings.cognitive_secondary_model == "vendor/custom-open:3b"
    assert RECOMMENDED_PRIMARY_MODEL in known_local_model_names()
    assert RECOMMENDED_SECONDARY_MODEL in known_local_model_names()



def test_effective_model_selection_uses_roles_not_concrete_model_names(
    tmp_path,
):
    routing = CognitiveRoutingConfiguration(
        enabled=True,
        primary=ProviderConfiguration(
            provider="ollama",
            model="vendor/owner-primary:anything",
        ),
        secondary=ProviderConfiguration(
            provider="ollama",
            model="vendor/owner-secondary:anything",
        ),
    )
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="ollama",
            model="vendor/legacy:anything",
        ),
        filesystem_root=tmp_path,
        routing=routing,
    )

    selection = CognitiveModelSelection.from_configuration(configuration)

    assert selection.routing_enabled is True
    assert selection.primary.model == "vendor/owner-primary:anything"
    assert selection.secondary is not None
    assert selection.secondary.model == "vendor/owner-secondary:anything"
    assert selection.model_names == (
        "vendor/owner-primary:anything",
        "vendor/owner-secondary:anything",
    )
