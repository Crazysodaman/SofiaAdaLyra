"""Deferred production homelab twin: real OPS host evidence, synthetic only."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from sofia.ops.digital_twin import (
    TwinDependencyStore,TwinReviewedDependency,TwinSnapshot,
    read_digital_twin_fleet,run_digital_twin_scenario,
    simulate_hypothetical_failure,snapshot_from_ops,
)
from sofia.ops.model import FleetHost,HostLifecycle,HostTelemetry
from sofia.ops.capability import OpsCapabilitySet,create_ops_tool_bindings
from sofia.safe.permissions import capability_permission_policy,PermissionLevel
from sofia.config.user_settings import RuntimeUserSettingsStore

pytestmark=pytest.mark.pkg_ops
AT=datetime(2026,10,11,18,tzinfo=timezone.utc)


def host(name,*,trusted=True,age_seconds=0,life=HostLifecycle.HEALTHY):
    return FleetHost(
        host_id=name,platform="Windows",architecture="x86_64",
        lifecycle=life,trusted=trusted,
        telemetry=HostTelemetry(
            observed_at=AT-timedelta(seconds=age_seconds),
            cpu_percent=28.0,storage_free_bytes=200_000_000,
        ),
    )


def edge(child,parent,kind):
    return TwinReviewedDependency(
        dependent_host_id=child,prerequisite_host_id=parent,
        kind=kind,reviewed_at=AT,approval_ref="owner-ui:"+uuid4().hex,
    )


def test_simulation_tracks_real_trusted_hosts_and_only_reviewed_links():
    hosts=(host("Artemis"),host("Eos"),host("Hestia"),host("Untrusted",trusted=False))
    link_dns=edge("Eos","Artemis","dns")
    link_service=edge("Hestia","Eos","service")
    snapshot=snapshot_from_ops(hosts,(link_dns,link_service),at=AT)
    assert len(snapshot.hosts)==3
    assert "Untrusted" not in [item.host_id for item in snapshot.hosts]
    simulation=simulate_hypothetical_failure(
        snapshot,scenario="dns_outage",target_host_id="Artemis",at=AT,
    )
    assert simulation.affected_host_ids==("Artemis","Eos")
    assert simulation.assumed_dependencies==(("Eos","Artemis","dns"),)
    assert simulation.fidelity=="dependency_graph_v1"
    assert simulation.source_snapshot_sha256==snapshot.digest
    assert simulation.may_execute_real_actions is False
    assert simulation.may_claim_real_outage is False
    assert simulation.may_grant_authority is False
    unrelated=simulate_hypothetical_failure(
        snapshot,scenario="container_crash",target_host_id="Artemis",at=AT,
    )
    assert unrelated.affected_host_ids==("Artemis",)


def test_simulation_fails_closed_on_unknown_or_untrusted_target():
    hosts=(host("Artemis"),host("Potential",trusted=False))
    snapshot=snapshot_from_ops(hosts,(),at=AT)
    with pytest.raises(PermissionError,match="known OPS"):
        simulate_hypothetical_failure(
            snapshot,scenario="dns_outage",
            target_host_id="Potential",at=AT,
        )
    with pytest.raises(ValueError,match="eight reviewed"):
        simulate_hypothetical_failure(
            snapshot,scenario="automatic_network_probe",
            target_host_id="Artemis",at=AT,
        )


def test_owner_declared_dependencies_persist_in_canonical_db_without_scanning(tmp_path):
    state=tmp_path/"sofia.db"
    RuntimeUserSettingsStore(state).load()
    stored=TwinDependencyStore(state)
    first=edge("Eos","Artemis","dns")
    stored.record_owner_review(first,known_host_ids=("Eos","Artemis"))
    reread=TwinDependencyStore(state).reviewed()
    assert reread==(first,)
    with pytest.raises(PermissionError,match="cannot be silently replaced"):
        stored.record_owner_review(
            edge("Eos","Artemis","dns"),
            known_host_ids=("Eos","Artemis"),
        )
    with pytest.raises(ValueError,match="canonical OPS"):
        stored.record_owner_review(
            edge("Unknown","Artemis","service"),
            known_host_ids=("Eos","Artemis"),
        )
    import sqlite3
    with sqlite3.connect(state) as db:
        rows=db.execute(
            "SELECT COUNT(*) FROM ops_twin_reviewed_dependency"
        ).fetchone()[0]
    assert rows==1


def test_unknown_telemetry_remains_explicit_and_never_becomes_healthy(monkeypatch):
    hosts=(
        host("Artemis",age_seconds=8000),
        FleetHost(
            "Venus","Windows","x86_64",
            HostLifecycle.ENROLLED,True,telemetry=None,
        ),
    )
    snapshot=snapshot_from_ops(hosts,(edge("Venus","Artemis","fleet_transport"),),at=AT)
    simulated=simulate_hypothetical_failure(
        snapshot,scenario="fleet_agent_unreachable",
        target_host_id="Artemis",at=AT,
    )
    assert simulated.affected_host_ids==("Artemis","Venus")
    assert simulated.telemetry_stale_or_missing==("Artemis","Venus")


def test_real_ops_registration_is_readonly_and_has_no_direct_execution():
    caps=OpsCapabilitySet(service=object()).capabilities()
    names={item.name for item in caps}
    assert "ops.digital_twin.inspect" in names
    assert "ops.digital_twin.simulate" in names
    for name in ("ops.digital_twin.inspect","ops.digital_twin.simulate"):
        policy=capability_permission_policy(name)
        assert policy.level is PermissionLevel.OBSERVE_READ
        assert policy.standing_grant_allowed
    bindings=create_ops_tool_bindings()
    names={item.capability_name for item in bindings}
    assert "ops.digital_twin.inspect" in names
    assert "ops.digital_twin.simulate" in names
    assert "workshop.vm.provision" not in names


def test_source_grounded_ops_service_path_never_runs_host_tools(tmp_path):
    state=tmp_path/"sofia.db"
    RuntimeUserSettingsStore(state).load()
    host_data=(host("Artemis"),host("Eos"))
    store=TwinDependencyStore(state)
    store.record_owner_review(
        edge("Eos","Artemis","storage"),
        known_host_ids=("Eos","Artemis"),
    )
    service=SimpleNamespace(
        state_path=state,registry=SimpleNamespace(hosts=lambda:host_data),
    )
    observed=read_digital_twin_fleet(service=service,at=AT)
    assert observed["source"]=="canonical OPS Fleet"
    assert observed["simulation_only"]
    assert observed["observed_network_topology"].startswith("UNKNOWN")
    experiment=run_digital_twin_scenario(
        service=service,scenario="disk_pressure",
        target_host_id="Artemis",at=AT,
    )
    assert experiment["affected_host_ids"]==("Artemis","Eos")
    assert experiment["source_reviewed_edge_count"]==1
    assert experiment["may_execute_real_actions"] is False
    assert "NOT an observed outage" in experiment["scientific_limit"]


def test_duplicate_or_impossible_host_graphs_fail_closed():
    same=host("Artemis")
    with pytest.raises(ValueError,match="duplicate"):
        snapshot_from_ops((same,same),(),at=AT)
    with pytest.raises(ValueError,match="unreviewed"):
        TwinSnapshot(
            hosts=(),
            dependencies=(edge("Eos","Artemis","dns"),),
            generated_at=AT,
        )
