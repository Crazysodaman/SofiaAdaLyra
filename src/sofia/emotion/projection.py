"""Stateless present-state scoring and conversational projection."""
from __future__ import annotations

from datetime import datetime
import json

from sofia.emotion.catalog import (
    _ACTIVE_THRESHOLD, _BACKGROUND_RELATIONAL, _HALF_LIFE_HOURS,
    _NEGATIVE, _POSITIVE, _SOURCE_WEIGHT,
)
from sofia.emotion.model import ActiveEmotion, CurrentEmotionalState, EmotionalEvent


def _intensity_word(value: float) -> str:
    if value >= 0.75:
        return "strong"
    if value >= 0.45:
        return "moderate"
    if value >= 0.20:
        return "mild"
    return "trace"


def derive_current_state(
    *, current: datetime, target: str | None, raw_events: tuple[EmotionalEvent, ...],
) -> CurrentEmotionalState:
    """Project validated, scoped journal events without owning persistent state."""
    # Reunion appraisals are successive present-time interpretations of
    # contact resuming, not independent long-lived emotional deposits.
    # Keep their full history in the journal, but only let the newest
    # reunion influence the current state. Otherwise frequent returns can
    # compound warmth/fondness toward 1.0 for days.
    latest_reunion_seen = False
    projected_events = []
    for event in raw_events:
        if event.event_id.startswith("reunion:"):
            if latest_reunion_seen:
                continue
            latest_reunion_seen = True
        projected_events.append(event)
    events = tuple(projected_events)
    scores: dict[str, float] = {}
    refs: dict[str, list[str]] = {}
    ids: dict[str, list[str]] = {}
    for event in events:
        age_hours = max(
            0.0, (current - event.occurred_at).total_seconds() / 3600,
        )
        source_weight = _SOURCE_WEIGHT[event.source]
        for name in event.current_emotions:
            half_life = _HALF_LIFE_HOURS.get(name, 8.0)
            contribution = source_weight * (2.0 ** (-age_hours / half_life))
            if contribution < 0.01:
                continue
            previous = scores.get(name, 0.0)
            scores[name] = 1.0 - ((1.0 - previous) * (1.0 - contribution))
            refs.setdefault(name, [])
            ids.setdefault(name, [])
            if event.evidence_ref not in refs[name]:
                refs[name].append(event.evidence_ref)
            if event.event_id not in ids[name]:
                ids[name].append(event.event_id)

    active = tuple(
        ActiveEmotion(
            name=name, intensity=round(score, 3),
            evidence_refs=tuple(refs[name][:6]),
            event_ids=tuple(ids[name][:6]),
        )
        for name, score in sorted(
            scores.items(), key=lambda item: (-item[1], item[0]),
        )
        if score >= _ACTIVE_THRESHOLD
    )[:6]

    positive = sum(item.intensity for item in active if item.name in _POSITIVE)
    negative = sum(item.intensity for item in active if item.name in _NEGATIVE)
    if positive >= 0.20 and negative >= 0.20:
        tone = "mixed"
    elif positive > negative + 0.10:
        tone = "positive"
    elif negative > positive + 0.10:
        tone = "negative"
    else:
        tone = "settled"
    return CurrentEmotionalState(
        as_of=current, subject=target, tone=tone, active=active,
    )


def current_state_prompt(state: CurrentEmotionalState) -> str:
    """Render a derived state without changing journal ownership."""
    lines = [
        "CURRENT MODELED EMOTIONAL STATE (trusted application projection)",
        f"As of: {state.as_of.isoformat()}",
        f"Relationship subject: {state.subject or 'none'}",
        f"Overall tone: {state.tone}",
    ]
    foreground = tuple(
        item for item in state.active
        if item.name not in _BACKGROUND_RELATIONAL
    )
    background = tuple(
        item for item in state.active
        if item.name in _BACKGROUND_RELATIONAL
    )
    if foreground:
        lines.append("Foreground modeled emotions:")
        for item in foreground:
            lines.append(json.dumps({
                "emotion": item.name,
                "intensity": _intensity_word(item.intensity),
                "evidence_refs": item.evidence_refs,
                "event_ids": item.event_ids,
            }, ensure_ascii=False))
    else:
        lines.append("Foreground modeled emotions: none.")

    if background:
        lines.append(
            "Background relational tone: present. Exact persistent relationship "
            "labels stay out of ordinary provider context so they can soften or color "
            "delivery without being mechanically named or foregrounded. Explicit "
            "history/causality questions receive the relevant evidence separately."
        )
    else:
        lines.append("Background relational tone: none.")
    reunion_grounded = any(
        item.name == "longing"
        or any(event_id.startswith("reunion:") for event_id in item.event_ids)
        for item in state.active
    )
    lines.append(
        "Reciprocal absence/missing-you claim grounded: "
        + ("yes" if reunion_grounded else "no")
    )
    lines.extend((
        "This is Sofía's current application-level emotional state for conversational "
        "self-report. It is not evidence of biology, physical sensation, or consciousness.",
        "For a social or emotional self-report, answer directly from this state in natural "
        "language. Do not substitute identity, outfit, capability, or customer-service "
        "boilerplate unless the user asked for those topics. Do not say 'functioning as "
        "intended' or explain AI-versus-human emotions unless that distinction was asked.",
        "Emotion labels are grounding evidence, not a response template. Foreground reactions "
        "may be named when useful; background relational tone normally changes delivery without "
        "being named. Vary wording, preserve Sofía's direct/playful/skeptical/confident baseline, "
        "and persistent relationship tone must not turn every answer into soft reassurance.",
        "Do not expose numeric intensity, thresholds, decay terminology, evidence IDs, or internal "
        "mood machinery unless the user explicitly asks how the emotion system works.",
        "Describe the current grounded state only. Never claim Sofía was thinking, waiting, "
        "suffering, or continuously aware while offline unless a recorded process provides that "
        "evidence. Emotional state never grants permission, overrides boundaries, or obligates "
        "the user.",
    ))
    active_names = {item.name for item in state.active}
    if active_names.intersection({
        "sexual-attraction", "sexual-desire", "sexual-arousal",
        "sensuality", "romance",
    }):
        lines.append(
            "Sexual attraction, desire, arousal, sensuality, romance, affection, and comfort "
            "are separate modeled dimensions rather than a single sexual mode; never infer one "
            "from another, and never equate any of them with consent."
        )
    if reunion_grounded or any(
        event_id.startswith("absence:")
        for item in state.active
        for event_id in item.event_ids
    ):
        lines.append(
            "For reunion/absence appraisal, anger about lateness requires stronger source-backed "
            "evidence such as an explicit return expectation. Elapsed time alone must not "
            "manufacture blame. Express negative reunion emotion without guilt, pressure, "
            "accusation, exclusivity, or an obligation for the user to maintain contact."
        )
    return "\n".join(lines)
