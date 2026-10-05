"""Register application background tasks without starting scheduler threads.

The application retains lifecycle and rollback ownership; the coordinator owns
scheduling, budgets and foreground priority. Callbacks bind existing services
and do not create a second runtime, conversation or state model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import socket
from typing import TYPE_CHECKING

from sofia.application.background import ApplicationBackgroundCoordinator
from sofia.application.fleet_runtime import (
    create_fleet_bootstrap_coordinator, create_fleet_candidate_notifier,
    create_fleet_reconciliation_notifier,
)
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.ops.backup_topology import (
    backup_topology_interval_seconds,
    create_backup_topology_from_environment,
)
from sofia.ops.discovery import FleetDiscoveryCoordinator, FleetDiscoveryEnrollmentReconciler
from sofia.personality.influence import ContinuityInfluence
from sofia.run.heartbeat import ApplicationHeartbeat

if TYPE_CHECKING:
    from sofia.application.bootstrap import SofiaApplication


def create_background_coordinator(
    application: SofiaApplication,
    *,
    reflection_enabled: bool,
    habit_runtime_enabled: bool,
    act_delivery_enabled: bool,
    presentation_runtime_enabled: bool,
    fleet_discovery_source,
    fleet_reconciliation_enabled: bool,
) -> ApplicationBackgroundCoordinator:
    """Prepare callbacks; the caller must own the coordinator before start()."""
    act_service = getattr(application, "_act_service", None)
    ops_service = getattr(application._runtime, "ops_service", None)
    fleet_discovery_enabled = fleet_discovery_source is not None
    backup_topology = create_backup_topology_from_environment(
        state_path=Path(application._configuration.state_path),
        state_plane=application._runtime.state_plane,
    )
    coordinator = ApplicationBackgroundCoordinator(
        service=application._conversation_service,
        state_path=Path(application._configuration.state_path),
        reflection_enabled=reflection_enabled,
    )
    from sofia.avatar.wardrobe_review import WardrobeReviewStore, review_next
    from sofia.social.principals import local_sparks_principal
    review_store = WardrobeReviewStore(application._configuration.state_path)

    def review_wardrobe(now):
        from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
        with application._model_lock:
            key = review_next(
                review_store,
                lambda request: application._runtime.respond(request, principal=local_sparks_principal()),
                now=now,
            )
            if key is not None and any(row["proposal_id"] == key and row["status"] == "approved" for row in review_store.list()):
                bundle = load_or_bootstrap_presentation(embodiment=application._runtime.embodiment, state_path=application._configuration.state_path)
                application._install_presentation_bundle(bundle)
            return key

    coordinator.set_task("wardrobe_review", review_wardrobe, interval_seconds=30, ready=lambda: review_store.has_pending(datetime.now(timezone.utc)))
    activity_store = HostActivityStore(
        application._configuration.state_path
    )
    host_id = socket.gethostname()

    def deliver_act(now):
        activity = activity_store.state(host_id).effective
        busy = activity in {
            ActivityMode.GAMING,
            ActivityMode.BUSY,
            ActivityMode.DO_NOT_DISTURB,
        }
        return act_service.deliver_one(
            now=now,
            busy=busy,
        )

    if act_delivery_enabled:
        coordinator.set_act_delivery(deliver_act)

    def bridge_reflection_outreach(now):
        service = application._conversation_service
        if not hasattr(service, "current_emotional_state"):
            return None
        emotion = service.current_emotional_state(now=now)
        environment = application._runtime.environment_service.snapshot(
            now=now,
            refresh_providers=False,
        )
        influence = ContinuityInfluence.from_state(
            emotion=emotion,
            environment=environment,
        )
        if act_service is None:
            return None
        count = act_service.bridge_reflection_outbox(
            reflections=service.reflection_journal,
            scope=service.relationship_scope,
            now=now,
            influence=influence,
        )
        return count or None

    if act_delivery_enabled:
        coordinator.set_task(
            "reflection_outreach",
            bridge_reflection_outreach,
        )

    if fleet_discovery_enabled:
        discovery = FleetDiscoveryCoordinator(
            application._runtime.ops_service.registry,
            candidate_notifier=create_fleet_candidate_notifier(
                act_service=application._act_service,
            ),
        )
        bootstrap_coordinator = (
            create_fleet_bootstrap_coordinator(
                configuration=application._configuration,
                act_service=application._act_service,
            )
        )

        def discover_fleet_candidates(now):
            result = discovery.run(fleet_discovery_source)
            bootstrap_result = (
                None
                if bootstrap_coordinator is None
                else bootstrap_coordinator.reconcile(result)
            )
            identities = DurableNodeIdentityRegistry(
                application._configuration.state_path
            )
            endpoints = DurableEndpointPolicy(
                application._configuration.state_path
            )
            try:
                reconciled = FleetDiscoveryEnrollmentReconciler(
                    enrollment_service=(
                        application._runtime.ops_service.enrollment
                    ),
                    identity_registry=identities,
                    endpoint_policy=endpoints,
                ).reconcile(result)
            finally:
                identities.close()
                endpoints.close()
            count = (
                len(result.created_host_ids)
                + len(result.rejected_host_ids)
                + len(reconciled.enrolled_host_ids)
                + (
                    0
                    if bootstrap_result is None
                    else len(
                        bootstrap_result.operator_host_ids
                    )
                    + len(
                        bootstrap_result.installed_host_ids
                    )
                )
            )
            return count or None

        coordinator.set_task(
            "fleet_discovery",
            discover_fleet_candidates,
            interval_seconds=float(
                application._configuration.fleet_discovery.interval_seconds
            ),
        )

    if backup_topology is not None:
        def run_backup_topology(now):
            return backup_topology.run(now=now)

        coordinator.set_task(
            "backup_topology",
            run_backup_topology,
            interval_seconds=backup_topology_interval_seconds(),
        )

    if fleet_reconciliation_enabled:
        reconciliation_notifier = (
            create_fleet_reconciliation_notifier(
                act_service=application._act_service,
            )
        )

        def reconcile_fleet(now):
            created = ops_service.observe_reconciliation(
                now=now,
            )
            if reconciliation_notifier is not None:
                for record in created:
                    reconciliation_notifier(record)
            return len(created) or None

        coordinator.set_task(
            "fleet_reconciliation",
            reconcile_fleet,
            interval_seconds=300.0,
        )

    if presentation_runtime_enabled:
        def evaluate_avatar_presentation(now):
            result = application._evaluate_contextual_presentation_when_idle(
                now=now,
                refresh_environment=True,
                idle_seconds=coordinator.idle_seconds,
            )
            return (
                result
                if result is not None and result.changed
                else None
            )

        coordinator.set_task(
            "avatar_presentation",
            evaluate_avatar_presentation,
            interval_seconds=900.0,
        )

    def analyze_habits(now):
        service = application._conversation_service
        principal = (
            service._principal_context()
            if hasattr(service, "_principal_context")
            else None
        )
        if principal is None:
            return None
        count = application._habit_continuity.analyze_conversation_patterns(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            now=now,
        )
        return count or None

    def decay_habits(now):
        service = application._conversation_service
        principal = (
            service._principal_context()
            if hasattr(service, "_principal_context")
            else None
        )
        if principal is None:
            return None
        count = application._habit_continuity.decay_patterns(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            now=now,
        )
        return count or None

    def evaluate_expectations(now):
        service = application._conversation_service
        principal = (
            service._principal_context()
            if hasattr(service, "_principal_context")
            else None
        )
        if principal is None:
            return None
        count = application._habit_continuity.evaluate_expectations(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            now=now,
        )
        return count or None

    last_coverage_at = datetime.now(timezone.utc)

    def record_habit_coverage(now):
        nonlocal last_coverage_at
        service = application._conversation_service
        principal = (
            service._principal_context()
            if hasattr(service, "_principal_context")
            else None
        )
        if principal is None:
            last_coverage_at = now
            return None
        application._habit_continuity.record_runtime_coverage(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            started_at=last_coverage_at,
            ended_at=now,
        )
        last_coverage_at = now
        return True

    if habit_runtime_enabled:
        coordinator.set_task(
            "habit_observation",
            record_habit_coverage,
        )
        coordinator.set_task(
            "habit_analysis",
            analyze_habits,
        )
        coordinator.set_task(
            "habit_decay",
            decay_habits,
        )
        coordinator.set_task(
            "expectation_evaluation",
            evaluate_expectations,
        )
    runtime_id = getattr(application._runtime, "runtime_id", None)
    heartbeat_store = getattr(
        application,
        "_heartbeat_store",
        None,
    )
    if runtime_id is not None and heartbeat_store is not None:
        def publish_heartbeat(now, healthy):
            runtime_state = getattr(
                getattr(application._runtime, "state", None),
                "value",
                "ready" if healthy else "unknown",
            )
            heartbeat_store.publish(
                ApplicationHeartbeat(
                    instance_id=str(runtime_id),
                    recorded_at=now,
                    ready=bool(
                        healthy and runtime_state == "ready"
                    ),
                    runtime_state=runtime_state,
                    database_writable=True,
                    background_running=True,
                    detail=(
                        "application background loop healthy"
                        if healthy
                        else "application background loop reported an error"
                    ),
                )
            )
        coordinator.set_heartbeat(publish_heartbeat)

    return coordinator
