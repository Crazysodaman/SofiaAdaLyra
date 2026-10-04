from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.capability.model import CapabilityRequest
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.matrix.privacy import MatrixPrivacyPlanner
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.integrations.capabilities import create_configured_integration_tools
from sofia.composition.root import compose
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.safe.permissions import PermissionStore
from sofia.social.principals import local_sparks_principal
from sofia.ui.control_center import MASTER_SETTINGS_SECTIONS
from sofia.ui.settings_window import _optional_expiry_minutes, _permission_scope


def _registration(registrations, name):
    return next(item for item in registrations if item.capability.name == name)


def test_permissions_section_is_exposed_in_master_tray_settings():
    assert "Permissions" in MASTER_SETTINGS_SECTIONS


def test_permission_ui_scope_parser_is_bounded_to_json_objects():
    assert _permission_scope("") == {}
    assert _permission_scope('{"container_id":"mealie"}') == {
        "container_id": "mealie"
    }
    with pytest.raises(ValueError, match="JSON object"):
        _permission_scope('["mealie"]')


def test_permission_ui_expiry_parser():
    assert _optional_expiry_minutes("") is None
    assert _optional_expiry_minutes("15") == 15
    with pytest.raises(ValueError, match="whole minutes"):
        _optional_expiry_minutes("1.5")


def test_level_two_sqlite_backup_runs_without_execution_approval(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE example(value TEXT)")
    tools = create_configured_integration_tools(
        filesystem_root=tmp_path,
        state_path=state,
    )
    registration = _registration(tools, "sqlite.state.backup")
    result = registration.handler(
        CapabilityRequest(
            capability=registration.capability,
            parameters={},
            requested_scope=None,
            rationale="routine safe backup",
        )
    )
    assert result["destination"]


def test_level_three_storage_write_needs_grant_or_exact_approval(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass
    tools = create_configured_integration_tools(
        filesystem_root=tmp_path,
        state_path=state,
    )
    registration = _registration(tools, "storage.mkdir")
    request = CapabilityRequest(
        capability=registration.capability,
        parameters={"root_index": 0, "path": "allowed"},
        requested_scope=None,
        rationale="create approved directory",
    )

    with pytest.raises(PermissionError, match="approval_id"):
        registration.handler(request)

    PermissionStore(state).grant(
        "storage.mkdir",
        scope={"root_index": 0, "path": "allowed"},
        grant_id="mkdir-allowed",
        now=datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc),
    )

    registration.handler(request)
    assert (tmp_path / "allowed").is_dir()

    with pytest.raises(PermissionError, match="approval_id"):
        registration.handler(
            CapabilityRequest(
                capability=registration.capability,
                parameters={"root_index": 0, "path": "different"},
                requested_scope=None,
                rationale="outside standing scope",
            )
        )


def test_level_three_tool_schema_allows_standing_grant_without_approval_id(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass
    tools = create_configured_integration_tools(
        filesystem_root=tmp_path,
        state_path=state,
    )
    registration = _registration(tools, "storage.mkdir")
    schema = registration.binding.definition.parameters
    assert "approval_id" in schema["properties"]
    assert "approval_id" not in schema["required"]


def test_level_four_tool_schema_requires_exact_approval(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass
    tools = create_configured_integration_tools(
        filesystem_root=tmp_path,
        state_path=state,
    )
    registration = _registration(tools, "storage.delete")
    schema = registration.binding.definition.parameters
    assert "approval_id" in schema["required"]


def test_private_chat_permission_gates_private_matrix_projection(tmp_path):
    state = tmp_path / "sofia.db"
    store = PermissionStore(state)
    principal = local_sparks_principal()
    planner = MatrixPrivacyPlanner(state)

    assert planner.plan(principal).allow_historical_private_scope is True

    store.set_private_adult_authority(
        private_chat=False,
        adult_chat=False,
        adult_avatar=False,
        adult_external_delivery=False,
    )
    plan = planner.plan(principal)
    assert plan.allow_historical_private_scope is False
    assert plan.allow_private_presentation_candidate is False


def test_adult_private_authority_is_projected_into_trusted_cognitive_context(tmp_path):
    state = tmp_path / "sofia.db"
    store = PermissionStore(state)
    authority = store.set_private_adult_authority(
        private_chat=True,
        adult_chat=True,
        adult_avatar=True,
        adult_external_delivery=False,
    )
    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="hello",
                ),
            ),
        ),
        principal=local_sparks_principal(),
        private_adult_authority=authority,
    )
    assembled = CognitiveContextAssembler().assemble(context)
    system_text = assembled.messages[0].content
    assert "PRIVATE / ADULT AUTHORITY" in system_text
    assert "Adult chat authorized: yes" in system_text
    assert "Adult/private avatar authorized: yes" in system_text
    assert "Adult/private external delivery authorized: no" in system_text


def test_runtime_tool_exposure_reads_new_standing_grants_without_restart(tmp_path):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=(),
    )
    runtime = compose(configuration)
    assert runtime.current_authority().can_use_capability("storage.mkdir") is False

    PermissionStore(configuration.state_path).grant(
        "storage.mkdir",
        scope={"root_index": 0, "path": "docs"},
        grant_id="live-storage-grant",
    )

    assert runtime.current_authority().can_use_capability("storage.mkdir") is True
