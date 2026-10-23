"""Register application background tasks without starting scheduler threads.

The application retains lifecycle and rollback ownership; the coordinator owns
scheduling, budgets and foreground priority. Callbacks bind existing services
and do not create a second runtime, conversation or state model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import logging
import os
import socket
from typing import TYPE_CHECKING

from sofia.platform.application.background import ApplicationBackgroundCoordinator
from sofia.platform.act.outreach import Importance, OutreachCategory
from sofia.platform.application.presence import (
    InitiativeEvent, PresenceInitiativeEngine, WorldAvailability,
    WorldEpistemicState, WorldObservation,
)
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID
from sofia.platform.application.fleet_runtime import (
    create_fleet_bootstrap_coordinator, create_fleet_candidate_notifier,
    create_fleet_reconciliation_notifier,
)
from sofia.platform.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.platform.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.platform.ops.activity import ActivityMode, HostActivityStore
from sofia.platform.ops.backup_topology import (
    backup_topology_enabled,
    backup_topology_interval_seconds,
    create_backup_topology_from_environment,
)
from sofia.platform.ops.discovery import FleetDiscoveryCoordinator, FleetDiscoveryEnrollmentReconciler
from sofia.core.personality.influence import ContinuityInfluence
from sofia.platform.run.heartbeat import ApplicationHeartbeat

if TYPE_CHECKING:
    from sofia.platform.application.bootstrap import SofiaApplication


_LOG = logging.getLogger(__name__)


def _consider_life_idea_without_wedging_worker(
    life, *, generate, now: datetime, busy: bool, resource_pressure: float,
):
    """Model outage/invalid ideation declines this optional idea only.

    Do not swallow operator-stop, SQLite corruption, authorization failure,
    or unrelated code errors. The normal LIFE tick must still reconcile
    existing work, previously approved goals and durable RUN receipts.
    """
    from sofia.core.cognition.engine import CognitiveEngineError
    from sofia.core.life.idea_agent import ProjectIdeaGenerationError
    try:
        return life.consider_new_project(
            generate=generate, now=now, busy=busy,
            resource_pressure=resource_pressure,
        )
    except (CognitiveEngineError, ProjectIdeaGenerationError) as exc:
        _LOG.warning(
            "Optional LIFE idea skipped: provider unavailable or invalid "
            "model output (%s); existing work reconciliation continues.",
            type(exc).__name__,
        )
        return None


def bridge_voluntary_life_outreach(
    *, life, presence: PresenceInitiativeEngine, act_service,
    now: datetime, busy: bool, generate,
) -> int:
    """Let Sofía optionally talk about her own verified private successes.

    This bridge belongs to the existing independent LIFE worker and the
    existing Presence/ACT recipient policy, NOT to a new social scheduler.
    Project metadata only is offered to the authenticated owner: never raw
    files, private reflections, a public post or a device control action.
    The human can opt out globally or choose quiet, and silence is normal.
    """
    if busy or act_service is None or presence is None:
        return 0
    if not act_service.delivery_enabled:
        return 0
    route = act_service.delivery_route
    # Desktop's owner tray or a separately authenticated pinned owner DM.
    # Home Assistant notify targets and general channels have no proven
    # one-to-one private project audience mapping.
    if (
        route is None
        or route[0] not in {"desktop", "discord"}
        or (route[0] == "desktop" and route[1] != "tray")
    ):
        return 0
    policy = act_service.policy
    if policy is None or not policy.enabled or policy.mute or policy.stop:
        return 0
    if policy.recipient_id != SPARKS_PRINCIPAL_ID:
        return 0
    from sofia.platform.config.user_settings import RuntimeUserSettingsStore
    outreach = RuntimeUserSettingsStore(act_service.state_path).load().outreach
    if outreach is not None and (not outreach.enabled or outreach.mute):
        return 0
    if presence.recent_life_project_outreach(now=now):
        return 0
    from sofia.core.social.principals import local_sparks_principal
    owner = local_sparks_principal()
    moments = tuple(
        item for item in life.voluntary_project_updates(now=now, limit=16)
        if presence.owner_life_update_feedback(
            project_id=item["project_id"], principal=owner,
        ) != "declined"
    )
    if not moments:
        return 0
    # One event is sufficient; preference strength chooses which source
    # event deserves the moment. No per-project sharing approval prompt.
    candidate = max(
        moments,
        key=lambda row: (row["salience"], row["verified_at"], row["event_id"]),
    )
    if candidate["audience_id"] != "local:text":
        return 0
    interest_words = {
        word.strip(".,:;!?()[]{}").casefold()
        for field in (candidate.get("interest_name"), candidate.get("interest_context"))
        if isinstance(field, str)
        for word in field.split()
    }
    shared_domains = (
        ("robotics", {"robot", "robotics", "gaia"}),
        ("railway", {"railway", "railroad", "jmri", "train"}),
        ("coding", {"code", "coding", "software", "programming"}),
        ("virtual_lab", {"lab", "laboratory", "simulation", "experiment"}),
    )
    shared_domain = next((
        name for name, markers in shared_domains if interest_words & markers
    ), None)
    # Sofía's model may choose to share or to remain quiet. It never
    # writes the outgoing factual claims or gets additional authority.
    from sofia.core.life.outreach_agent import (
        ProjectOutreachChoiceAgent, ProjectOutreachChoiceError,
    )
    if not callable(generate):
        return 0
    try:
        choice = ProjectOutreachChoiceAgent(generate).choose(
            moment_kind=candidate["moment_kind"],
            title=candidate["title"],
            verified_at=candidate["verified_at"],
            salience=candidate["salience"],
        )
    except ProjectOutreachChoiceError:
        return 0
    if not choice.share_now:
        return 0
    if presence.owner_life_update_feedback(
        project_id=candidate["project_id"], principal=owner,
    ) == "declined":
        return 0
    # A model turn may have been interrupted by the operator or the
    # original project being retired. Recheck the live source and user
    # stop/mute boundary before queuing any real notice.
    refreshed = life.voluntary_project_updates(now=now, limit=16)
    # A model choice applies to one exact original LIFE milestone snapshot.
    # The same event ID may survive corrections to source refs, project
    # wording, salience, time, or audience while the model was thinking.
    # Refuse an obsolete snapshot instead of queuing old facts to ACT.
    if not any(item == candidate for item in refreshed):
        return 0
    if act_service.delivery_route != route:
        # A destination changed during cognitive latency. Reassess on the
        # next background tick rather than sending private context elsewhere.
        return 0
    from sofia.platform.safe.operator_stop import OperatorStopStore
    if OperatorStopStore(act_service.state_path).current().active:
        return 0
    refreshed_outreach = RuntimeUserSettingsStore(
        act_service.state_path,
    ).load().outreach
    if refreshed_outreach is not None and (
        not refreshed_outreach.enabled or refreshed_outreach.mute
    ):
        return 0
    current_policy = act_service.policy
    if (
        current_policy is None or not current_policy.enabled
        or current_policy.mute or current_policy.stop
        or current_policy.recipient_id != SPARKS_PRINCIPAL_ID
    ):
        return 0
    if (
        presence.recent_life_project_outreach(now=now)
        or presence.owner_life_update_feedback(
            project_id=candidate["project_id"], principal=owner,
        ) == "declined"
    ):
        return 0
    event_id = "life-update:" + sha256(
        candidate["event_id"].encode("utf-8")
    ).hexdigest()[:32]
    completed = candidate["moment_kind"] == "verified_completion"
    observation = WorldObservation(
        observation_id="life-observed:" + sha256(
            candidate["event_id"].encode("utf-8")
        ).hexdigest()[:32],
        subject_id="life:" + sha256(
            candidate["project_id"].encode("utf-8")
        ).hexdigest()[:24],
        predicate=(
            "original_project.verified_completion" if completed
            else "original_project.verified_draft"
        ),
        source_id=(
            "life:canonical_project_event" if completed
            else "life:canonical_artifact_evaluation"
        ),
        observed_at=candidate["verified_at"],
        expires_at=candidate["expires_at"],
        confidence=1.0,
        epistemic_state=WorldEpistemicState.OBSERVED,
        availability=WorldAvailability.NOT_APPLICABLE,
        value={
            "project_id": candidate["project_id"],
            "source_record_id": candidate["event_id"],
            "source_record_kind": candidate["moment_kind"],
            "source_evidence_refs": candidate["source_evidence_refs"],
            "independent_objectives_verified": completed,
            "original_artifact_bytes_verified": True,
            "artifact_disclosed": False,
            "shared_activity_domain": shared_domain,
        },
        audience_id="local:text",
    )
    # Model-authored project names are low-trust content. Strip control
    # characters and Discord mention/markup delimiters before a private
    # outbound message can ever hit a configured transport.
    safe_title = "".join(
        char if char.isprintable() and char not in "<>@`" else " "
        for char in candidate["title"]
    )
    name = " ".join(safe_title.split())[:120].strip() or "my creative project"
    # Vary the conversational invitation using a stable source identifier,
    # not randomized nagging or fabricated emotional events.
    style = {
        "warm": 0, "playful": 1, "matter_of_fact": 2,
    }[choice.tone]
    if completed:
        content = (
            f"I finished {name}, and its original checks passed. "
            "I wanted to share that little win with you. Want to hear what I made?"
            if style == 0 else
            f"Guess what I finished: {name}. The checks passed, "
            "and I thought you might like to hear how it turned out."
            if style == 1 else
            f"A small creative victory: {name} is finished and verified. "
            "I felt like telling you about it. Curious what I tried?"
        )
    else:
        content = (
            f"I made a draft for {name}. It isn't fully verified yet, "
            "but I thought you might like to hear what I tried."
            if style == 0 else
            f"I've been working on {name} and have a real first draft. "
            "Some of the goals still need review. Want the story behind it?"
            if style == 1 else
            f"A little progress on {name}: I made a draft. "
            "I'm still sorting out how it holds up, but I wanted to tell you."
        )
    if shared_domain is not None:
        content += (
            " If that sounds fun, we could look at the next step together; "
            "no pressure if you'd rather leave it there."
        )
    decision = presence.consider(InitiativeEvent(
        event_id=event_id,
        trigger_kind=(
            "shared_activity_offer" if shared_domain is not None
            else "task_completed"
        ),
        observation=observation,
        content=content,
        created_at=now,
        expires_at=candidate["expires_at"],
        category=OutreachCategory.SOCIAL,
        importance=Importance.ROUTINE,
        salience=candidate["salience"],
        recipient_id=SPARKS_PRINCIPAL_ID,
    ))
    # Queued is not sent, received or read. ACT retains all delivery policy
    # and its own attempt/transport acknowledgement receipts.
    return int(decision.status == "queued")


def _generate_private_life_outreach(application, request):
    """Use the same authenticated owner model and application-wide lock."""
    from sofia.core.social.principals import local_sparks_principal
    with application._model_lock:
        return application._runtime.respond(
            request, principal=local_sparks_principal(),
        )


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
    backup_topology = (
        create_backup_topology_from_environment(
            state_path=Path(application._configuration.state_path),
            state_plane=application._runtime.state_plane,
        )
        if backup_topology_enabled()
        else None
    )
    coordinator = ApplicationBackgroundCoordinator(
        service=application._conversation_service,
        state_path=Path(application._configuration.state_path),
        reflection_enabled=reflection_enabled,
    )
    set_task_priority = getattr(coordinator, "set_task_priority", None)
    if set_task_priority is not None:
        set_task_priority(application._neuro.background_priority)
    set_reflection_wake_gate = getattr(
        coordinator,
        "set_reflection_wake_gate",
        None,
    )
    if set_reflection_wake_gate is not None:
        set_reflection_wake_gate(
            application._neuro.should_wake_for_reflection
        )

    def refresh_neuro(now):
        service = application._conversation_service
        with application._model_lock:
            if not service.ready_for_idle_reflection(
                idle_seconds=coordinator.idle_seconds
            ):
                return None
            principal = (
                service._principal_context()
                if hasattr(service, "_principal_context")
                else None
            )
            return application._refresh_neuro_inputs(
                now=now,
                principal=principal,
                refresh_environment=False,
            )

    coordinator.set_task(
        "neuro_refresh",
        refresh_neuro,
        interval_seconds=60.0,
    )

    def refresh_presence(now):
        """Project authoritative state without inferring health from silence."""
        presence = application._presence
        stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        runtime_state = application._runtime.state.value
        presence.record_state(
            observation_id=f"world:runtime:{stamp}",
            subject_id="runtime:sofia",
            predicate="application.runtime_state",
            source_id="runtime:lifecycle",
            observed_at=now,
            freshness=timedelta(minutes=3),
            confidence=1.0,
            epistemic_state=WorldEpistemicState.OBSERVED,
            availability=(
                WorldAvailability.HEALTHY
                if runtime_state == "ready"
                else WorldAvailability.DEGRADED
            ),
            value={"state": runtime_state},
        )
        activity = activity_store.state(host_id).effective
        presence.record_state(
            observation_id=f"world:activity:{stamp}",
            subject_id=f"host:{host_id}",
            predicate="user.availability",
            source_id="ops:host_activity",
            observed_at=now,
            freshness=timedelta(minutes=3),
            confidence=1.0,
            epistemic_state=WorldEpistemicState.OBSERVED,
            availability=WorldAvailability.NOT_APPLICABLE,
            value={"activity": activity.value},
            audience_id="sparks",
        )
        environment = application._runtime.environment_service.snapshot(
            now=now, refresh_providers=False,
        )
        presence.record_state(
            observation_id=f"world:environment:{stamp}",
            subject_id="environment:current",
            predicate="environment.context",
            source_id="environment:snapshot",
            observed_at=now,
            freshness=timedelta(minutes=3),
            confidence=1.0,
            epistemic_state=WorldEpistemicState.OBSERVED,
            availability=WorldAvailability.NOT_APPLICABLE,
            value={
                "season": None if environment.season is None else environment.season.value,
                "daylight": None if environment.daylight is None else environment.daylight.state.value,
                "weather_freshness": environment.weather_freshness.value,
            },
            audience_id="sparks",
        )
        return True

    coordinator.set_task("presence_refresh", refresh_presence, interval_seconds=60.0)

    # CA-6109: publish bounded read-only storage pressure through the existing
    # PRESENCE owner. The STOP-gated RUN coordinator schedules this as ordinary
    # maintenance, not an independent worker or a database authority.
    from sofia.platform.ops.capacity_runtime import record_local_capacity

    def observe_local_capacity(now):
        return record_local_capacity(
            state_path=application._configuration.state_path,
            presence=application._presence,
            now=now,
        )

    coordinator.set_task(
        "local_capacity_observation",
        observe_local_capacity,
        interval_seconds=300.0,
    )
    goal_production = getattr(application, "_goal_production", None)
    if goal_production is not None:
        coordinator.set_task(
            "goal_production",
            lambda now: goal_production.tick(now=now),
            interval_seconds=60.0,
        )
    from sofia.avatar.wardrobe_review import WardrobeReviewStore, review_next
    from sofia.core.social.principals import local_sparks_principal
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

    # Only the canonical scheduler may poll this public advisory feed.
    # Registration requires explicit environment opt-in, and does not create
    # a second writer, model session or permission authority.
    from sofia.core.mentor.remote_inbox import register_application_review_task
    register_application_review_task(
        application=application, coordinator=coordinator,
        activity_store=activity_store, host_id=host_id,
    )

    # Owner opt-in: observe settled responses without delaying them, then
    # review at most one private sample on an idle-approved background tick.
    # This never contacts OpenAI and never exports raw emotional history.
    from sofia.core.mentor.behavior_monitor import register_behavior_monitor
    register_behavior_monitor(
        application=application, coordinator=coordinator,
        activity_store=activity_store, host_id=host_id,
        repo=os.environ.get("SOFIA_MENTOR_SOURCE_ROOT", "."),
    )

    # Model discovery is a scheduled READ ONLY inventory, not an installation
    # or inference worker. It reuses the owner's /tags /version /show service,
    # canonical cognition_model_inventory, and RUN's existing single-flight
    # budget. No new independent polling thread or approval source exists.
    from sofia.platform.config.cognitive_models import CognitiveModelSelection
    from sofia.core.cognition.model_inventory import refresh_local_model_inventory
    from sofia.platform.machine.discovery import create_machine_discovery

    configured_model_providers = CognitiveModelSelection.from_configuration(
        application._configuration
    ).providers
    if any(provider.provider == "ollama" for provider in configured_model_providers):
        def model_discovery_ready() -> bool:
            return activity_store.state(host_id).effective not in {
                ActivityMode.GAMING,
                ActivityMode.BUSY,
                ActivityMode.DO_NOT_DISTURB,
            }

        def discover_local_models(now):
            observed_host = (
                create_machine_discovery().discover().identity.machine_id
            )
            observed = refresh_local_model_inventory(
                state_path=Path(application._configuration.state_path),
                host_id=observed_host,
                at=now,
                details_limit=4,
            )
            # Empty inventory is still a truthful observation; never infer
            # compatibility, accept licenses, install, or switch an LLM role.
            return {"observed_models": len(observed)}

        coordinator.set_task(
            "cognition_model_discovery",
            discover_local_models,
            interval_seconds=21600.0,
            ready=model_discovery_ready,
        )

    # Optional association decay belongs to the existing RUN lifecycle. It
    # does not wake an LLM, store raw conversation, or create memories.
    from sofia.platform.config.user_settings import RuntimeUserSettingsStore
    from sofia.neuro.connectome.association_store import ReviewedAssociationStore

    def association_decay_ready():
        from sofia.platform.safe.operator_stop import OperatorStopStore
        return (
            not OperatorStopStore(application._configuration.state_path)
            .current().active
            and RuntimeUserSettingsStore(application._configuration.state_path)
            .load().neuro_association_enabled
            and activity_store.state(host_id).effective not in {
                ActivityMode.GAMING, ActivityMode.BUSY,
                ActivityMode.DO_NOT_DISTURB,
            }
        )

    def decay_reviewed_associations(now):
        owner = local_sparks_principal()
        count = ReviewedAssociationStore(
            application._configuration.state_path,
        ).decay_scope(
            principal_id=owner.principal_id,
            audience_id=owner.audience_id,
            rate=0.01,
            at=now,
        )
        return {"decayed_weights": count} if count else None

    coordinator.set_task(
        "neuro_association_decay",
        decay_reviewed_associations,
        interval_seconds=86400.0,
        ready=association_decay_ready,
    )

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
        set_act_ready = getattr(coordinator, "set_act_ready", None)
        if callable(set_act_ready):
            set_act_ready(act_service.has_pending)

        def revisit_pending_conversation(now):
            """Offer one due v2 thread through Presence/ACT, never a new sender."""
            activity = activity_store.state(host_id).effective
            if activity in {
                ActivityMode.GAMING, ActivityMode.BUSY,
                ActivityMode.DO_NOT_DISTURB,
            }:
                return None
            from sofia.core.social.principals import local_sparks_principal
            decision = application._presence.offer_due_pending_conversation(
                principal=local_sparks_principal(), now=now,
            )
            return None if decision is None else {
                "event_id": decision.event_id,
                "status": decision.status,
                "reason": decision.reason,
            }

        coordinator.set_task(
            "conversation_followup",
            revisit_pending_conversation,
            interval_seconds=300.0,
        )

    autonomous_work = getattr(application, "_autonomous_work", None)
    if autonomous_work is not None:
        def run_autonomous_work(now):
            activity = activity_store.state(host_id).effective
            busy = activity in {
                ActivityMode.GAMING,
                ActivityMode.BUSY,
                ActivityMode.DO_NOT_DISTURB,
            }
            snapshot = application._neuro.last_snapshot
            pressure = 0.0 if snapshot is None else max(
                snapshot.homeostasis.cognitive_load,
                snapshot.homeostasis.competition_pressure,
            )
            result = autonomous_work.tick(
                now=now, busy=busy, resource_pressure=pressure,
            )
            return result if any(result.values()) else None

        coordinator.set_task(
            "autonomous_work",
            run_autonomous_work,
            interval_seconds=60.0,
        )

    learning = getattr(application, "_learning", None)
    if learning is not None:
        fleet_pressure = getattr(application, "_fleet_pressure_pilot", None)

        def enforce_learning_retention(now):
            result = learning.enforce_retention(at=now, limit=500)
            pilot_deleted = 0 if fleet_pressure is None else fleet_pressure.enforce_retention(
                at=now, limit=500,
            )
            combined = {**result, "fleet_forecasts_deleted": pilot_deleted}
            return combined if any(combined.values()) else None

        coordinator.set_task(
            "learning_retention",
            enforce_learning_retention,
            interval_seconds=86400.0,
        )
        if fleet_pressure is not None:
            def run_fleet_pressure_pilot(now):
                activity = activity_store.state(host_id).effective
                busy = activity in {
                    ActivityMode.GAMING,
                    ActivityMode.BUSY,
                    ActivityMode.DO_NOT_DISTURB,
                }
                return fleet_pressure.tick(at=now, busy=busy)

            coordinator.set_task(
                "fleet_pressure_shadow",
                run_fleet_pressure_pilot,
                interval_seconds=300.0,
                ready=lambda: fleet_pressure.ready(
                    at=datetime.now(timezone.utc),
                    busy=activity_store.state(host_id).effective in {
                        ActivityMode.GAMING,
                        ActivityMode.BUSY,
                        ActivityMode.DO_NOT_DISTURB,
                    },
                ),
            )

    generalization = getattr(application, "_generalization", None)
    if generalization is not None:
        def enforce_generalization_retention(now):
            retired = generalization.expire_retention(now=now, limit=64)
            invalidated = 0
            if generalization.skills is not None:
                invalidated = generalization.skills.reconcile_sources(
                    now=now, limit=64,
                )
            propagation = (
                {"episodes_revoked": 0, "principles_invalidated": 0}
                if generalization.advanced is None
                else generalization.advanced.propagate_revocations(now=now, limit=128)
            )
            result = {
                "generalization_suites_retired": retired,
                "generalization_skills_invalidated": invalidated,
                **propagation,
            }
            return result if any(result.values()) else None

        coordinator.set_task(
            "generalization_retention",
            enforce_generalization_retention,
            interval_seconds=86400.0,
        )

    life = getattr(application, "_life", None)
    if life is not None:
        def run_independent_life(now):
            from sofia.core.social.principals import local_sparks_principal
            activity = activity_store.state(host_id).effective
            busy = activity in {
                ActivityMode.GAMING,
                ActivityMode.BUSY,
                ActivityMode.DO_NOT_DISTURB,
            }
            snapshot = application._neuro.last_snapshot
            pressure = 0.0 if snapshot is None else max(
                snapshot.homeostasis.cognitive_load,
                snapshot.homeostasis.competition_pressure,
            )
            with application._model_lock:
                learning = life.learn_from_experiences(now=now, limit=16)
                project = _consider_life_idea_without_wedging_worker(
                    life,
                    generate=lambda request: application._runtime.respond(
                        request, principal=local_sparks_principal(),
                    ),
                    now=now, busy=busy, resource_pressure=pressure,
                )
                result = life.tick(
                    now=now, busy=busy, resource_pressure=pressure,
                    generate=lambda request: application._runtime.respond(
                        request, principal=local_sparks_principal(),
                    ),
                )
                principal = local_sparks_principal()
                journal = application._conversation_service.emotional_journal
                for experience in life.store.experiences(
                    audience_id=principal.audience_id,
                    include_private=True,
                    limit=16,
                ):
                    journal.record_life_experience(
                        experience, principal=principal,
                    )
            queued_updates = (
                bridge_voluntary_life_outreach(
                    life=life, presence=application._presence,
                    act_service=act_service, now=now, busy=busy,
                    generate=lambda request: _generate_private_life_outreach(
                        application, request,
                    ),
                )
                if act_delivery_enabled and act_service is not None else 0
            )
            return {
                **result, "interest_learning": learning,
                "life_social_updates_queued": queued_updates,
            } if (
                project is not None
                or result["jobs_started"] or result["scheduled"]
                or any(learning.values()) or queued_updates
            ) else None

        coordinator.set_task(
            "independent_life",
            run_independent_life,
            interval_seconds=300.0,
        )

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
        with application._model_lock:
            if hasattr(service, "reconsider_due_reflection"):
                service.reconsider_due_reflection(
                    now=now,
                    influence=influence,
                )
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
