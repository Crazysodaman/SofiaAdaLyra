from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from sofia.authorization.evaluator import (
    FilesystemAuthorizationEvaluator,
)
from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import CapabilityResultKind
from sofia.capability.proposal import CapabilityProposal
from sofia.codebase.codebase import CODEBASE_INSPECT_CAPABILITY
from sofia.composition.root import compose
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.runtime.model import RuntimeState


def create_configuration(
    tmp_path: Path,
) -> SofiaConfiguration:
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=(
            "codebase.inspect",
        ),
    )

    constitution_content = "# Constitution\n"

    configuration.constitution_path.write_text(
        constitution_content,
        encoding="utf-8",
    )

    constitution_hash = hashlib.sha256(
        constitution_content.encode("utf-8")
    ).hexdigest().upper()

    configuration.constitution_hash_path.write_text(
        constitution_hash,
        encoding="utf-8",
    )

    configuration.identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )

    configuration.personality_path.write_text(
        (
            '{"name": "Sofía Ada Lyra", '
            '"traits": ["rigorous"], '
            '"communication_style": "direct"}'
        ),
        encoding="utf-8",
    )

    configuration.avatar_path.write_text(
        (
            '{"subject": "Sofía Ada Lyra", '
            '"physical_self": {'
            '"form": "human", '
            '"additional_features": [], '
            '"measurements": {}, '
            '"appearance": {}, '
            '"anatomy": {}'
            '}, '
            '"available": {'
            '"computers": [], '
            '"robots": [], '
            '"avatars": []'
            '}, '
            '"current": {'
            '"computer": null, '
            '"robot": null, '
            '"avatar": null'
            '}}'
        ),
        encoding="utf-8",
    )

    return configuration


def authorize_filesystem(
    runtime,
) -> None:
    evaluator = FilesystemAuthorizationEvaluator(
        scope=runtime.configuration.filesystem_root,
    )

    authorization = evaluator.evaluate(
        "You are allowed to inspect your own files."
    )

    assert authorization is not None

    runtime.authorize_filesystem(
        authorization
    )


def create_started_runtime(
    tmp_path: Path,
):
    configuration = create_configuration(
        tmp_path
    )

    runtime = compose(configuration)

    runtime.start()

    assert runtime.state is RuntimeState.READY

    authorize_filesystem(runtime)

    return runtime


def make_proposal(
    requested_scope,
) -> CapabilityProposal:
    return CapabilityProposal(
        capability_name=CODEBASE_INSPECT_CAPABILITY.name,
        parameters={},
        rationale="Inspect the authorized Sofía codebase.",
        requested_scope=requested_scope,
    )


def test_composed_capability_allows_no_explicit_scope(
    tmp_path,
):
    runtime = create_started_runtime(tmp_path)

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal(None)
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence is not None


def test_composed_capability_allows_exact_authorized_scope(
    tmp_path,
):
    runtime = create_started_runtime(tmp_path)

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal(
            runtime.configuration.filesystem_root
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence is not None


def test_composed_capability_rejects_child_scope(
    tmp_path,
):
    runtime = create_started_runtime(tmp_path)

    child_scope = (
        runtime.configuration.filesystem_root
        / "child"
    )
    child_scope.mkdir()

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal(child_scope)
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_composed_capability_rejects_parent_scope(
    tmp_path,
):
    runtime = create_started_runtime(tmp_path)

    parent_scope = (
        runtime.configuration.filesystem_root.parent
    )

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal(parent_scope)
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_composed_capability_rejects_sibling_scope(
    tmp_path,
):
    runtime = create_started_runtime(tmp_path)

    sibling_scope = (
        tmp_path.parent
        / f"{tmp_path.name}-sibling"
    )
    sibling_scope.mkdir()

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal(sibling_scope)
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_composed_capability_rejects_non_path_scope(
    tmp_path,
):
    runtime = create_started_runtime(tmp_path)

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal("not-a-path")
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_composed_capability_rejects_scope_without_filesystem_authorization(
    tmp_path,
):
    configuration = create_configuration(
        tmp_path
    )

    runtime = compose(configuration)

    runtime.start()

    assert runtime.state is RuntimeState.READY
    assert runtime.filesystem_authorization is None

    gateway = CapabilityGateway(
        runtime.capability_system
    )

    result = gateway.execute(
        make_proposal(
            configuration.filesystem_root
        )
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None