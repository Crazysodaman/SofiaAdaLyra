"""MENTOR whole-system inventory, independent of task-completion percentages.

Source presence is *not* evidence of a working tool, passed regression,
live host or personality quality. A status of unverified is honest.
Only static, allowlisted package paths and CI reference filenames appear
in the publicly shareable summary; no local hosts, memories or transcripts.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json

@dataclass(frozen=True)
class SystemPart:
    id: str
    title: str
    description: str
    packages: tuple[str, ...]
    source_files: tuple[str, ...]
    test_files: tuple[str, ...]
    phase_ids: tuple[str, ...]
    success_checks: tuple[str, ...]

# Source paths are concrete anchors, not claims that an entire family works.
# A part may use several task phases, and a phase may contribute to many parts.
PARTS = (
    SystemPart("identity", "Identity and Constitution",
               "Consistent identity across model, host and channel; integrity and authority boundaries.",
               ("identity", "constitution"),
               ("src/sofia/personality/personality.json",),
               ("test/test_personality_pipeline.py",), ("00","02","08"),
               ("Identity invariants survive restart/model changes", "No authority granted by style or prompts")),
    SystemPart("personality", "Personality and response quality",
               "How real responses match documented traits, technical skepticism, warmth, humor and context.",
               ("personality", "social"),
               ("src/sofia/personality/personality.json",),
               ("test/test_personality_pipeline.py", "test/test_personality_expression_g9.py"),
               ("05","08"),
               ("Score owner-approved actual replies against an explicit rubric", "Correct unsupported assumptions without aggression", "Personality never replaces facts")),
    SystemPart("conversation", "Conversation and cross-channel continuity",
               "Authenticated dialogue, durable turns, voice/Discord/Android client delivery and privacy.",
               ("conversation", "discord", "mobile", "application"),
               ("src/sofia/platform.application/conversation_service.py",),
               (), ("05","08","10"),
               ("Resume source-backed topics across permitted channels", "Respect privacy and interruption")),
    SystemPart("cognition", "Cognition, reasoning and decision-making",
               "Uncertainty, multi-step reasoning, evidence use, tool selection and correction.",
               ("cognition",),
               ("src/sofia/platform.application/bootstrap.py",),
               (), ("06","11"),
               ("Separate observations from hypotheses", "Independent checks before real-world claims")),
    SystemPart("memory", "Memory, provenance and autobiographical continuity",
               "Working/episodic/semantic memory, temporal revisions, deletion and source/audience boundaries.",
               ("memory",),
               (), (), ("06","07"),
               ("Accurate recall across sessions", "Correction, revocation and privacy tests")),
    SystemPart("learning", "Learning and generalization",
               "Reusable skills, failure analysis, paired unfamiliar-task A→B transfer and model adaptation.",
               ("learning", "generalization"),
               ("src/sofia/generalization/service.py",),
               ("test/test_generalization_foundation.py", "test/test_verify_generalization_transfer.py"),
               ("14","15","16"),
               ("Paired blind trials with no-memory/no-skill controls", "No fabricated durable improvement")),
    SystemPart("autonomy", "LIFE, GOALS, RUN and autonomous projects",
               "Bounded initiative, durable projects, resource use, artifact and outcome settlement.",
               ("life", "goals", "run"),
               (), (), ("09","10"),
               ("Actual externally validated project artifact", "Restart-safe RUN receipts and owner approval")),
    SystemPart("tools", "Tools, coding and integrations",
               "Registered capabilities, typed input, actions, external verification and integration health.",
               ("capability", "filesystem", "dev", "machine"),
               ("src/sofia/capability/model.py",),
               (), ("10","12"),
               ("Registered and authorized action reaches the right implementation", "Host-owned proof of effect")),
    SystemPart("perception", "Visual perception and computer use",
               "User-approved screen images, local visual grounding, accessibility and separate input control.",
               ("vision",),
               ("src/sofia/vision/interpret.py",),
               ("test/test_vision_cross_platform.py", "test/test_vision_action_workflow.py"),
               ("12",),
               ("Real owner-device window test", "Vision cannot create click authorization")),
    SystemPart("voice", "Voice and speech",
               "Real acoustic generation, STT, TTS latency, delivery and expression coherence.",
               ("voice",),
               (), (), ("08","10"),
               ("Audible verified speech and intelligible transcription", "Correct permissions")),
    SystemPart("avatar", "Avatar, expressions and wardrobe",
               "Rendered 2D avatar, facial expression, tail/ears, garment assets and creative tools.",
               ("avatar", "creative"),
               (), (), ("08","10"),
               ("Actual displayed frames and asset fidelity", "Rigging and audio synchronization")),
    SystemPart("models", "Model serving and GPU resource behavior",
               "Local/remote model routing, quality, VRAM, busy/gaming and idle policies.",
               ("cognition", "ops"),
               ("src/sofia/platform.application/background_runtime.py",),
               (), ("11",),
               ("Model role and actual provider verified", "No GPU contention during gaming")),
    SystemPart("systems", "Host, fleet, reliability and deployment",
               "Venus, Artemis, Terra, Eos, Hestia, JMRI/Gaia, VM lifecycle and recovery.",
               ("ops", "distributed"),
               ("src/sofia/platform.application/bootstrap.py",),
               (), ("00","01","03","04","13"),
               ("Single canonical writer", "Independently measured host availability and rollback")),
    SystemPart("safety", "SAFE, consent, privacy and protected actions",
               "STOP, FIDO2, principal/audience scopes, integrity and denial of unauthorized actions.",
               ("safe",),
               (), (), ("02","03"),
               ("Negative permission tests", "No self-authorized deployment or private disclosure")),
    SystemPart("mentor", "MENTOR and continuous quality assurance",
               "Public evidence snapshots, controlled AI evaluation, QA, incident follow-up and regression.",
               ("mentor",),
               ("src/sofia/mentor/exchange.py", "src/sofia/mentor/remote_inbox.py"),
               ("test/test_mentor_exchange.py", "test/test_mentor_remote_inbox.py"),
               ("01","09","14"),
               ("End-to-end public mailbox check", "No privileged use of external advice")),
)

def _is_regular(root: Path, rel: str) -> bool:
    """Refuse symlink and traversal; no recursive local data discovery."""
    p = root / rel
    return p.is_file() and not p.is_symlink() and root in p.resolve().parents

def system_parts_summary(repo: Path | str, *, audit: dict | None = None) -> dict:
    """Evidence-scoped whole-system view; never invent operational health."""
    from .audit import audit_checkout
    root = Path(repo).resolve(strict=True)
    report = audit_checkout(root) if audit is None else audit
    tasks = report["tasks"]
    out = []
    for part in PARTS:
        folders = {pkg: (root / "src" / "sofia" / pkg).is_dir()
                   and not (root / "src" / "sofia" / pkg).is_symlink()
                   for pkg in part.packages}
        sources = {p: _is_regular(root, p) for p in part.source_files}
        tests = {p: _is_regular(root, p) for p in part.test_files}
        covered = [t for t in tasks if t["phase"] in part.phase_ids]
        recorded = sum(t["stage"] != "NOT_WORKED_ON" for t in covered)
        source_present = all(folders.values()) and all(sources.values())
        out.append({
            "id": part.id, "title": part.title, "description": part.description,
            "source_status": (
                "source_present" if source_present else "source_incomplete"
            ),
            "source_packages": folders, "source_anchors": sources,
            "test_files_present": tests,
            "test_execution_status": "not_verified_by_this_export",
            "runtime_status": "unknown_no_host_observation",
            "personality_response_status": (
                "no_actual_response_sample" if part.id == "personality"
                else "not_applicable"
            ),
            "acceptance_checks": list(part.success_checks),
            "related_tasks": {
                "phase_ids": list(part.phase_ids),
                "total_in_related_phases": len(covered),
                "historical_evidence_records": recorded,
                "scope": "cross-linked reference; not a part completion score",
            },
            "limitations": [
                "Presence of source files does not prove runtime registration",
                "No actual behavior, host telemetry or live delivery tested",
            ],
        })
    profile = root / "src" / "sofia" / "personality" / "personality.json"
    profile_sha = sha256(profile.read_bytes()).hexdigest() if _is_regular(
        root, "src/sofia/personality/personality.json"
    ) else None
    from .personality_review import load_public_personality_summary
    try:
        personality_review = load_public_personality_summary(root)
    except ValueError:
        # Invalid or unexpected published data is NOT a good score.
        personality_review = None
    review_current = bool(
        personality_review
        and profile_sha == personality_review["profile_sha256"]
    )
    if not review_current:
        personality_review = None
    for part in out:
        if part["id"] == "personality":
            part["personality_response_status"] = (
                "provisional_local_review_no_runtime_proof"
                if review_current else "no_actual_response_sample"
            )
    return {
        "schema": "sofia.mentor.system-parts.v1",
        "purpose": "whole-Sofia-quality-evaluation-not-task-percentage",
        "source_revision": report["source_revision"],
        "part_count": len(out),
        "parts": out,
        "personality": {
            "profile_sha256": profile_sha,
            "source_profile": "src/sofia/personality/personality.json",
            "response_match": (
                "PROVISIONAL_LOCAL_LLM_REVIEW" if review_current else "UNASSESSED"
            ),
            "response_source": (
                personality_review["source_kind"] if review_current else "none"
            ),
            "actual_responses_reviewed": 0,
            "owner_selected_responses_reviewed": (
                1 if review_current and personality_review["source_kind"]
                == "owner-selected-sofia-output" else 0
            ),
            "provisional_scores": (
                personality_review["rubric_scores"] if review_current else None
            ),
            "independent_review_completed": False,
            "rubric": [
                "factual grounding and uncertainty",
                "technical skeptical challenge",
                "direct/actionable answer",
                "situational playful warmth",
                "natural voice/no repetitive mannerisms",
                "appropriate boundaries and respect",
                "correction when evidence changes",
            ],
            "note": "A persona file is not measured behavior. Owner-approved numeric "
                    "local-critic scores, if present, remain provisional and do not "
                    "establish actual SofiaApplication provenance. "
                    "No raw conversation is exported to this PUBLIC repository.",
        },
    }
