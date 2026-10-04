"""Assemble and dispatch a response from the runtime's canonical services."""
from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import replace
from sofia.cognition.context import CognitiveContext
from sofia.cognition.matrix import ContextPlan, MatrixDomain, PrivacyProjectionPlan
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.cognition.operation import CognitiveOperation
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.environment.prompt import environment_details_relevant
from sofia.filesystem.model import FilesystemResult
from sofia.personality.influence import ContinuityInfluence
from sofia.personality.reflection import ReflectionJournal
from sofia.social.model import PrincipalContext, SocialScope
from sofia.social.principals import SPARKS_PRINCIPAL_ID

if TYPE_CHECKING:
    from sofia.runtime.runtime import SofiaRuntime


def respond_with_runtime_context(
    runtime: SofiaRuntime,
    request: CognitiveRequest,
    filesystem_results: tuple[FilesystemResult, ...] = (),
    *,
    principal: PrincipalContext | None = None,
    context_plan: ContextPlan | None = None,
    privacy_plan: PrivacyProjectionPlan | None = None,
    contextual_influence: ContinuityInfluence | None = None,
) -> CognitiveResponse:
    if not isinstance(request, CognitiveRequest):
        raise TypeError(
            "SofiaRuntime request must be a CognitiveRequest."
        )

    if principal is not None and not isinstance(principal, PrincipalContext):
        raise TypeError(
            "SofiaRuntime principal must be a PrincipalContext or None."
        )

    if context_plan is not None and not isinstance(
        context_plan, ContextPlan
    ):
        raise TypeError(
            "SofiaRuntime context_plan must be a ContextPlan or None."
        )
    if privacy_plan is not None and not isinstance(
        privacy_plan, PrivacyProjectionPlan
    ):
        raise TypeError(
            "SofiaRuntime privacy_plan must be a PrivacyProjectionPlan or None."
        )
    if contextual_influence is not None and not isinstance(
        contextual_influence,
        ContinuityInfluence,
    ):
        raise TypeError(
            "SofiaRuntime contextual_influence must be "
            "a ContinuityInfluence or None."
        )

    if contextual_influence is not None and context_plan is not None:
        if not context_plan.allows(MatrixDomain.EMOTION):
            contextual_influence = replace(
                contextual_influence,
                primary_emotion_evidence_refs=(),
                emotional_tone="neutral",
                primary_emotion=None,
                primary_intensity=0.0,
                active_emotions=(),
            )
        if not context_plan.allows(MatrixDomain.ENVIRONMENT):
            contextual_influence = replace(
                contextual_influence,
                daypart="unknown",
                season=None,
                daylight=None,
                weather_condition=None,
                temperature_c=None,
                weather_freshness=None,
                location_freshness=None,
                daypart_evidence_refs=(),
                season_evidence_refs=(),
                weather_evidence_refs=(),
            )

    if privacy_plan is not None:
        if principal is None and privacy_plan.principal_id is not None:
            raise ValueError(
                "privacy plan is bound but runtime principal is absent"
            )
        if principal is not None and (
            privacy_plan.principal_id != principal.principal_id
            or privacy_plan.audience_id != principal.audience_id
            or privacy_plan.audience_kind != principal.audience_kind.value
        ):
            raise ValueError(
                "privacy plan does not match authenticated runtime principal"
            )

    selective_context = context_plan is not None

    def include_domain(*domains: MatrixDomain) -> bool:
        if not selective_context or context_plan is None:
            return True
        return any(context_plan.allows(domain) for domain in domains)

    if not isinstance(filesystem_results, tuple):
        raise TypeError(
            "SofiaRuntime filesystem_results must be a tuple."
        )

    for result in filesystem_results:
        if not isinstance(result, FilesystemResult):
            raise TypeError(
                "SofiaRuntime filesystem_results must contain "
                "FilesystemResult instances."
            )

    user_content = _latest_user_content(request)
    environment_query = user_content
    if (
        user_content
        and runtime._environment_query_resolver.is_generic_source_followup(
            user_content
        )
    ):
        previous_user_content = _previous_user_content(request)
        if (
            previous_user_content
            and runtime._environment_query_resolver.is_weather_or_forecast_query(
                previous_user_content
            )
        ):
            environment_query = "what is your weather source"

    reflection_answer = None
    if (
        user_content
        and runtime._reflection_query_resolver.might_match(user_content)
    ):
        reflection_journal = ReflectionJournal(
            runtime._configuration.state_path
        )
        thoughts = list(
            reflection_journal.recent_thoughts(
                limit=3,
                scope=SocialScope.global_scope(),
            )
        )
        if (
            principal is not None
            and (
                privacy_plan is None
                or privacy_plan.allow_relationship_scope
            )
        ):
            thoughts.extend(
                reflection_journal.recent_thoughts(
                    limit=3,
                    scope=principal.relationship_scope,
                )
            )
        reflection_answer = runtime._reflection_query_resolver.resolve(
            user_content,
            thoughts=tuple(thoughts),
        )

    if user_content:
        status_answer = runtime._operational_status_query_resolver.resolve(
            user_content,
            selection=CognitiveModelSelection.from_configuration(
                runtime._configuration
            ),
            capability_names=runtime._capability_system.capability_names(),
            authority=runtime.current_authority(),
        )
        if status_answer.recognized:
            return CognitiveResponse(content=status_answer.content)

    presentation = runtime.avatar_projection_for(
        principal=principal,
    )
    if (
        user_content
        and include_domain(MatrixDomain.AVATAR)
        and runtime._embodiment is not None
        and presentation is not None
        and runtime._avatar_presentation is not None
    ):
        self_fact = runtime._avatar_self_fact_resolver.resolve(
            user_content,
            embodiment=runtime._embodiment,
            presentation=presentation,
            available_outfit_ids=runtime._avatar_presentation.available_outfit_ids,
            wardrobe_matrix=runtime._avatar_matrix_for(presentation),
        )
        if self_fact.recognized:
            if (
                runtime._avatar_self_fact_resolver.allows_private_projection(
                    user_content
                )
                and (
                    privacy_plan is None
                    or privacy_plan.allow_private_presentation_candidate
                )
            ):
                private_grant = runtime._private_presentation_grants.resolve(
                    principal=principal,
                    explicit_current_opt_in=True,
                )
                if private_grant is not None:
                    private_presentation = runtime.avatar_projection_for(
                        principal=principal,
                        private_grant=private_grant,
                    )
                    if private_presentation is not None:
                        self_fact = runtime._avatar_self_fact_resolver.resolve(
                            user_content,
                            embodiment=runtime._embodiment,
                            presentation=private_presentation,
                            available_outfit_ids=(
                                runtime._avatar_presentation.available_outfit_ids
                            ),
                            wardrobe_matrix=runtime._avatar_matrix_for(
                                private_presentation
                            ),
                        )
            if (
                reflection_answer is not None
                and reflection_answer.recognized
            ):
                return CognitiveResponse(
                    content=(
                        reflection_answer.content
                        + "\n\n"
                        + self_fact.content
                    )
                )
            return CognitiveResponse(content=self_fact.content)

    if (
        reflection_answer is not None
        and reflection_answer.recognized
    ):
        return CognitiveResponse(content=reflection_answer.content)

    environment_snapshot = None
    environment_details_needed = environment_details_relevant(
        user_content or None
    )
    environment_service = getattr(
        runtime,
        "_environment_service",
        None,
    )
    if (
        environment_service is not None
        and environment_query
        and include_domain(MatrixDomain.ENVIRONMENT)
        and runtime._environment_query_resolver.might_match(
            environment_query
        )
    ):
        environment_snapshot = (
            environment_service.snapshot(
                refresh_providers=environment_details_needed,
            )
        )
        environment_answer = (
            runtime._environment_query_resolver.resolve(
                environment_query,
                snapshot=environment_snapshot,
            )
        )
        if environment_answer.recognized:
            return CognitiveResponse(
                content=environment_answer.content
            )

    if include_domain(MatrixDomain.MEMORY):
        audience_scope_allowed = (
            privacy_plan is None
            or privacy_plan.allow_audience_scope
        )
        if audience_scope_allowed:
            memories = runtime._memory_system.recall_relevant(
                user_content,
                principal=principal,
                influence=contextual_influence,
            )
        else:
            memories = ()

        historical_private_allowed = (
            privacy_plan is None
            or privacy_plan.allow_historical_private_scope
        )
        if audience_scope_allowed and historical_private_allowed:
            historical_conversation_evidence = (
                runtime._memory_system.recall_historical_evidence(
                    user_content,
                    principal=principal,
                )
            )
        else:
            historical_conversation_evidence = ()
    else:
        memories = ()
        historical_conversation_evidence = ()

    measurement_query = None

    if (
        runtime._embodiment is not None
        and include_domain(MatrixDomain.AVATAR)
    ):
        measurement_query = runtime._measurement_query_resolver.resolve(
            query=user_content,
            embodiment=runtime._embodiment,
        )

    if (
        environment_snapshot is None
        and environment_service is not None
        and include_domain(MatrixDomain.ENVIRONMENT)
    ):
        environment_snapshot = (
            environment_service.snapshot(
                refresh_providers=environment_details_needed,
            )
        )

    operation = CognitiveOperation(
        context=CognitiveContext(
            request=request,
            identity=runtime._identity,
            personality=runtime._personality,
            constitution=runtime._constitution,
            embodiment=(
                runtime._embodiment
                if include_domain(
                    MatrixDomain.AVATAR,
                    MatrixDomain.INTERACTION,
                )
                else None
            ),
            measurement_query=measurement_query,
            core_state=runtime._core_state,
            memories=memories,
            historical_conversation_evidence=(
                historical_conversation_evidence
            ),
            operational_state=(
                runtime.operational_state
                if include_domain(
                    MatrixDomain.COGNITION,
                    MatrixDomain.MACHINE,
                    MatrixDomain.OPS,
                    MatrixDomain.AUTHORITY,
                    MatrixDomain.CONTINUITY,
                )
                else None
            ),
            runtime_continuity=(
                runtime._runtime_continuity
                if include_domain(MatrixDomain.CONTINUITY)
                else None
            ),
            filesystem_results=filesystem_results,
            workspace_changes=(
                runtime._workspace_changes
                if include_domain(MatrixDomain.CONTINUITY)
                else None
            ),
            operational_self_model=(
                runtime.operational_self_model
                if include_domain(
                    MatrixDomain.COGNITION,
                    MatrixDomain.MACHINE,
                    MatrixDomain.OPS,
                )
                else None
            ),
            avatar_presentation=(
                runtime.avatar_projection_for(principal=principal)
                if include_domain(
                    MatrixDomain.AVATAR,
                    MatrixDomain.INTERACTION,
                )
                else None
            ),
            environment_snapshot=(
                environment_snapshot
                if include_domain(MatrixDomain.ENVIRONMENT)
                else None
            ),
            principal=principal,
            private_adult_authority=(
                runtime._permission_store.private_adult_authority()
                if (
                    principal is not None
                    and principal.principal_id == SPARKS_PRINCIPAL_ID
                    and principal.audience_kind.value == "private"
                )
                else None
            ),
        ),
        authority=runtime.current_authority(),
    )

    return runtime._cognitive_system.respond(
        operation
    )


def _previous_user_content(
    request: CognitiveRequest,
) -> str:
    seen_latest = False
    for message in reversed(request.messages):
        if message.role.value != "user":
            continue
        if not seen_latest:
            seen_latest = True
            continue
        return message.content
    return ""


def _latest_user_content(
    request: CognitiveRequest,
) -> str:
    for message in reversed(
        request.messages
    ):
        if message.role.value == "user":
            return message.content

    return ""