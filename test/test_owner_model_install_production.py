"""Production owner model installation via canonical SAFE, tests not executed."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore
from sofia.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.safe.operator_stop import OperatorStopStore
from sofia.ui.settings_service import install_approved_configured_model

pytestmark = pytest.mark.pkg_safe
MODEL = "owner-reviewed/primary:9b"
HOST = "venus-local-host"


class ObservedOllama:
    def __init__(self):
        self.installed = set()
        self.pulls = []
    def models(self):
        return {"models": [{"name": name} for name in sorted(self.installed)]}
    def running(self):
        return {"models": []}
    def pull(self, name):
        self.pulls.append(name)
        self.installed.add(name)


def setup(tmp_path, monkeypatch):
    import sofia.integrations.ollama as ollama
    import sofia.machine.discovery as discovery
    from types import SimpleNamespace
    monkeypatch.setattr(
        discovery, "create_machine_discovery",
        lambda: SimpleNamespace(
            discover=lambda: SimpleNamespace(
                identity=SimpleNamespace(machine_id=HOST)
            ),
        ),
    )
    state = tmp_path / "sofia.db"
    RuntimeUserSettingsStore(state).save(
        RuntimeUserSettings(cognitive_primary_model=MODEL)
    )
    backend = ObservedOllama()
    monkeypatch.setattr(ollama, "OllamaAdapter", lambda: backend)
    return state, backend


def approve(state, *, model=MODEL, host=HOST, role="primary"):
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability="cognition.model.install",
        request_fingerprint=execution_fingerprint(
            "cognition.model.install",
            {"role": role, "model": model, "host_id": host},
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    ExecutionApprovalVerifier(state).record(approval)
    return approval.approval_id


def attempt(state, approval, *, model=MODEL, host=HOST, role="primary"):
    return install_approved_configured_model(
        state,
        role=role,
        expected_model=model,
        host_id=host,
        approval_id=approval,
    )


def test_exact_owner_approved_model_is_pulled_once_and_inventory_confirmed(tmp_path, monkeypatch):
    state, backend = setup(tmp_path, monkeypatch)
    receipt = approve(state)
    result = attempt(state, receipt)
    assert result.model == MODEL
    assert result.state.value == "unloaded"
    assert backend.pulls == [MODEL]
    from sofia.safe.audit import AuditChain
    valid, violation = AuditChain(state).verify()
    assert valid and violation is None
    with pytest.raises(PermissionError, match="already consumed"):
        ExecutionApprovalVerifier(state).consume(
            approval_id=receipt,
            capability="cognition.model.install",
            parameters={"role": "primary", "model": MODEL, "host_id": HOST},
            now=datetime.now(timezone.utc),
        )


def test_model_pull_denied_without_approval_and_no_backend_effect(tmp_path, monkeypatch):
    state, backend = setup(tmp_path, monkeypatch)
    with pytest.raises(PermissionError, match="approval"):
        attempt(state, str(uuid4()))
    assert backend.pulls == []


def test_model_pull_denied_when_receipt_is_bound_to_another_host(tmp_path, monkeypatch):
    state, backend = setup(tmp_path, monkeypatch)
    receipt = approve(state, host="artemis-instead")
    with pytest.raises(PermissionError, match="parameters do not match"):
        attempt(state, receipt)
    assert backend.pulls == []


def test_model_pull_denied_when_configuration_changes_before_installer(tmp_path, monkeypatch):
    state, backend = setup(tmp_path, monkeypatch)
    receipt = approve(state)
    RuntimeUserSettingsStore(state).save(
        RuntimeUserSettings(cognitive_primary_model="other/owner:4b")
    )
    with pytest.raises(PermissionError, match="configured"):
        attempt(state, receipt)
    assert backend.pulls == []


def test_operator_stop_denies_install_without_consuming_approval(tmp_path, monkeypatch):
    state, backend = setup(tmp_path, monkeypatch)
    receipt = approve(state)
    OperatorStopStore(state).set(
        active=True, updated_by="Sparks",
        reason="operator paused model changes",
    )
    with pytest.raises(PermissionError, match="operator stop"):
        attempt(state, receipt)
    assert backend.pulls == []
    assert ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=receipt,
        capability="cognition.model.install",
        parameters={"role": "primary", "model": MODEL, "host_id": HOST},
        now=datetime.now(timezone.utc),
    )


def test_cannot_claim_remote_host_approval_on_local_machine(tmp_path, monkeypatch):
    state, backend = setup(tmp_path, monkeypatch)
    receipt = approve(state, host="artemis-remote")
    with pytest.raises(PermissionError, match="this local machine"):
        attempt(state, receipt, host="artemis-remote")
    assert backend.pulls == []


def test_already_installed_model_does_not_consume_grant_or_fabricate_install_receipt(
    tmp_path, monkeypatch,
):
    state, backend = setup(tmp_path, monkeypatch)
    backend.installed.add(MODEL)
    receipt = approve(state)
    existing = attempt(state, receipt)
    assert existing.state.value == "unloaded"
    assert backend.pulls == []
    assert ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=receipt,
        capability="cognition.model.install",
        parameters={"role": "primary", "model": MODEL, "host_id": HOST},
        now=datetime.now(timezone.utc),
    )
