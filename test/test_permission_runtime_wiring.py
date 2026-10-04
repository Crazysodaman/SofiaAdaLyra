from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.capability.catalog import ToolCatalogCapability
from sofia.capability.model import Capability, CapabilityRequest
from sofia.capability.system import CapabilitySystem
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.matrix.privacy import MatrixPrivacyPlanner
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.integrations.capabilities import create_configured_integration_tools
from sofia.dev.approval import DevOperation
from sofia.dev.capability import (
    DevCandidateStore,
    DevToolService,
    create_dev_tool_bindings,
)
from sofia.dev.workflow import EngineeringCandidate
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.knowledge.capability import KnowledgeCapabilitySet
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.operator_stop import OperatorStopStore
from sofia.composition.authorization import create_capability_authorizer
from sofia.composition.root import compose
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.safe.permissions import PermissionStore
from sofia.safe.permission_capability import PermissionInspectionCapability
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


def test_permission_inspection_is_owner_private_and_reports_live_state(tmp_path):
    state = tmp_path / "sofia.db"
    store = PermissionStore(state)
    store.grant(
        "storage.mkdir",
        scope={"root_index": 0, "path": "docs"},
        grant_id="inspectable-grant",
    )
    capability = PermissionInspectionCapability(store)

    result = capability.execute(
        CapabilityRequest(
            capability=capability.capability,
            parameters={
                "__principal_id": "person:sparks",
                "__audience_id": "local:sparks",
                "__audience_kind": "private",
            },
            requested_scope=None,
            rationale="inspect my permission state",
        )
    )

    assert result["levels"]["1"] == "observe_read"
    assert result["standing_grants"][0]["grant_id"] == "inspectable-grant"
    assert result["private_adult"]["adult_external_delivery"] is False

    with pytest.raises(PermissionError, match="owner-only"):
        capability.execute(
            CapabilityRequest(
                capability=capability.capability,
                parameters={
                    "__principal_id": "principal:other",
                    "__audience_id": "private:other",
                    "__audience_kind": "private",
                },
                requested_scope=None,
                rationale="not the owner",
            )
        )


def test_level_five_cannot_be_enabled_by_legacy_standing_configuration(tmp_path):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=("permissions.grant",),
    )
    authorizer = create_capability_authorizer(
        runtime_provider=lambda: object(),
        configuration=configuration,
        operator_stop=OperatorStopStore(configuration.state_path),
    )
    request = CapabilityRequest(
        capability=Capability(
            "permissions.grant",
            "Attempt to expand Sofía authority.",
        ),
        parameters={"capability": "storage.delete"},
        requested_scope=None,
        rationale="must remain impossible for Sofía to self-authorize",
    )
    assert authorizer(request) is False


class _KnowledgeProbe:
    def __init__(self):
        self.calls = []

    def ingest_text(self, path, **kwargs):
        self.calls.append(("ingest_text", path, kwargs))
        return {"path": path}

    def ingest_pdf(self, path, **kwargs):
        self.calls.append(("ingest_pdf", path, kwargs))
        return {"path": path}

    def write_document(self, path, content, overwrite=False):
        self.calls.append(("write_document", path, content, overwrite))
        return {"path": path}


def test_level_two_knowledge_ingest_needs_no_approval(tmp_path):
    state = tmp_path / "sofia.db"
    probe = _KnowledgeProbe()
    permissions = PermissionStore(state)
    capabilities = KnowledgeCapabilitySet(
        probe,
        approval_verifier=ExecutionApprovalVerifier(state),
        permission_store=permissions,
    )
    capability = next(
        item
        for item in capabilities.capabilities()
        if item.name == "knowledge.ingest.text"
    )
    result = capabilities.execute(
        CapabilityRequest(
            capability=capability,
            parameters={"path": "docs/readme.txt"},
            requested_scope=None,
            rationale="safe autonomous knowledge indexing",
        )
    )
    assert result == {"path": "docs/readme.txt"}
    assert probe.calls[0][0] == "ingest_text"


def test_level_three_knowledge_write_honors_exact_standing_scope(tmp_path):
    state = tmp_path / "sofia.db"
    probe = _KnowledgeProbe()
    permissions = PermissionStore(state)
    capabilities = KnowledgeCapabilitySet(
        probe,
        approval_verifier=ExecutionApprovalVerifier(state),
        permission_store=permissions,
    )
    capability = next(
        item
        for item in capabilities.capabilities()
        if item.name == "knowledge.document.write"
    )
    request = CapabilityRequest(
        capability=capability,
        parameters={
            "path": "docs/permission-notes.md",
            "content": "safe",
            "overwrite": False,
        },
        requested_scope=None,
        rationale="write one approved documentation file",
    )

    with pytest.raises(PermissionError, match="approval_id"):
        capabilities.execute(request)

    permissions.grant(
        "knowledge.document.write",
        scope={
            "path": "docs/permission-notes.md",
            "content": "safe",
            "overwrite": False,
        },
        grant_id="knowledge-doc-write",
    )
    result = capabilities.execute(request)
    assert result == {"path": "docs/permission-notes.md"}

    other = CapabilityRequest(
        capability=capability,
        parameters={
            "path": "docs/other.md",
            "content": "safe",
            "overwrite": False,
        },
        requested_scope=None,
        rationale="outside the standing grant",
    )
    with pytest.raises(PermissionError, match="approval_id"):
        capabilities.execute(other)


def test_dev_build_is_safe_autonomous_but_production_dev_changes_are_not():
    class ApprovalProbe:
        def consume(self, **_kwargs):
            raise AssertionError("safe-autonomous build must not consume approval")

    service = DevToolService.__new__(DevToolService)
    service.approval_verifier = ApprovalProbe()

    service._authorize(
        DevOperation.BUILD,
        {"proposal_id": "candidate-1"},
    )

    with pytest.raises(PermissionError, match="approval_id"):
        service._authorize(
            DevOperation.APPLY,
            {"proposal_id": "candidate-1"},
        )


def test_dev_candidate_history_round_trips_from_durable_state(tmp_path):
    state = tmp_path / "sofia.db"
    store = DevCandidateStore(SQLiteStatePlane(state))
    candidate = EngineeringCandidate(
        proposal_id="candidate-history",
        base_sha="a" * 40,
        patch="diff --git a/x b/x\n",
        changed_paths=("x",),
        allowed_paths=("x",),
        tests_passed=True,
    )
    store.put(candidate)

    service = DevToolService.__new__(DevToolService)
    service.store = store

    listed = service.candidates()
    inspected = service.candidate("candidate-history")

    assert listed[0]["proposal_id"] == "candidate-history"
    assert listed[0]["tests_passed"] is True
    assert "patch" not in listed[0]
    assert inspected["patch"] == candidate.patch


def test_dev_candidate_history_tools_are_level_one_read_only():
    from sofia.safe.permissions import (
        PermissionLevel,
        capability_permission_policy,
    )

    bindings = {
        item.capability_name: item
        for item in create_dev_tool_bindings()
    }
    for capability in ("dev.candidates.list", "dev.candidate.get"):
        assert (
            capability_permission_policy(capability).level
            is PermissionLevel.OBSERVE_READ
        )
        schema = bindings[capability].definition.parameters
        assert "approval_id" not in schema["properties"]


def test_dev_build_tool_schema_does_not_require_or_offer_approval_id():
    bindings = {
        item.capability_name: item
        for item in create_dev_tool_bindings()
    }
    build = bindings["dev.build"].definition.parameters
    assert "approval_id" not in build["properties"]
    assert "approval_id" not in build["required"]

    for protected in ("dev.apply", "dev.rollback", "dev.commit", "dev.push"):
        schema = bindings[protected].definition.parameters
        assert "approval_id" in schema["properties"]
        assert "approval_id" in schema["required"]


def test_legacy_standing_configuration_cannot_authorize_level_three(tmp_path):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=("storage.mkdir",),
    )
    authorizer = create_capability_authorizer(
        runtime_provider=lambda: object(),
        configuration=configuration,
        operator_stop=OperatorStopStore(configuration.state_path),
    )
    request = CapabilityRequest(
        capability=Capability("storage.mkdir", "Create a directory."),
        parameters={"root_index": 0, "path": "legacy-bypass"},
        requested_scope=None,
        rationale="legacy config must not grant a mutation",
    )
    assert authorizer(request) is False


def test_runtime_ignores_legacy_mutating_standing_configuration(tmp_path):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=("storage.mkdir",),
    )
    runtime = compose(configuration)
    assert runtime.current_authority().can_use_capability("storage.mkdir") is False


def test_tool_catalog_reads_live_authority_provider():
    allowed = {"hardware.inspect"}
    system = CapabilitySystem(authorization_checker=lambda _request: True)
    hardware = Capability("hardware.inspect", "Read hardware.")
    system.register(hardware, lambda _request: {"ok": True})
    catalog = ToolCatalogCapability(system, lambda: tuple(allowed))
    system.register(catalog.capability, catalog.execute)

    request = CapabilityRequest(
        capability=catalog.capability,
        parameters={},
        requested_scope=None,
        rationale="inspect tools",
    )
    first = {item["name"]: item for item in catalog.execute(request)}
    assert first["hardware.inspect"]["standing_authorized"] is True

    allowed.clear()
    second = {item["name"]: item for item in catalog.execute(request)}
    assert second["hardware.inspect"]["standing_authorized"] is False
