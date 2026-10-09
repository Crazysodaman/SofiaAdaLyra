"""Application integration for evidence-linked emotional expression and reflection."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from threading import Condition, RLock
from time import monotonic
from weakref import WeakSet

from sofia.application.conversation_service import ConversationService
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.matrix import (
    EmbodiedExpressionPlan,
    EmbodiedExpressionPlanner,
    HistoryPolicy,
    MatrixDomain,
    ResponseValidationDisposition,
)
from sofia.cognition.performance import (
    efficiency_snapshot, emit_performance, performance_trace_enabled,
)
from sofia.conversation.model import ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.emotion.clarification import ClarificationJournal
from sofia.emotion.appraisal import ConversationEmotionAppraiser
from sofia.emotion.model import CurrentEmotionalState
from sofia.emotion.journal import EmotionalJournal
from sofia.personality.influence import ContinuityInfluence
from sofia.personality.modulation import derive_expression_modulation
from sofia.personality.observation_bridge import record_workspace_observation
from sofia.personality.reflection import ReflectionJournal
from sofia.personality.thought_agent import ReflectionOutcome, ThoughtAgent
from sofia.runtime.runtime import SofiaRuntime
from sofia.social.model import PrincipalContext, SocialScope
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.social.affect import (
    UserAffectAppraiser,
    UserAffectObservation,
    UserAffectTracker,
)


_CAUSAL_LAST_TURN_QUERY = re.compile(
    r"^\s*(?:why|how\s+so|tell\s+me\s+(?:the\s+)?why|"
    r"what\s+do\s+you\s+mean|explain\s+that)\s*[?!.]*\s*$",
    re.IGNORECASE,
)

_CONTEXT_HISTORY_QUERY = re.compile(
    r"\b(?:why\s+(?:do|are)\s+you\s+(?:feel|feeling)|"
    r"what\s+made\s+you\s+feel|what\s+caused\s+you\s+to\s+feel|"
    r"why\s+are\s+you\s+(?:happy|sad|upset|angry|mad|excited|"
    r"warm|affectionate|fond|frustrated|worried|nervous|calm)|"
    r"where\s+is\s+that\s+feeling\s+coming\s+from|"
    r"what\s+is\s+that\s+feeling\s+from|"
    r"what\s+happened|how\s+did\s+.{1,80}\s+go)\b",
    re.IGNORECASE,
)

_LOG = logging.getLogger(__name__)


class ConversationActivityGroup:
    """Aggregate foreground activity across all application conversation surfaces."""

    def __init__(self) -> None:
        self._condition = Condition(RLock())
        self._active_foreground = 0
        self._draining = False
        self._members: WeakSet = WeakSet()

    def register(self, service) -> None:
        with self._condition:
            self._members.add(service)

    @contextmanager
    def foreground(self):
        """Track a turn without serializing independent channel inference."""
        with self._condition:
            if self._draining:
                raise RuntimeError("conversation activity is draining for shutdown")
            self._active_foreground += 1
        try:
            yield
        finally:
            with self._condition:
                self._active_foreground -= 1
                self._condition.notify_all()

    def begin_shutdown(self) -> None:
        """Reject new turns and wait until already-started turns commit."""
        with self._condition:
            self._draining = True
            self._condition.wait_for(lambda: self._active_foreground == 0)

    def accept_foreground(self) -> None:
        """Open the foreground gate for initial start or a clean restart."""
        with self._condition:
            if self._active_foreground:
                raise RuntimeError("cannot reopen while foreground turns are active")
            self._draining = False

    def ready_for_idle(self, *, idle_seconds: float) -> bool:
        if (
            isinstance(idle_seconds, bool)
            or not isinstance(idle_seconds, (int, float))
            or idle_seconds < 0
        ):
            raise ValueError("idle_seconds must be a nonnegative number")
        # The condition protects the cross-channel activity snapshot without
        # serializing the independent per-session turn locks.
        with self._condition:
            now = monotonic()
            members = tuple(self._members)
            return bool(members) and all(
                getattr(service, "_active_user_requests", 0) == 0
                and (
                    now
                    - getattr(service, "_last_user_activity", now)
                    >= idle_seconds
                )
                for service in members
            )


class EmotionalConversationService(ConversationService):
    """Keep emotional events and reflections outside identity and authority.

    The emotional journal is recorded only after the user turn is durably
    saved by the base service. Periodic reflections run on conversation
    requests or, when enabled, in the application-owned idle worker.
    The model receives bounded, read-only data, not journal write access.
    """

    def __init__(
        self,
        runtime: SofiaRuntime,
        conversation_store: ConversationStore,
        *,
        model_lock=None,
        activity_group: ConversationActivityGroup | None = None,
    ) -> None:
        super().__init__(runtime=runtime, conversation_store=conversation_store)
        self._emotional_journal: EmotionalJournal | None = None
        self._reflection_journal: ReflectionJournal | None = None
        self._clarification_journal: ClarificationJournal | None = None
        self._embodied_expression_planner = EmbodiedExpressionPlanner()
        self._current_expression_plan: EmbodiedExpressionPlan | None = None
        self._previous_expression_modulation = None
        self._evolution_service = None
        self._last_emotion_appraisal_error: str | None = None
        self._pending_emotion_appraisal = None
        self._user_affect_tracker = UserAffectTracker()
        self._last_user_affect_error: str | None = None
        self._pending_user_affect = None
        self._model_lock = model_lock if model_lock is not None else RLock()
        if (
            activity_group is not None
            and not isinstance(activity_group, ConversationActivityGroup)
        ):
            raise TypeError(
                "activity_group must be ConversationActivityGroup or None"
            )
        self._activity_group = (
            activity_group
            if activity_group is not None
            else ConversationActivityGroup()
        )
        # Preserve the per-service activity contract used by deterministic
        # INTERACTION fast paths while aggregating those fields application-wide.
        self._active_user_requests = 0
        self._last_user_activity = monotonic()
        self._activity_group.register(self)

    def set_evolution_service(self, service) -> None:
        """Bridge durable reflections into EVOLVE as hypotheses, never authority."""

        if service is not None and not hasattr(service, "record_evidence"):
            raise TypeError("evolution service must record provenance-backed evidence")
        self._evolution_service = service

    def open(self) -> None:
        super().open()
        try:
            state_path = self._runtime.configuration.state_path
            self._emotional_journal = EmotionalJournal(state_path)
            self._reflection_journal = ReflectionJournal(state_path)
            self._clarification_journal = ClarificationJournal(state_path)
            changes = getattr(self._runtime, "workspace_changes", None)
            if self._runtime.personality is not None and changes is not None:
                record_workspace_observation(
                    event=changes, emotions=self._emotional_journal,
                    reflections=self._reflection_journal,
                    ignored_paths=(Path(state_path),),
                )
        except Exception:
            super().close()
            self._emotional_journal = None
            self._reflection_journal = None
            self._clarification_journal = None
            raise

    @property
    def emotional_journal(self) -> EmotionalJournal:
        if self._emotional_journal is None:
            raise RuntimeError("Emotional journal is not open.")
        return self._emotional_journal

    @property
    def reflection_journal(self) -> ReflectionJournal:
        if self._reflection_journal is None:
            raise RuntimeError("Reflection journal is not open.")
        return self._reflection_journal

    @property
    def clarification_journal(self) -> ClarificationJournal:
        if self._clarification_journal is None:
            raise RuntimeError("Clarification journal is not open.")
        return self._clarification_journal

    @property
    def current_expression_plan(self) -> EmbodiedExpressionPlan | None:
        """Return the present turn's non-authoritative avatar-expression plan."""
        return getattr(self, "_current_expression_plan", None)

    def _principal_context(self) -> PrincipalContext | None:
        session = getattr(self, "_session", None)
        social_store = getattr(self, "_social_store", None)
        if session is None or social_store is None:
            return None
        return social_store.get(session.id)

    def _relationship_subject(self) -> str:
        """Use authenticated session identity when relationship context exists."""
        principal = self._principal_context()
        if principal is not None:
            return principal.principal_id
        core_state = getattr(self._runtime, "core_state", None)
        relationships = (
            getattr(core_state, "relationships", ())
            if core_state is not None
            else ()
        )
        if relationships:
            subject = getattr(relationships[0], "subject", None)
            if isinstance(subject, str) and subject.strip():
                value = subject.strip()
                # The canonical core self-model predates principal IDs and
                # stores Sparks by display name. Emotional persistence uses
                # authenticated principal IDs, so normalize the known local
                # relationship to the same durable key across desktop,
                # Discord, remote chat and background presentation evaluation.
                if value.casefold() == "sparks":
                    return SPARKS_PRINCIPAL_ID
                return value
        return "unbound"

    @property
    def relationship_scope(self) -> SocialScope:
        principal = self._principal_context()
        if principal is not None:
            return principal.relationship_scope
        core_state = getattr(self._runtime, "core_state", None)
        relationships = (
            getattr(core_state, "relationships", ())
            if core_state is not None
            else ()
        )
        if relationships:
            subject = self._relationship_subject()
            if isinstance(subject, str) and subject.strip():
                return SocialScope.relationship(subject)
        # Keep the fallback read scope aligned with _relationship_subject().
        # A relationship-scoped event recorded for the sentinel must not
        # disappear merely because no authenticated principal is available.
        return SocialScope.relationship(self._relationship_subject())

    def observe_background_absence(self, *, now: datetime) -> str | None:
        """Let the running idle worker appraise a real contact gap at this instant."""
        if self._runtime.personality is None:
            return None
        return self.emotional_journal.observe_absence(
            subject=self._relationship_subject(), now=now,
        )

    def current_emotional_state(
        self,
        *,
        now: datetime | None = None,
    ) -> CurrentEmotionalState:
        """Return the current modeled state for this active relationship scope."""
        if self._runtime.personality is None:
            raise RuntimeError("No personality profile is active.")
        current = now or datetime.now(timezone.utc)
        return self.emotional_journal.current_state(
            now=current,
            subject=self._relationship_subject(),
            scope=self.relationship_scope,
        )

    def ready_for_idle_reflection(self, *, idle_seconds: float) -> bool:
        """Avoid idle inference during or shortly after any application channel."""
        activity_group = getattr(self, "_activity_group", None)
        if activity_group is not None:
            return activity_group.ready_for_idle(
                idle_seconds=idle_seconds
            )

        # Preserve the service-level contract for lightweight harnesses that
        # intentionally construct this class without __init__. Production
        # instances always use ConversationActivityGroup.
        if (
            isinstance(idle_seconds, bool)
            or not isinstance(idle_seconds, (int, float))
            or idle_seconds < 0
        ):
            raise ValueError("idle_seconds must be a nonnegative number")
        now = monotonic()
        return (
            getattr(self, "_active_user_requests", 0) == 0
            and now - getattr(self, "_last_user_activity", now)
            >= idle_seconds
        )

    def respond(
        self,
        content: str,
        *,
        principal: PrincipalContext | None = None,
        channel: str = "conversation",
    ):
        """Serialize user inference against application-owned idle inference."""
        started = monotonic()
        self._active_user_requests += 1
        activity = getattr(self, "_activity_group", None)
        try:
            foreground = (
                activity.foreground() if activity is not None else nullcontext()
            )
            with foreground, self._model_lock:
                acquired = monotonic()
                try:
                    if principal is None:
                        response = super().respond(
                            content,
                            channel=channel,
                        )
                    else:
                        response = super().respond(
                            content,
                            principal=principal,
                            channel=channel,
                        )
                    self._persist_pending_emotion_appraisal()
                    self._persist_pending_user_affect()
                    return response
                finally:
                    # Includes request construction/persistence as well as the
                    # model call; Ollama's own timer isolates inference below.
                    emit_performance("conversation",
                        lock_wait_ms=(acquired - started) * 1000,
                        elapsed_ms=(monotonic() - started) * 1000)
                    if performance_trace_enabled():
                        metrics = efficiency_snapshot()
                        emit_performance(
                            "runtime",
                            cache_hits=metrics.cache_hits,
                            cache_misses=metrics.cache_misses,
                            sqlite_queries=metrics.sqlite_queries,
                            sqlite_writes=metrics.sqlite_writes,
                            llm_calls=metrics.llm_calls,
                            concurrent_model_calls=metrics.concurrent_model_calls,
                            peak_concurrent_model_calls=(
                                metrics.peak_concurrent_model_calls
                            ),
                            process_cpu_ms=metrics.process_cpu_ms,
                            peak_rss_bytes=metrics.peak_rss_bytes,
                        )
        finally:
            self._last_user_activity = monotonic()
            self._active_user_requests -= 1

    @property
    def last_emotion_appraisal_error(self) -> str | None:
        """Return the latest non-fatal post-turn appraisal failure."""
        return getattr(self, "_last_emotion_appraisal_error", None)

    @property
    def last_user_affect_error(self) -> str | None:
        """Return the latest non-fatal user-affect envelope failure."""
        return getattr(self, "_last_user_affect_error", None)

    def current_user_affect(
        self,
        *,
        now: datetime | None = None,
    ) -> UserAffectObservation | None:
        """Return the session-local tentative reading for the active person."""
        tracker = getattr(self, "_user_affect_tracker", None)
        if tracker is None:
            return None
        return tracker.current(
            self._relationship_subject(),
            now=now or datetime.now(timezone.utc),
        )

    def _persist_pending_user_affect(self) -> None:
        """Attach a validated assessment to its real user turn in memory only."""
        assessment = getattr(self, "_pending_user_affect", None)
        self._pending_user_affect = None
        if assessment is None:
            return
        try:
            messages = self.messages()
            if len(messages) < 2:
                return
            assistant = messages[-1]
            user = messages[-2]
            if (
                assistant.role is not ConversationRole.ASSISTANT
                or user.role is not ConversationRole.USER
            ):
                return
            tracker = getattr(self, "_user_affect_tracker", None)
            if tracker is None:
                tracker = UserAffectTracker()
                self._user_affect_tracker = tracker
            tracker.record(UserAffectObservation(
                subject=self._relationship_subject(),
                evidence_ref=user.id,
                observed_at=user.created_at,
                assessment=assessment,
            ))
        except Exception as exc:
            self._last_user_affect_error = type(exc).__name__
            _LOG.exception(
                "Validated user affect could not be retained for this session"
            )

    def _persist_pending_emotion_appraisal(self) -> None:
        """Persist the already-validated one-call appraisal after the reply."""
        appraisal = getattr(self, "_pending_emotion_appraisal", None)
        self._pending_emotion_appraisal = None
        if appraisal is None or not hasattr(self, "_runtime"):
            return
        messages = self.messages()
        if len(messages) < 2:
            return
        assistant = messages[-1]
        user = messages[-2]
        if (
            assistant.role is not ConversationRole.ASSISTANT
            or user.role is not ConversationRole.USER
        ):
            return

        try:
            self.emotional_journal.record(
                event_id=f"conversation-appraisal:{assistant.id}",
                source="inferred",
                evidence_ref=assistant.id,
                description=(
                    f"Post-conversation self-appraisal: {appraisal.reason}"
                )[:320],
                emotions=appraisal.emotions,
                occurred_at=assistant.created_at,
                subject=self._relationship_subject(),
                scope=self.relationship_scope,
            )
        except Exception as exc:
            self._last_emotion_appraisal_error = type(exc).__name__
            _LOG.exception(
                "Validated emotional appraisal could not be persisted; the "
                "durable conversation response is unchanged"
            )

    def _finalize_response(
        self,
        request: CognitiveRequest,
        response: CognitiveResponse,
        *,
        principal: PrincipalContext | None,
    ) -> CognitiveResponse:
        """Strip and retain the optional host-validated appraisal envelope."""
        self._pending_emotion_appraisal = None
        self._last_emotion_appraisal_error = None
        self._pending_user_affect = None
        self._last_user_affect_error = None
        try:
            visible, appraisal = ConversationEmotionAppraiser.extract_response(
                response.content
            )
        except Exception as exc:
            self._last_emotion_appraisal_error = type(exc).__name__
            _LOG.warning("Discarding malformed emotional appraisal envelope")
            visible = ConversationEmotionAppraiser.strip_untrusted_envelope(
                response.content
            )
            appraisal = None
        self._pending_emotion_appraisal = appraisal
        try:
            messages = self.messages()
        except (AttributeError, RuntimeError):
            # Small host/unit paths can finalize a supplied request without an
            # active persisted session. Production conversation always has one.
            messages = ()
        user_content = next(
            (
                item.content for item in reversed(messages)
                if item.role is ConversationRole.USER
            ),
            next(
                (
                    item.content for item in reversed(request.messages)
                    if item.role is CognitiveRole.USER
                ),
                "",
            ),
        )
        try:
            visible, user_affect = UserAffectAppraiser.extract_response(
                visible,
                user_content=user_content,
            )
        except Exception as exc:
            self._last_user_affect_error = type(exc).__name__
            _LOG.warning("Discarding malformed user-affect envelope")
            visible = UserAffectAppraiser.strip_untrusted_envelope(visible)
            user_affect = None
        self._pending_user_affect = user_affect
        # No malformed or misordered private envelope may reach persistence or
        # presentation, even when the other envelope validated successfully.
        visible = ConversationEmotionAppraiser.strip_untrusted_envelope(visible)
        visible = UserAffectAppraiser.strip_untrusted_envelope(visible)
        if not visible:
            visible = "I couldn't settle that response cleanly. Try me again."
        if visible == response.content:
            return response
        return replace(response, content=visible)

    def _matrix_finalize_response(
        self,
        request: CognitiveRequest,
        response: CognitiveResponse,
        *,
        principal: PrincipalContext | None,
    ) -> CognitiveResponse:
        """Never retain an appraisal from a draft rejected by the matrix."""
        settled = super()._matrix_finalize_response(
            request,
            response,
            principal=principal,
        )
        validation = getattr(self, "_current_response_validation", None)
        if (
            validation is not None
            and validation.disposition is ResponseValidationDisposition.FALLBACK
        ):
            self._pending_emotion_appraisal = None
            self._pending_user_affect = None
        return settled

    def clarify_event(self, *, event_id: str, message_id: str) -> None:
        """Explicitly link one saved user turn to one selected event.

        An authorized application UI must resolve and confirm the event ID.
        Neither the LLM nor this method guesses a target from arbitrary text,
        infers a new emotion, or rewrites the original reaction.
        """
        if self._runtime.personality is None:
            raise RuntimeError("No personality profile is active.")
        if self._session is None:
            raise RuntimeError("A conversation session must be active.")
        matching = tuple(message for message in self.messages() if message.id == message_id)
        if len(matching) != 1 or matching[0].role is not ConversationRole.USER:
            raise ValueError("Clarification must reference a saved user message in this session.")
        message = matching[0]
        self.clarification_journal.record(
            event_id=event_id, message_id=message.id,
            content=message.content, created_at=message.created_at,
        )

    def reflect_on_event(self, *, event_id: str) -> ReflectionOutcome:
        """Generate one optional thought from explicitly selected evidence.

        A trusted application caller selects the event. No automatic tool
        action or message delivery is possible through this method.
        """
        # Existing mock-only tests instantiate the service without __init__.
        started = monotonic()
        with getattr(self, "_model_lock", nullcontext()):
            acquired = monotonic()
            try:
                return self._reflect_on_event_locked(event_id=event_id)
            finally:
                emit_performance("idle_reflection",
                    lock_wait_ms=(acquired - started) * 1000,
                    elapsed_ms=(monotonic() - started) * 1000)

    def reconsider_due_reflection(
        self, *, now: datetime, influence: ContinuityInfluence,
    ) -> ReflectionOutcome | None:
        """Revisit one due private thought for possible authorized outreach."""
        due = self.reflection_journal.due_followups(
            now=now,
            limit=1,
            scope=self.relationship_scope,
        )
        if not due:
            return None
        return ThoughtAgent(
            generate=self._runtime.respond,
            reflections=self.reflection_journal,
        ).reconsider(
            followup=due[0],
            now=now,
            influence=influence,
        )

    def _reflect_on_event_locked(self, *, event_id: str) -> ReflectionOutcome:
        if self._runtime.personality is None:
            raise RuntimeError("No personality profile is active.")
        if self._session is None:
            raise RuntimeError("A conversation session must be active.")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("A recorded event ID is required.")
        now = datetime.now(timezone.utc)
        matching = tuple(
            event for event in self.emotional_journal.recent(
                now=now,
                days=366,
                limit=50,
                scope=self.relationship_scope,
            ) if event.event_id == event_id
        )
        if len(matching) != 1:
            raise KeyError("No matching recent emotional event was recorded.")
        event = matching[0]
        agent = ThoughtAgent(
            generate=self._runtime.respond,
            reflections=self.reflection_journal,
        )
        current_state = self.emotional_journal.current_state(
            now=now,
            subject=self._relationship_subject(),
            scope=self.relationship_scope,
        )
        environment_service = getattr(
            self._runtime,
            "environment_service",
            None,
        )
        environment = (
            environment_service.snapshot(
                now=now,
                refresh_providers=False,
            )
            if environment_service is not None
            else None
        )
        influence = ContinuityInfluence.from_state(
            emotion=current_state,
            environment=environment,
        )
        outcome = agent.reflect(
            event=event,
            now=now,
            influence=influence,
        )
        if outcome.thought_id is not None:
            thoughts = tuple(
                thought for thought in self.reflection_journal.recent_thoughts(
                    limit=50,
                    scope=event.scope,
                )
                if thought.thought_id == outcome.thought_id
            )
            if len(thoughts) != 1:
                raise RuntimeError("Recorded reflection could not be reloaded.")
            thought = thoughts[0]
            evolution = getattr(self, "_evolution_service", None)
            if evolution is not None:
                evolution.record_evidence(
                    evidence_id=f"reflection:{thought.thought_id}",
                    kind="reflection-hypothesis",
                    source_ref=f"reflection:{thought.thought_id}",
                    summary=(
                        "A durable reflection generated a possible improvement "
                        "hypothesis; its cited source evidence still requires review."
                    ),
                    payload={
                        "thought_id": thought.thought_id,
                        "subject": thought.subject,
                        "content": thought.content,
                        "evidence_refs": list(thought.evidence_refs),
                        "emotion_labels": list(thought.emotions),
                    },
                    observed_at=thought.created_at,
                )
            if thought.emotions:
                self.emotional_journal.record(
                    event_id=f"reflection-affect:{thought.thought_id}",
                    source="inferred",
                    evidence_ref=thought.thought_id,
                    description=(
                        "A recorded background reflection revisited prior evidence; "
                        "its modeled affect now contributes to current emotional state."
                    ),
                    emotions=thought.emotions,
                    occurred_at=thought.created_at,
                    subject=event.subject,
                    scope=event.scope,
                )
        return outcome

    def close(self) -> None:
        super().close()
        self._emotional_journal = None
        self._reflection_journal = None
        self._clarification_journal = None
        self._current_expression_plan = None
        self._previous_expression_modulation = None
        tracker = getattr(self, "_user_affect_tracker", None)
        if tracker is not None:
            tracker.clear()
        self._pending_user_affect = None

    def _should_record_legacy_affection(self, user) -> bool:
        """Subclass hook: independent policy may veto a legacy head-pat cue."""
        return True

    def _build_request(self) -> CognitiveRequest:
        request = super()._build_request()
        if self._runtime.personality is None:
            return request
        messages = self.messages()
        subject = self._relationship_subject()
        if messages and messages[-1].role is ConversationRole.USER:
            user = messages[-1]
            self.emotional_journal.record_user_cue(
                message_id=user.id, content=user.content,
                occurred_at=user.created_at, subject=subject,
                allow_legacy_affection=self._should_record_legacy_affection(user),
            )
            self.emotional_journal.record_return_expectation_from_user_cue(
                message_id=user.id, content=user.content,
                occurred_at=user.created_at, subject=subject,
            )
            self.emotional_journal.observe_contact(
                subject=subject, message_id=user.id, occurred_at=user.created_at,
            )
        context_plan = getattr(self, "_current_context_plan", None)
        emotion_allowed = (
            context_plan is None
            or context_plan.allows(MatrixDomain.EMOTION)
        )

        now = datetime.now(timezone.utc)
        scope = self.relationship_scope
        current_state = self.emotional_journal.current_state(
            now=now,
            subject=subject,
            scope=scope,
        )
        environment_allowed = (
            context_plan is None
            or context_plan.allows(MatrixDomain.ENVIRONMENT)
        )
        environment_service = (
            getattr(
                self._runtime,
                "environment_service",
                None,
            )
            if environment_allowed
            else None
        )
        environment = (
            environment_service.snapshot(
                now=now,
                refresh_providers=False,
            )
            if environment_service is not None
            else None
        )
        influence = ContinuityInfluence.from_state(
            emotion=current_state,
            environment=environment,
        )
        if not emotion_allowed:
            influence = replace(
                influence,
                primary_emotion_evidence_refs=(),
                emotional_tone="neutral",
                primary_emotion=None,
                primary_intensity=0.0,
                foreground_emotion_evidence_refs=(),
                foreground_emotion=None,
                foreground_intensity=0.0,
                active_emotions=(),
            )
        self._current_contextual_influence = influence

        expression_modulation = derive_expression_modulation(
            turn=getattr(self, "_current_turn_matrix", None),
            influence=influence,
            user_text=("" if not messages else messages[-1].content),
            neuro=getattr(self, "_current_neuro_snapshot", None),
            previous=getattr(self, "_previous_expression_modulation", None),
        )
        self._previous_expression_modulation = expression_modulation

        expression_plan = None
        current_user = (
            messages[-1]
            if messages and messages[-1].role is ConversationRole.USER
            else None
        )
        if current_user is not None:
            planner = getattr(self, "_embodied_expression_planner", None)
            if planner is None:
                planner = EmbodiedExpressionPlanner()
                self._embodied_expression_planner = planner
            recent_assistant = tuple(
                item.content
                for item in messages[:-1]
                if item.role is ConversationRole.ASSISTANT
            )[-8:]
            expression_plan = planner.plan(
                message_id=current_user.id,
                influence=influence,
                recent_assistant_messages=recent_assistant,
            )
        self._current_expression_plan = expression_plan

        projections = []
        projections.append(expression_modulation.prompt())
        tracker = getattr(self, "_user_affect_tracker", None)
        if tracker is None:
            tracker = UserAffectTracker()
            self._user_affect_tracker = tracker
        previous_user_affect = tracker.current(subject, now=now)
        if previous_user_affect is not None:
            projections.append(
                UserAffectAppraiser.context_prompt(previous_user_affect)
            )
        # Current-turn affect adaptation is a conversational calibration layer,
        # not Sofía's EMOTION matrix state. Keep it available in technical and
        # operational turns where frustration or overload still matters.
        projections.append(UserAffectAppraiser.response_instruction())
        if emotion_allowed:
            projections.extend((
                self.emotional_journal.current_state_prompt(
                    now=now,
                    subject=subject,
                    scope=scope,
                ),
                influence.prompt(),
                ConversationEmotionAppraiser.response_instruction(
                    current_state
                ),
            ))
        if (
            expression_plan is not None
            and (
                expression_plan.primary is not None
                or expression_plan.avoid_recent
            )
        ):
            projections.append(expression_plan.prompt())

        # Project only provenance relevant to this turn. A fresh appraisal
        # created from the current user message may be shown immediately, while
        # older journal history requires an explicit causal/history question.
        # This preserves evidence-linked emotion without letting old reunion or
        # missed-you rows hijack unrelated "hru", weather, or mood turns.
        request_user = (
            request.messages[-1]
            if request.messages
            and request.messages[-1].role is CognitiveRole.USER
            else None
        )
        latest_text = (
            current_user.content
            if current_user is not None
            else ("" if request_user is None else request_user.content)
        )
        causal_last_turn = (
            emotion_allowed
            and context_plan is not None
            and context_plan.history_policy is HistoryPolicy.LAST_TURN
            and context_plan.allows(MatrixDomain.EMOTION)
            and _CAUSAL_LAST_TURN_QUERY.fullmatch(latest_text) is not None
        )
        history_requested = (
            emotion_allowed
            and (
                _CONTEXT_HISTORY_QUERY.search(latest_text) is not None
                or causal_last_turn
            )
        )
        if emotion_allowed:
            emotional_context = self.emotional_journal.prompt_context(
                now=now,
                subject=subject,
                scope=scope,
                evidence_refs=(
                    None
                    if history_requested
                    else (() if current_user is None else (current_user.id,))
                ),
            )
            if emotional_context is not None:
                projections.append(emotional_context)

        clarifications = getattr(self, "_clarification_journal", None)
        if history_requested and clarifications is not None:
            clarification_context = clarifications.prompt_context(now=now)
            if clarification_context is not None:
                projections.append(clarification_context)

        # Completed reflections may inform an explicit historical/topic question,
        # but only when their stored subject/content overlaps the user's topic.
        reflections = getattr(self, "_reflection_journal", None)
        if reflections is not None:
            reflections.reflect_due(now=now, scope=scope)
            if history_requested:
                reflection_context = reflections.prompt_context(
                    scope=scope,
                    query=latest_text,
                )
                if reflection_context is not None:
                    projections.append(reflection_context)
        if not projections:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                      content="\n\n".join(projections)), *request.messages),
            tools=request.tools,
            allow_tools=request.allow_tools,
            capability_allowlist=request.capability_allowlist,
            route_hint=request.route_hint,
        )

    def _v2_expression_context(
        self,
        *,
        current_user,
        principal: PrincipalContext | None,
    ):
        """Build personality modulation only after a validated draft exists."""
        _ = principal
        if self._runtime.personality is None:
            return None
        subject = self._relationship_subject()
        self.emotional_journal.record_user_cue(
            message_id=current_user.id,
            content=current_user.content,
            occurred_at=current_user.created_at,
            subject=subject,
            allow_legacy_affection=self._should_record_legacy_affection(current_user),
        )
        self.emotional_journal.record_return_expectation_from_user_cue(
            message_id=current_user.id,
            content=current_user.content,
            occurred_at=current_user.created_at,
            subject=subject,
        )
        self.emotional_journal.observe_contact(
            subject=subject,
            message_id=current_user.id,
            occurred_at=current_user.created_at,
        )
        now = datetime.now(timezone.utc)
        state = self.emotional_journal.current_state(
            now=now,
            subject=subject,
            scope=self.relationship_scope,
        )
        environment = self._runtime.environment_service.snapshot(
            now=now,
            refresh_providers=False,
        )
        influence = ContinuityInfluence.from_state(
            emotion=state,
            environment=environment,
        )
        modulation = derive_expression_modulation(
            turn=getattr(self, "_current_turn_matrix", None),
            influence=influence,
            user_text=current_user.content,
            neuro=getattr(self, "_current_neuro_snapshot", None),
            previous=getattr(self, "_previous_expression_modulation", None),
        )
        self._current_contextual_influence = influence
        self._previous_expression_modulation = modulation
        return modulation
