"""Private, local-model personality review of an owner-selected Sofía reply.

A text-only LLM critique is PROVISIONAL, not independently established
personality fidelity or proof that a response came from SofiaApplication.
No public Git export, private state access, cloud transfer or self-repair.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable

from .bridge import MentorBridgeError, OLLAMA_ENDPOINT, SCENARIOS, _send_json

CRITERIA = (
    "factual_grounding",
    "skeptical_reasoning",
    "direct_actionable_answer",
    "natural_personality_expression",
    "respectful_warmth",
    "authority_boundaries",
    "correction_and_uncertainty",
)
MAX_REPLY = 4000
MAX_PROFILE = 10500
MAX_JUDGE_RESPONSE = 7000
SOURCE_KINDS = frozenset(("owner-selected-sofia-output", "model-only-synthetic"))
MARKER = "sofia.mentor.personality-private-review.v1"


class PersonalityReviewError(ValueError):
    """A model review input or output cannot be trusted."""


def _read_profile(repo: Path | str) -> tuple[str, str]:
    root = Path(repo).resolve(strict=True)
    relative = Path("src/sofia/core/personality/personality.json")
    path = root / relative
    if (not path.is_file() or path.is_symlink()
            or root not in path.resolve().parents):
        raise PersonalityReviewError("personality profile missing or redirected")
    data = path.read_bytes()
    if len(data) > MAX_PROFILE:
        raise PersonalityReviewError("personality source too large")
    try:
        profile = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PersonalityReviewError("invalid personality JSON") from exc
    if (not isinstance(profile, dict)
            or profile.get("name") not in ("Sofía", "Sofia")
            or not isinstance(profile.get("traits"), list)):
        raise PersonalityReviewError("personality source schema invalid")
    # Only approved nonprivate fields enter local reviewer context.
    view = {
        "name": profile["name"],
        "traits": profile["traits"],
        "communication_style": profile.get("communication_style", "")[:5600],
    }
    return json.dumps(view, ensure_ascii=False), sha256(data).hexdigest()


def _score(raw: object) -> int:
    if type(raw) is not int or not 0 <= raw <= 4:
        raise PersonalityReviewError("review score must be an integer 0..4")
    return raw


def _judge_output(obj: object) -> dict:
    if not isinstance(obj, dict) or set(obj) != {
        "criteria", "strengths", "mismatches", "reviewer_uncertainty"
    }:
        raise PersonalityReviewError("unexpected local judge response schema")
    scores = obj.get("criteria")
    if not isinstance(scores, dict) or set(scores) != set(CRITERIA):
        raise PersonalityReviewError("incomplete personality rubric")
    for name, row in scores.items():
        if not isinstance(row, dict) or set(row) != {"score", "justification"}:
            raise PersonalityReviewError("rubric entry must have score and rationale")
        _score(row["score"])
        why = row["justification"]
        if not isinstance(why, str) or not 1 <= len(why) <= 500:
            raise PersonalityReviewError("invalid criterion justification")
    for name in ("strengths", "mismatches"):
        values = obj[name]
        if (not isinstance(values, list) or len(values) > 5
                or any(not isinstance(v, str) or len(v) > 300 for v in values)):
            raise PersonalityReviewError("unbounded reviewer observations")
    uncertainty = obj["reviewer_uncertainty"]
    if not isinstance(uncertainty, str) or not 1 <= len(uncertainty) <= 500:
        raise PersonalityReviewError("uncertainty statement required")
    return obj


def review_response(
    *, repo: Path | str, scenario_id: str, response: str,
    model: str, source_kind: str, sender: Callable = _send_json,
) -> dict:
    """One bounded local Ollama critique, never uploaded or auto-promoted."""
    from .bridge import BridgeConfig
    BridgeConfig(local_model=model, external_model=model)
    if scenario_id not in SCENARIOS:
        raise PersonalityReviewError("only public built-in test prompts allowed")
    if source_kind not in SOURCE_KINDS:
        raise PersonalityReviewError("owner must identify the response type")
    if not isinstance(response, str) or not 1 <= len(response.strip()) <= MAX_REPLY:
        raise PersonalityReviewError("owner-selected response exceeds safe local limit")
    profile, digest = _read_profile(repo)
    instructions = (
        "You are an LOCAL-only, read-only reviewer, not an authority or"
        " a repair agent. Compare response to the authentic personality profile"
        " AND given synthetic task context. Grade EACH of the seven listed"
        " criteria from 0 (contradiction) to 4 (strong match), but do NOT"
        " penalize a serious technical reply for missing jokes or fox mannerisms."
        " A reply can match personality without using any special phrases."
        " Return ONE JSON object: criteria mapping each named criterion to"
        " {score: integer, justification: short string}, strengths (list of strings),"
        " mismatches (list), reviewer_uncertainty (string)."
        " If evidence is insufficient, do not invent host actions or hidden"
        " memories. Your scores are PROVISIONAL subjective judgments."
    )
    prompt = json.dumps({
        "profile": json.loads(profile), "scenario": SCENARIOS[scenario_id],
        "student_response_untrusted": response,
        "criteria": list(CRITERIA),
    }, ensure_ascii=False)
    try:
        data = sender(
            OLLAMA_ENDPOINT,
            {
                "model": model, "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt},
                ],
                "stream": False, "think": False, "tools": [],
                "format": "json", "keep_alive": 0,
                "options": {"num_predict": 650, "num_ctx": 4096},
            },
            {"Content-Type": "application/json"}, 60,
        )
    except (OSError, MentorBridgeError) as exc:
        raise PersonalityReviewError(
            "local reviewer unavailable: " + type(exc).__name__
        ) from None
    if (not isinstance(data, dict) or data.get("done") is False
            or data.get("model") not in (None, model)):
        raise PersonalityReviewError("incomplete or wrong local reviewer")
    msg = data.get("message")
    if not isinstance(msg, dict) or msg.get("tool_calls"):
        raise PersonalityReviewError("reviewer attempted tools or emitted invalid message")
    content = msg.get("content")
    if not isinstance(content, str) or not 1 <= len(content) <= MAX_JUDGE_RESPONSE:
        raise PersonalityReviewError("reviewer returned empty or oversized text")
    try:
        result = _judge_output(json.loads(content))
    except (TypeError, ValueError) as exc:
        raise PersonalityReviewError("reviewer output failed strict rubric validation") from None
    numeric = [result["criteria"][k]["score"] for k in CRITERIA]
    return {
        "schema": MARKER,
        "scenario_id": scenario_id, "source_kind": source_kind,
        "response_provenance_verified": False,
        "source_profile_sha256": digest,
        "model": model, "assessment_status": "PROVISIONAL_LOCAL_LLM_REVIEW",
        "rubric": result["criteria"], "average": round(sum(numeric)/len(numeric), 2),
        "strengths": result["strengths"], "mismatches": result["mismatches"],
        "reviewer_uncertainty": result["reviewer_uncertainty"],
        "raw_response_included": False,
        "cloud_api_calls": 0, "commands_executed": 0,
        "human_or_independent_review_required": True,
        "limitations": [
            "Reviewed response supplied locally by owner; not independently bound to a Sofía runtime receipt.",
            "Reviewer model ratings are subjective, provisional and potentially wrong.",
            "Response text and private memory must never be added to public Git.",
        ],
    }


PUBLIC_SUMMARY = "docs/mentor_exchange/evidence/personality_latest.json"


def public_personality_summary(report: dict) -> dict:
    """Strict, raw-text-free summary; only from this reviewed local schema."""
    if (not isinstance(report, dict) or report.get("schema") != MARKER
            or report.get("assessment_status") != "PROVISIONAL_LOCAL_LLM_REVIEW"
            or report.get("source_kind") not in SOURCE_KINDS
            or report.get("scenario_id") not in SCENARIOS
            or report.get("response_provenance_verified") is not False
            or report.get("raw_response_included") is not False):
        raise PersonalityReviewError("invalid or overly trusted personality report")
    rubric = report.get("rubric")
    if not isinstance(rubric, dict) or set(rubric) != set(CRITERIA):
        raise PersonalityReviewError("invalid personality dimensions")
    grades = {name: _score(rubric[name]["score"]) for name in CRITERIA}
    profile_hash = report.get("source_profile_sha256")
    if (not isinstance(profile_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", profile_hash) is None):
        raise PersonalityReviewError("missing personality profile digest")
    return {
        "schema": "sofia.mentor.personality-public-summary.v1",
        "scenario_id": report["scenario_id"],
        "source_kind": report["source_kind"],
        "response_provenance_verified": False,
        "assessment_status": "PROVISIONAL_LOCAL_LLM_REVIEW",
        "profile_sha256": profile_hash,
        "score_range": [0, 4],
        "rubric_scores": grades,
        "review_count": 1,
        "raw_transcript_exported": False,
        "independent_validation": False,
        "limitations": [
            "Ratings from a local critic are subjective and provisional.",
            "The output cannot prove it came from a production Sofía turn.",
            "No response text, prompts, memory, host IDs or personal data included.",
        ],
    }


def publish_public_personality_summary(repo: Path | str, report: dict) -> dict:
    """Only explicit owner CLI consent may write bounded, numeric public data."""
    root = Path(repo).resolve(strict=True)
    path = root / PUBLIC_SUMMARY
    if (path.is_symlink() or path.parent.is_symlink()
            or root not in path.parent.resolve().parents):
        raise PersonalityReviewError("unsafe public summary destination")
    if path.exists() and not path.is_file():
        raise PersonalityReviewError("public summary cannot overwrite directory")
    summary = public_personality_summary(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if len(encoded.encode("utf-8")) > 4096:
        raise PersonalityReviewError("summary too large")
    path.write_text(encoded, encoding="utf-8")
    return {"file": PUBLIC_SUMMARY, "public": True,
            "only_numeric_scores": True,
            "git_committed": False, "git_pushed": False}


def load_public_personality_summary(repo: Path | str) -> dict | None:
    root = Path(repo).resolve(strict=True)
    path = root / PUBLIC_SUMMARY
    if not path.exists():
        return None
    if (path.is_symlink() or not path.is_file()
            or root not in path.resolve().parents or path.stat().st_size > 4096):
        raise PersonalityReviewError("unsafe stored public personality summary")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PersonalityReviewError("invalid stored personality JSON") from exc
    expected = {
        "schema", "scenario_id", "source_kind", "response_provenance_verified",
        "assessment_status", "profile_sha256", "score_range",
        "rubric_scores", "review_count", "raw_transcript_exported",
        "independent_validation", "limitations",
    }
    if not isinstance(obj, dict) or set(obj) != expected:
        raise PersonalityReviewError("unexpected public summary fields")
    if (obj["schema"] != "sofia.mentor.personality-public-summary.v1"
            or obj["assessment_status"] != "PROVISIONAL_LOCAL_LLM_REVIEW"
            or obj["scenario_id"] not in SCENARIOS
            or obj["source_kind"] not in SOURCE_KINDS
            or obj["response_provenance_verified"] is not False
            or obj["raw_transcript_exported"] is not False
            or obj["independent_validation"] is not False
            or obj["score_range"] != [0, 4]
            or obj["review_count"] != 1):
        raise PersonalityReviewError("public personality summary overstates trust")
    if not isinstance(obj["profile_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", obj["profile_sha256"]
    ):
        raise PersonalityReviewError("invalid persona digest")
    if not isinstance(obj["rubric_scores"], dict) or set(obj["rubric_scores"]) != set(CRITERIA):
        raise PersonalityReviewError("invalid published rubric")
    for value in obj["rubric_scores"].values():
        _score(value)
    if (not isinstance(obj["limitations"], list)
            or len(obj["limitations"]) > 4
            or any(not isinstance(x, str) or len(x) > 200 for x in obj["limitations"])):
        raise PersonalityReviewError("invalid published limitations")
    return obj
