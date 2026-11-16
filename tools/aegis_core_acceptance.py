"""Conservative Core 1.0 acceptance evidence aggregator.

This tool builds a machine-readable inventory of the existing Core 1.0
requirements (CORE-01..CORE-40), batches B00..B08, the G7-A evidence boundary
and the owner-only Core criteria POC-C1..POC-C5.  It consumes real source test
results (JUnit) plus explicit evidence receipts and reports a per-item state.

Design rules:

* ``PASS`` is only produced when *every* evidence kind declared by an item is
  present and internally valid.
* A skipped test is never a pass.  A missing negative case is never a pass.
* Receipts must be signed with a caller-trusted Ed25519 key over canonical
  JSON.  Self-declared signer lists never establish trust.  Every receipt binds
  the exact source SHA, artifact bytes, host IDs, timestamps and result.
  Stale, future, mismatched or unregistered values are rejected.
* Receipts without a valid signature keep every receipt-backed item
  ``BLOCKED`` and the verdict ``NO_GO``.
* G8 (#129) is always a separate verdict.  It can only be certified by a
  distinct real-host receipt whose owner host and remote client are registered
  and independently attested.  Disposable evidence can never certify G8.
* The authoritative documents under ``docs/`` are never modified and no
  acceptance is claimed by this tool.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_ROOT / "src"))
    sys.path.insert(0, str(_ROOT))

from sofia.sdk.cognition_json import loads_strict_model_json  # noqa: E402
from tools.aegis_platform_row_preflight import (  # noqa: E402
    _hash_bounded_evidence_artifact,
)

SCHEMA = "aegis.core.acceptance-report.v1"
RECEIPTS_SCHEMA = "aegis.core.acceptance-receipts.v1"
G8_SCHEMA = "aegis.core.g8-real-host-receipt.v1"
SIGNATURE_ALGORITHM = "Ed25519"

RECEIPTS_TOP_FIELDS = frozenset({
    "schema", "source_sha", "hosts", "items", "signature",
})
G8_TOP_FIELDS = frozenset({
    "schema", "source_sha", "hosts", "receipt", "signature",
})
SIGNATURE_FIELDS = frozenset({
    "algorithm", "signer_key_id", "signature_b64",
})
HOST_FIELDS = frozenset({"host_class"})
ITEM_FIELDS = frozenset({"source_sha", "evidence"})
BASE_ENTRY_FIELDS = frozenset({
    "host_id", "host_class", "signer_key_id", "artifact_path",
    "artifact_sha256", "application_sha256", "observed", "result",
    "witnessed_at", "negative_cases",
})
OWNER_ENTRY_FIELDS = BASE_ENTRY_FIELDS | frozenset({"real_host"})
G8_ENTRY_FIELDS = OWNER_ENTRY_FIELDS | frozenset({
    "remote_host_id", "owner_approved",
})

EVIDENCE_KINDS = (
    "source_tests",
    "disposable_process",
    "installed_artifact",
    "remote_conversation",
    "owner_host",
)
HOST_CLASS_BY_KIND = {
    "disposable_process": "DISPOSABLE",
    "installed_artifact": "INSTALLED",
    "remote_conversation": "REMOTE",
    "owner_host": "OWNER",
}
STATES = ("PASS", "FAIL", "BLOCKED", "NOT_TESTED")

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_DEFAULT_MAX_AGE_DAYS = 365

SRC = ("source_tests",)
PROC = ("source_tests", "disposable_process")
INSTALL = ("source_tests", "disposable_process", "installed_artifact")
REMOTE = INSTALL + ("remote_conversation",)
OWNER = REMOTE + ("owner_host",)


@dataclass(frozen=True)
class ItemSpec:
    item_id: str
    group: str
    title: str
    source_tests: tuple[str, ...]
    required: tuple[str, ...]
    release_scope: bool = True


def _spec(
    item_id: str,
    group: str,
    title: str,
    source_tests: tuple[str, ...],
    required: tuple[str, ...],
    *,
    release_scope: bool = True,
) -> ItemSpec:
    return ItemSpec(item_id, group, title, source_tests, required, release_scope)


# The source-test names are *narrow probes*.  Their presence never certifies an
# installed-host, remote-conversation or owner-host acceptance requirement.
INVENTORY: tuple[ItemSpec, ...] = (
    _spec("CORE-01", "CORE", "Identity and self-concept", (
        "test_identity.py", "test_platform_installation_identity.py",
    ), OWNER),
    _spec("CORE-02", "CORE", "Values and philosophy", (
        "test_constitution_integrity.py", "test_constitution_store.py",
    ), PROC),
    _spec("CORE-03", "CORE", "Likes and dislikes", (
        "test_personality_preferences.py", "test_romance_preferences.py",
    ), PROC),
    _spec("CORE-04", "CORE", "Interests and hobbies", (
        "test_life_fulfillment.py",
    ), PROC),
    _spec("CORE-05", "CORE", "Curiosity", (
        "test_web_research.py",
    ), PROC),
    _spec("CORE-06", "CORE", "Opinions and convictions", (
        "test_beliefs_store.py", "test_beliefs_wiring.py",
    ), PROC),
    _spec("CORE-07", "CORE", "Autobiographical memory", (
        "test_memory_provenance.py", "test_significant_memory_and_autobiography.py",
    ), INSTALL),
    _spec("CORE-08", "CORE", "Emotional expression", (
        "test_emotional_journal.py", "test_conversation_emotion_appraisal.py",
    ), PROC),
    _spec("CORE-09", "CORE", "Aspirations", (
        "test_goals_v1.py",
    ), PROC),
    _spec("CORE-10", "CORE", "Habits", (
        "test_habit_foundation.py", "test_habit_contextual_matrix.py",
    ), PROC),
    _spec("CORE-11", "CORE", "Relationships", (
        "test_rel_impressions.py", "test_social_principals.py",
    ), INSTALL),
    _spec("CORE-12", "CORE", "Creativity", (
        "test_creative_infrastructure.py",
    ), PROC),
    _spec("CORE-13", "CORE", "Self-knowledge", (
        "test_self_model.py", "test_cognitive_self_state.py",
    ), PROC),
    _spec("CORE-14", "CORE", "Personal learning", (
        "test_learning_foundation.py",
    ), PROC),
    _spec("CORE-15", "CORE", "Privacy and boundaries", (
        "test_ws2_memory_private_admission.py", "test_expression_audience_gate.py",
    ), REMOTE),
    _spec("CORE-16", "CORE", "Attention and continuity", (
        "test_continuity_context.py", "test_conversation_continuity.py",
    ), INSTALL),
    _spec("CORE-17", "CORE", "Independent questions", (
        "test_presence_initiative.py",
    ), PROC),
    _spec("CORE-18", "CORE", "Social impressions", (
        "test_rel_impressions.py", "test_social_principals.py",
    ), PROC),
    _spec("CORE-19", "CORE", "Leisure and inactivity", (
        "test_life_fulfillment.py",
    ), PROC),
    _spec("CORE-20", "CORE", "Natural interest development", (
        "test_life_fulfillment.py",
    ), PROC),
    _spec("CORE-21", "CORE", "Personality evolution", (
        "test_personality_evolution.py", "test_personality_preferences.py",
    ), PROC),
    _spec("CORE-22", "CORE", "Anticipation", (
        "test_continuity_context.py", "test_proactive_continuity_awareness.py",
    ), PROC),
    _spec("CORE-23", "CORE", "Personal refusal", (
        "test_expression_audience_gate.py",
    ), PROC),
    _spec("CORE-24", "CORE", "Meaningful memories", (
        "test_significant_memory_and_autobiography.py",
    ), PROC),
    _spec("CORE-25", "CORE", "Internal dilemmas", (
        "test_goal_production_wiring.py", "test_goals_v1.py",
    ), PROC),
    _spec("CORE-26", "CORE", "Personal standards", (
        "test_life_fulfillment.py",
    ), PROC),
    _spec("CORE-27", "CORE", "Relationship repair", (
        "test_rel_repair.py",
    ), PROC),
    _spec("CORE-28", "CORE", "Evolving humor", (
        "test_personality_evolution.py",
    ), PROC),
    _spec("CORE-29", "CORE", "Long-term ambitions", (
        "test_goals_v1.py", "test_life_autonomous_followthrough.py",
    ), PROC),
    _spec("CORE-30", "CORE", "Self-observed change", (
        "test_self_model.py", "test_personality_evolution.py",
    ), PROC),
    _spec("CORE-31", "CORE", "Thoughtful surprises", (
        "test_proactive_continuity_awareness.py",
    ), PROC),
    _spec("CORE-32", "CORE", "Personal fulfillment", (
        "test_life_fulfillment.py",
    ), PROC),
    _spec("CORE-33", "CORE", "Communication learning", (
        "test_communication_learning.py",
    ), PROC),
    _spec("CORE-34", "CORE", "Multi-person familiarity (post-Core only)", (),
          SRC, release_scope=False),
    _spec("CORE-35", "CORE", "Codebase awareness", (
        "test_codebase_analyzers.py", "test_codebase_inspection_store.py",
    ), INSTALL),
    _spec("CORE-36", "CORE", "Supervised restart", (
        "test_core_maintenance_b07.py", "test_application_restart_continuity.py",
    ), PROC),
    _spec("CORE-37", "CORE", "Verified self-update", (
        "test_core_maintenance_b07.py", "test_run_update_restart.py",
    ), INSTALL),
    _spec("CORE-38", "CORE", "Core self-improvement", (
        "test_core_maintenance_b07.py",
    ), PROC),
    _spec("CORE-39", "CORE", "Module discovery", (
        "test_module_awareness.py", "test_module_compatibility_v1.py",
    ), PROC),
    _spec("CORE-40", "CORE", "Module troubleshooting", (
        "test_core_maintenance_b07.py", "test_module_lifecycle_v1.py",
    ), PROC),
    _spec("B00", "BATCH", "Baseline and architectural ownership", (
        "test_composition.py", "test_identity.py", "test_run_doctor.py",
    ), PROC),
    _spec("B01", "BATCH", "Convictions and owner/self separation", (
        "test_beliefs_store.py", "test_beliefs_wiring.py",
    ), PROC),
    _spec("B02", "BATCH", "Self-knowledge and trait evolution", (
        "test_personality_evolution.py", "test_self_model.py",
    ), PROC),
    _spec("B03", "BATCH", "Interests, standards and fulfillment", (
        "test_life_fulfillment.py",
    ), PROC),
    _spec("B04", "BATCH", "Autobiographical continuity", (
        "test_significant_memory_and_autobiography.py",
        "test_memory_provenance.py", "test_application_restart_continuity.py",
    ), INSTALL),
    _spec("B05", "BATCH", "Communication and evolving humor", (
        "test_communication_learning.py", "test_habit_foundation.py",
    ), PROC),
    _spec("B06", "BATCH", "Relationships, boundaries and judgment", (
        "test_rel_repair.py", "test_rel_impressions.py", "test_social_principals.py",
    ), PROC),
    _spec("B07", "BATCH", "Code awareness and module governance", (
        "test_core_maintenance_b07.py", "test_module_awareness.py",
    ), PROC),
    _spec("B08", "BATCH", "Release integration and broad acceptance", (
        "test_core_link_conversation.py", "test_core_link_desktop.py",
        "test_application_restart_continuity.py",
    ), OWNER),
    _spec("G7-A", "G7A", "Evidence-boundary and learning truth pins", (
        "test_cognition_v2_evidence.py", "test_cognition_v2_fleet_observation.py",
        "test_goal_production_wiring.py",
    ), PROC),
    _spec("POC-C1", "POC", "One persistent Core identity and writer", (
        "test_core_team3_disposable_continuity.py",
        "test_application_restart_continuity.py",
    ), OWNER),
    _spec("POC-C2", "POC", "Genuine owner and audience boundaries", (
        "test_ws2_memory_private_admission.py", "test_safe_permissions.py",
        "test_expression_audience_gate.py",
    ), REMOTE),
    _spec("POC-C3", "POC", "Personal-use model and capability freedom", (
        "test_generic_cognition_providers.py",
        "test_default_runtime_provider_boundary.py",
        "test_model_configuration_independence.py",
    ), INSTALL),
    _spec("POC-C4", "POC", "Private memory and asset audience scoping", (
        "test_ws2_memory_private_admission.py", "test_memory_provenance.py",
        "test_imported_history_local_audience_privacy.py",
    ), INSTALL),
    _spec("POC-C5", "POC", "Honest degradation and governed actions", (
        "test_core_maintenance_b07.py", "test_generic_core_worker_isolation.py",
    ), INSTALL),
)

INVENTORY_BY_ID = {item.item_id: item for item in INVENTORY}
assert len(INVENTORY_BY_ID) == len(INVENTORY)
assert tuple(item.item_id for item in INVENTORY if item.group == "CORE") == tuple(
    f"CORE-{number:02d}" for number in range(1, 41)
)
assert tuple(item.item_id for item in INVENTORY if item.group == "BATCH") == tuple(
    f"B{number:02d}" for number in range(0, 9)
)
assert tuple(item.item_id for item in INVENTORY if item.group == "POC") == tuple(
    f"POC-C{number}" for number in range(1, 6)
)


class CoreAcceptanceError(RuntimeError):
    """Raised when collector input is malformed or unsafe."""


def _read_json(path: Path, *, limit: int = 8 * 1024 * 1024) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise CoreAcceptanceError(f"input is not a regular file: {path}")
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise CoreAcceptanceError(f"input is outside bounded size: {path}")
    loaded = loads_strict_model_json(path.read_bytes().decode("utf-8"))
    if type(loaded) is not dict:
        raise CoreAcceptanceError(f"input must be a JSON object: {path}")
    return loaded


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha() -> str:
    repo = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "rev-parse", "HEAD"],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
    )
    if completed.returncode != 0:
        raise CoreAcceptanceError("cannot observe exact source SHA")
    value = completed.stdout.strip()
    if not _SHA40.fullmatch(value):
        raise CoreAcceptanceError("Git returned an invalid source SHA")
    return value


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _case_file(case: ElementTree.Element) -> str:
    direct = case.attrib.get("file", "")
    if direct:
        return Path(direct.replace("\\", "/")).name
    classname = case.attrib.get("classname", "")
    for part in reversed(classname.split(".")):
        if part.startswith("test_"):
            return part if part.endswith(".py") else part + ".py"
    return ""


def _case_keys(case: ElementTree.Element) -> tuple[str, ...]:
    name = case.attrib.get("name", "")
    classname = case.attrib.get("classname", "")
    filename = _case_file(case)
    keys = {name}
    if classname:
        keys.add(classname)
        keys.add(f"{classname}.{name}")
    if filename and name:
        keys.add(f"{filename}::{name}")
    return tuple(key for key in keys if key)


def parse_junit(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "present": False,
            "sha256": None,
            "files": {},
            "cases": 0,
            "issues": ["JUNIT_EVIDENCE_ABSENT"],
        }
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return {
            "present": False,
            "sha256": None,
            "files": {},
            "cases": 0,
            "issues": ["JUNIT_EVIDENCE_ABSENT"],
        }
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        return {
            "present": False,
            "sha256": _sha256_file(path),
            "files": {},
            "cases": 0,
            "issues": [f"JUNIT_MALFORMED:{error}"],
        }
    files: dict[str, list[tuple[tuple[str, ...], str]]] = {}
    cases = 0
    for case in root.iter("testcase"):
        cases += 1
        filename = _case_file(case)
        if not filename:
            continue
        result = "PASS"
        if case.find("failure") is not None or case.find("error") is not None:
            result = "FAIL"
        elif case.find("skipped") is not None:
            result = "SKIP"
        files.setdefault(filename, []).append((_case_keys(case), result))
    return {
        "present": True,
        "sha256": _sha256_file(path),
        "files": files,
        "cases": cases,
        "issues": [],
    }


def _source_status(
    spec: ItemSpec, junit: dict[str, Any],
) -> dict[str, Any]:
    missing: list[str] = []
    failed = False
    if not spec.source_tests:
        missing.append("NO_MAPPED_SOURCE_TEST")
        return {"state": "BLOCKED", "missing": missing, "failed": False}
    if not junit.get("present"):
        missing.append("JUNIT_EVIDENCE_ABSENT")
        return {"state": "NOT_TESTED", "missing": missing, "failed": False}
    for filename in spec.source_tests:
        results = junit["files"].get(filename)
        if not results:
            missing.append(f"SOURCE_TEST_NOT_OBSERVED:{filename}")
            continue
        if any(result == "FAIL" for _keys, result in results):
            failed = True
        if any(result == "SKIP" for _keys, result in results):
            missing.append(f"SOURCE_TEST_SKIPPED:{filename}")
    if failed:
        return {"state": "FAIL", "missing": missing, "failed": True}
    if missing:
        return {
            "state": "NOT_TESTED" if not junit.get("present") else "BLOCKED",
            "missing": missing,
            "failed": False,
        }
    return {"state": "PASS", "missing": [], "failed": False}


def _canonical_payload_bytes(document: dict[str, Any]) -> bytes:
    payload = {
        key: value for key, value in document.items() if key != "signature"
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _load_trusted_key(
    public_key: Path | None,
    key_sha256: str | None,
    signer_key_id: str | None,
) -> tuple[Ed25519PublicKey | None, list[str]]:
    if (public_key is None or not key_sha256
            or not isinstance(signer_key_id, str) or not signer_key_id):
        return None, ["TRUST_ROOT_ABSENT"]
    if not _SHA64.fullmatch(str(key_sha256)):
        return None, ["TRUSTED_KEY_SHA256_INVALID"]
    path = Path(public_key).absolute()
    if path.is_symlink() or not path.is_file():
        return None, ["TRUSTED_PUBLIC_KEY_UNAVAILABLE"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != key_sha256:
        return None, ["TRUSTED_KEY_SHA256_MISMATCH"]
    try:
        key = serialization.load_pem_public_key(raw)
    except (TypeError, ValueError):
        return None, ["TRUSTED_PUBLIC_KEY_INVALID"]
    if not isinstance(key, Ed25519PublicKey):
        return None, ["TRUSTED_PUBLIC_KEY_NOT_ED25519"]
    return key, []


def _verify_signature(
    document: dict[str, Any],
    *,
    trusted_key: Ed25519PublicKey | None,
    trusted_signer_key_id: str | None,
) -> tuple[bool, list[str]]:
    signature = document.get("signature")
    if type(signature) is not dict:
        return False, ["SIGNATURE_ABSENT"]
    if set(signature) != SIGNATURE_FIELDS:
        return False, ["SIGNATURE_FIELDS_MISMATCH"]
    issues: list[str] = []
    if signature.get("algorithm") != SIGNATURE_ALGORITHM:
        issues.append("SIGNATURE_ALGORITHM_UNSUPPORTED")
    if signature.get("signer_key_id") != trusted_signer_key_id:
        issues.append("SIGNATURE_SIGNER_NOT_TRUSTED")
    try:
        raw = base64.b64decode(
            str(signature.get("signature_b64", "")), validate=True,
        )
    except (TypeError, ValueError):
        issues.append("SIGNATURE_BASE64_INVALID")
        raw = b""
    if len(raw) != 64:
        issues.append("SIGNATURE_LENGTH_INVALID")
    if issues:
        return False, issues
    if trusted_key is None:
        return False, ["SIGNATURE_KEY_UNAVAILABLE"]
    try:
        trusted_key.verify(raw, _canonical_payload_bytes(document))
    except InvalidSignature:
        return False, ["SIGNATURE_INVALID"]
    return True, []


def _validate_hosts(
    hosts: object, *, label: str,
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if not isinstance(hosts, dict) or not hosts:
        return {}, [f"{label}_HOSTS_INVALID"]
    for host_id, record in hosts.items():
        if (not isinstance(host_id, str) or not host_id
                or type(record) is not dict
                or set(record) != HOST_FIELDS
                or record.get("host_class") not in set(HOST_CLASS_BY_KIND.values())):
            issues.append(f"{label}_HOSTS_INVALID")
            return {}, issues
    return hosts, issues


def load_receipts(
    path: Path | None,
    *,
    source_sha: str,
    trusted_public_key: Path | None = None,
    trusted_key_sha256: str | None = None,
    signer_key_id: str | None = None,
) -> dict[str, Any]:
    if path is None:
        return {
            "present": False,
            "signature_valid": False,
            "schema_ok": False,
            "items": {},
            "hosts": {},
            "evidence_dir": None,
            "signature_issues": ["EVIDENCE_RECEIPTS_ABSENT"],
            "content_issues": [],
            "issues": ["EVIDENCE_RECEIPTS_ABSENT"],
            "trusted_signer_key_id": signer_key_id,
        }
    try:
        document = _read_json(path, limit=16 * 1024 * 1024)
    except (ValueError, UnicodeDecodeError) as error:
        raise CoreAcceptanceError(f"invalid receipt JSON: {error}") from error
    trusted_key, trust_issues = _load_trusted_key(
        trusted_public_key, trusted_key_sha256, signer_key_id,
    )
    signature_valid = False
    signature_issues = list(trust_issues)
    if not trust_issues:
        signature_valid, signature_issues = _verify_signature(
            document, trusted_key=trusted_key,
            trusted_signer_key_id=signer_key_id,
        )
    content_issues: list[str] = []
    if set(document) != RECEIPTS_TOP_FIELDS:
        content_issues.append("RECEIPTS_FIELDS_MISMATCH")
    if document.get("schema") != RECEIPTS_SCHEMA:
        content_issues.append("RECEIPTS_SCHEMA_MISMATCH")
    if document.get("source_sha") != source_sha:
        content_issues.append("RECEIPTS_SOURCE_SHA_MISMATCH")
    hosts, host_issues = _validate_hosts(
        document.get("hosts"), label="RECEIPTS",
    )
    content_issues.extend(host_issues)
    items = document.get("items")
    if not isinstance(items, dict):
        content_issues.append("RECEIPTS_ITEMS_INVALID")
        items = {}
    else:
        for item_id, record in items.items():
            if item_id not in INVENTORY_BY_ID:
                content_issues.append("RECEIPTS_UNKNOWN_ITEM")
                continue
            if type(record) is not dict or set(record) != ITEM_FIELDS:
                content_issues.append("RECEIPTS_ITEM_FIELDS_MISMATCH")
                continue
            if record.get("source_sha") != source_sha:
                content_issues.append("RECEIPTS_ITEM_SOURCE_SHA_MISMATCH")
            entries = record.get("evidence")
            if type(entries) is not dict:
                content_issues.append("RECEIPTS_ITEM_EVIDENCE_INVALID")
                continue
            for kind in entries:
                if kind not in HOST_CLASS_BY_KIND:
                    content_issues.append("RECEIPTS_UNKNOWN_EVIDENCE_KIND")
    all_issues = sorted(set(signature_issues + content_issues))
    return {
        "present": True,
        "signature_valid": signature_valid,
        "schema_ok": not content_issues,
        "items": items,
        "hosts": hosts,
        "evidence_dir": Path(path).parent,
        "signature_issues": sorted(set(signature_issues)),
        "content_issues": sorted(set(content_issues)),
        "issues": all_issues,
        "trusted_signer_key_id": signer_key_id,
    }


def load_g8_receipt(
    path: Path | None,
    *,
    source_sha: str,
    trusted_public_key: Path | None = None,
    trusted_key_sha256: str | None = None,
    signer_key_id: str | None = None,
) -> dict[str, Any]:
    if path is None:
        return {
            "present": False,
            "signature_valid": False,
            "schema_ok": False,
            "hosts": {},
            "receipt": None,
            "evidence_dir": None,
            "signature_issues": ["G8_RECEIPT_ABSENT"],
            "content_issues": [],
            "issues": ["G8_RECEIPT_ABSENT"],
            "trusted_signer_key_id": signer_key_id,
        }
    try:
        document = _read_json(path, limit=8 * 1024 * 1024)
    except (ValueError, UnicodeDecodeError) as error:
        raise CoreAcceptanceError(f"invalid G8 receipt JSON: {error}") from error
    trusted_key, trust_issues = _load_trusted_key(
        trusted_public_key, trusted_key_sha256, signer_key_id,
    )
    signature_valid = False
    signature_issues = list(trust_issues)
    if not trust_issues:
        signature_valid, signature_issues = _verify_signature(
            document, trusted_key=trusted_key,
            trusted_signer_key_id=signer_key_id,
        )
    content_issues: list[str] = []
    if set(document) != G8_TOP_FIELDS:
        content_issues.append("G8_FIELDS_MISMATCH")
    if document.get("schema") != G8_SCHEMA:
        content_issues.append("G8_SCHEMA_MISMATCH")
    if document.get("source_sha") != source_sha:
        content_issues.append("G8_SOURCE_SHA_MISMATCH")
    hosts, host_issues = _validate_hosts(document.get("hosts"), label="G8")
    content_issues.extend(host_issues)
    receipt = document.get("receipt")
    if type(receipt) is not dict:
        content_issues.append("G8_RECEIPT_NOT_OBJECT")
    elif set(receipt) != G8_ENTRY_FIELDS:
        content_issues.append("G8_RECEIPT_FIELDS_MISMATCH")
    all_issues = sorted(set(signature_issues + content_issues))
    return {
        "present": True,
        "signature_valid": signature_valid,
        "schema_ok": not content_issues,
        "hosts": hosts,
        "receipt": receipt,
        "evidence_dir": Path(path).parent,
        "signature_issues": sorted(set(signature_issues)),
        "content_issues": sorted(set(content_issues)),
        "issues": all_issues,
        "trusted_signer_key_id": signer_key_id,
    }


def _validate_entry(
    entry: object,
    *,
    kind: str,
    hosts: dict[str, Any],
    evidence_dir: Path | None,
    trusted_signer_key_id: str | None,
    now: datetime,
    max_age_days: int,
    allowed_fields: frozenset[str] | None = None,
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    if type(entry) is not dict:
        return [], [f"{kind}:ENTRY_NOT_OBJECT"]
    allowed = allowed_fields or (
        OWNER_ENTRY_FIELDS if kind == "owner_host" else BASE_ENTRY_FIELDS
    )
    if set(entry) != allowed:
        invalid.append(f"{kind}:ENTRY_FIELDS_MISMATCH")
    expected_class = HOST_CLASS_BY_KIND[kind]
    if entry.get("host_class") != expected_class:
        invalid.append(f"{kind}:HOST_CLASS_MISMATCH")
    host_id = entry.get("host_id")
    host = hosts.get(host_id)
    if not isinstance(host, dict):
        invalid.append(f"{kind}:HOST_NOT_REGISTERED")
    elif host.get("host_class") != entry.get("host_class"):
        invalid.append(f"{kind}:HOST_REGISTRY_CLASS_MISMATCH")
    if entry.get("signer_key_id") != trusted_signer_key_id:
        invalid.append(f"{kind}:SIGNER_NOT_TRUSTED")
    if entry.get("observed") is not True:
        invalid.append(f"{kind}:NOT_OBSERVED")
    if entry.get("result") != "PASS":
        invalid.append(f"{kind}:RESULT_NOT_PASS")
    for field in ("artifact_sha256", "application_sha256"):
        if not _SHA64.fullmatch(str(entry.get(field, ""))):
            invalid.append(f"{kind}:{field.upper()}_INVALID")
    artifact_path = entry.get("artifact_path")
    claimed = entry.get("artifact_sha256")
    if not isinstance(artifact_path, str) or not artifact_path:
        missing.append(f"{kind}:ARTIFACT_PATH_ABSENT")
    elif _SHA64.fullmatch(str(claimed or "")):
        try:
            if evidence_dir is None:
                raise ValueError("no evidence directory")
            actual = _hash_bounded_evidence_artifact(Path(evidence_dir), artifact_path)
        except (ValueError, OSError):
            invalid.append(f"{kind}:ARTIFACT_BYTES_UNAVAILABLE")
        else:
            if actual != claimed:
                invalid.append(f"{kind}:ARTIFACT_DIGEST_MISMATCH")
    witnessed = _parse_timestamp(entry.get("witnessed_at"))
    if witnessed is None:
        invalid.append(f"{kind}:WITNESSED_AT_INVALID")
    else:
        if witnessed > now + timedelta(hours=1):
            invalid.append(f"{kind}:RECEIPT_FROM_FUTURE")
        if now - witnessed > timedelta(days=max_age_days):
            invalid.append(f"{kind}:RECEIPT_STALE")
    negatives = entry.get("negative_cases")
    if (not isinstance(negatives, list) or not negatives
            or any(not isinstance(value, str) or not value.strip()
                   for value in negatives)):
        invalid.append(f"{kind}:NEGATIVE_CASES_MISSING")
    if kind == "owner_host" and entry.get("real_host") is not True:
        invalid.append(f"{kind}:REAL_HOST_NOT_ATTESTED")
    return missing, invalid


def _evaluate_item(
    spec: ItemSpec,
    *,
    junit: dict[str, Any],
    receipts: dict[str, Any],
    source_sha: str,
    now: datetime,
    max_age_days: int,
) -> dict[str, Any]:
    if not spec.release_scope:
        return {
            "id": spec.item_id,
            "group": spec.group,
            "title": spec.title,
            "release_scope": False,
            "required_evidence": list(spec.required),
            "mapped_source_tests": list(spec.source_tests),
            "state": "NOT_TESTED",
            "missing": ["DEFERRED_POST_CORE_NOT_IN_RELEASE_SCOPE"],
            "invalid": [],
            "evidence": {kind: "NOT_TESTED" for kind in spec.required},
            "acceptance": "NOT_CLAIMED",
        }
    missing: list[str] = []
    invalid: list[str] = []
    evidence: dict[str, str] = {}
    if "source_tests" in spec.required:
        source = _source_status(spec, junit)
        missing.extend(source["missing"])
        if source["state"] == "FAIL":
            invalid.append("SOURCE_TEST_FAILED")
        evidence["source_tests"] = source["state"]
    item_receipt = receipts.get("items", {}).get(spec.item_id)
    for kind in spec.required:
        if kind == "source_tests":
            continue
        if not receipts.get("present"):
            missing.append(f"{kind}:EVIDENCE_RECEIPTS_ABSENT")
            evidence[kind] = "NOT_TESTED"
            continue
        if not receipts.get("signature_valid"):
            missing.append(f"{kind}:RECEIPTS_SIGNATURE_UNTRUSTED")
            missing.extend(
                f"{kind}:SIGNATURE:{issue}"
                for issue in receipts.get("signature_issues", ())
            )
            evidence[kind] = "BLOCKED"
            continue
        if not receipts.get("schema_ok"):
            invalid.extend(str(issue) for issue in receipts.get("content_issues", ()))
            evidence[kind] = "FAIL"
            continue
        if type(item_receipt) is not dict:
            missing.append(f"{kind}:ITEM_RECEIPT_ABSENT")
            evidence[kind] = "NOT_TESTED"
            continue
        entries = item_receipt.get("evidence")
        if type(entries) is not dict:
            invalid.append(f"{kind}:ITEM_EVIDENCE_NOT_OBJECT")
            evidence[kind] = "FAIL"
            continue
        entry = entries.get(kind)
        if entry is None:
            missing.append(f"{kind}:EVIDENCE_ENTRY_ABSENT")
            evidence[kind] = "NOT_TESTED"
            continue
        entry_missing, entry_invalid = _validate_entry(
            entry, kind=kind, hosts=receipts.get("hosts", {}),
            evidence_dir=receipts.get("evidence_dir"),
            trusted_signer_key_id=receipts.get("trusted_signer_key_id"),
            now=now, max_age_days=max_age_days,
        )
        missing.extend(entry_missing)
        invalid.extend(entry_invalid)
        if entry_invalid:
            evidence[kind] = "FAIL"
        elif entry_missing:
            evidence[kind] = "BLOCKED"
        else:
            evidence[kind] = "PASS"
    if invalid:
        state = "FAIL"
    elif missing:
        state = "BLOCKED" if (
            junit.get("present") or receipts.get("present")
        ) else "NOT_TESTED"
    else:
        state = "PASS"
    return {
        "id": spec.item_id,
        "group": spec.group,
        "title": spec.title,
        "release_scope": True,
        "required_evidence": list(spec.required),
        "mapped_source_tests": list(spec.source_tests),
        "state": state,
        "missing": sorted(set(missing)),
        "invalid": sorted(set(invalid)),
        "evidence": evidence,
        "acceptance": "NOT_CLAIMED",
    }


def _evaluate_g8(
    g8_receipt: dict[str, Any],
    *,
    source_sha: str,
    now: datetime,
    max_age_days: int,
) -> dict[str, Any]:
    if not g8_receipt.get("present"):
        return {
            "status": "NOT_CERTIFIED",
            "certified": False,
            "reasons": ["G8_RECEIPT_ABSENT"],
            "real_host_receipt_supplied": False,
        }
    if not g8_receipt.get("signature_valid"):
        return {
            "status": "NOT_CERTIFIED",
            "certified": False,
            "reasons": sorted(
                f"G8:{issue}" for issue in g8_receipt.get("signature_issues", ())
            ),
            "real_host_receipt_supplied": True,
        }
    if not g8_receipt.get("schema_ok"):
        return {
            "status": "NOT_CERTIFIED",
            "certified": False,
            "reasons": sorted(
                f"G8:{issue}" for issue in g8_receipt.get("content_issues", ())
            ),
            "real_host_receipt_supplied": True,
        }
    reasons: list[str] = []
    receipt = g8_receipt.get("receipt")
    if not isinstance(receipt, dict):
        reasons.append("G8_RECEIPT_NOT_OBJECT")
        receipt = {}
    if receipt.get("owner_approved") is not True:
        reasons.append("G8_OWNER_APPROVAL_ABSENT")
    owner_host_id = receipt.get("host_id")
    remote_host_id = receipt.get("remote_host_id")
    if not isinstance(remote_host_id, str) or remote_host_id == owner_host_id:
        reasons.append("G8_DISTINCT_REMOTE_HOST_ABSENT")
    else:
        remote = g8_receipt.get("hosts", {}).get(remote_host_id)
        if not isinstance(remote, dict) or remote.get("host_class") != "REMOTE":
            reasons.append("G8_REMOTE_HOST_NOT_REGISTERED")
    missing, invalid = _validate_entry(
        receipt, kind="owner_host", hosts=g8_receipt.get("hosts", {}),
        evidence_dir=g8_receipt.get("evidence_dir"),
        trusted_signer_key_id=g8_receipt.get("trusted_signer_key_id"),
        now=now, max_age_days=max_age_days,
        allowed_fields=G8_ENTRY_FIELDS,
    )
    reasons.extend(f"G8:{value}" for value in missing)
    reasons.extend(f"G8:{value}" for value in invalid)
    certified = not reasons
    return {
        "status": "CERTIFIED" if certified else "NOT_CERTIFIED",
        "certified": certified,
        "reasons": sorted(set(reasons)),
        "real_host_receipt_supplied": True,
    }


def _counts(states: list[str]) -> dict[str, int]:
    counts = {state: 0 for state in STATES}
    for state in states:
        counts[state] = counts.get(state, 0) + 1
    return counts


def collect(
    *,
    junit_path: Path | None,
    source_sha: str,
    runner: str,
    receipts_path: Path | None = None,
    g8_receipt_path: Path | None = None,
    trusted_public_key: Path | None = None,
    trusted_key_sha256: str | None = None,
    signer_key_id: str | None = None,
    now: datetime | None = None,
    max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
) -> dict[str, Any]:
    if not isinstance(source_sha, str) or not _SHA40.fullmatch(source_sha):
        raise CoreAcceptanceError("exact lowercase 40-hex source SHA required")
    if not isinstance(max_age_days, int) or max_age_days < 1:
        raise CoreAcceptanceError("max_age_days must be a positive integer")
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utcoffset() is None:
        raise CoreAcceptanceError("evaluation time must be timezone aware")
    junit = parse_junit(junit_path)
    trust = {
        "trusted_public_key": trusted_public_key,
        "trusted_key_sha256": trusted_key_sha256,
        "signer_key_id": signer_key_id,
    }
    receipts = load_receipts(receipts_path, source_sha=source_sha, **trust)
    g8_receipt = load_g8_receipt(
        g8_receipt_path, source_sha=source_sha, **trust,
    )
    items = [
        _evaluate_item(
            spec, junit=junit, receipts=receipts, source_sha=source_sha,
            now=observed_now, max_age_days=max_age_days,
        )
        for spec in INVENTORY
    ]
    g8 = _evaluate_g8(
        g8_receipt, source_sha=source_sha, now=observed_now,
        max_age_days=max_age_days,
    )
    scoped = [item for item in items if item["release_scope"]]
    all_scoped_pass = all(item["state"] == "PASS" for item in scoped)
    source_only = not receipts.get("present")
    if source_only:
        evidence_scope = "SOURCE_ONLY"
    elif receipts.get("signature_valid"):
        evidence_scope = "SIGNED_DECLARED_RECEIPTS"
    else:
        evidence_scope = "UNTRUSTED_RECEIPTS"
    return {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "runner": runner,
        "generated_at": observed_now.isoformat(),
        "authoritative_status_unchanged": True,
        "authoritative_sources": [
            "docs/sofia2/CORE_1_0_PLAN.md",
            "docs/development/AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md",
            "docs/development/AEGIS_OWNER_ONLY_GO_LIVE_ACCEPTANCE_2026-11-09.md",
            "docs/development/V18_TASK_STATUS_STANDARD.md",
        ],
        "evidence_rules": {
            "pass_requires_all_declared_kinds": True,
            "skipped_test_is_pass": False,
            "missing_negative_cases_is_pass": False,
            "stale_or_future_receipt_is_pass": False,
            "mismatched_source_sha_is_pass": False,
            "mismatched_artifact_digest_is_pass": False,
            "unregistered_host_or_signer_is_pass": False,
            "self_declared_signers_establish_trust": False,
            "unsigned_or_forged_receipt_is_pass": False,
            "g8_from_disposable_evidence_is_certified": False,
            "max_age_days": max_age_days,
        },
        "source_only": source_only,
        "evidence_scope": evidence_scope,
        "core_release_verdict": "GO" if all_scoped_pass else "NO_GO",
        "core_release_verdict_scope": "NON_G8_IN_SCOPE_ITEMS",
        "release_accepted": bool(all_scoped_pass and g8["certified"]),
        "production_authorized": False,
        "acceptance": "NOT_CLAIMED",
        "notes": [
            "PASS is scoped to the exact declared source tests and receipts.",
            "Receipt trust requires a caller-supplied Ed25519 key, fingerprint and signer ID.",
            "Self-declared signer and host maps never establish receipt trust.",
            "Source-only evidence never certifies an installed or owner host.",
            "G8 requires a distinct signed receipt and is never inferred from disposable data.",
            "Authoritative acceptance documents were not modified.",
        ],
        "junit": {
            "present": junit["present"],
            "sha256": junit["sha256"],
            "cases": junit["cases"],
            "issues": junit["issues"],
        },
        "receipts": {
            "present": receipts.get("present"),
            "signature_valid": receipts.get("signature_valid"),
            "schema_ok": receipts.get("schema_ok"),
            "signature_issues": receipts.get("signature_issues", []),
            "content_issues": receipts.get("content_issues", []),
            "issues": receipts.get("issues", []),
        },
        "g8_receipt": {
            "present": g8_receipt.get("present"),
            "signature_valid": g8_receipt.get("signature_valid"),
            "schema_ok": g8_receipt.get("schema_ok"),
            "issues": g8_receipt.get("issues", []),
        },
        "inventory": {
            "item_count": len(items),
            "release_scope_item_count": len(scoped),
            "items": items,
            "counts": _counts([item["state"] for item in items]),
            "release_scope_counts": _counts([item["state"] for item in scoped]),
        },
        "g8": g8,
    }


def _source_test_files() -> list[str]:
    return sorted({name for spec in INVENTORY for name in spec.source_tests})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Sign a receipt bundle with: python -m "
            "tools.aegis_sign_acceptance_receipt --receipt core-receipts.json "
            "--private-key owner-key.pem --signer-key-id owner-key-1 "
            "--output core-receipts.signed.json"
        ),
    )
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--runner", default=sys.platform)
    parser.add_argument(
        "--receipts", type=Path,
        help="Signed receipt bundle; requires the three trust arguments.",
    )
    parser.add_argument(
        "--g8-receipt", type=Path,
        help="Separate signed G8 real-host receipt; requires the trust arguments.",
    )
    parser.add_argument(
        "--trusted-public-key", type=Path,
        help="PEM Ed25519 public key trusted for receipt signatures.",
    )
    parser.add_argument(
        "--trusted-key-sha256",
        help="Lowercase SHA-256 of the exact PEM public-key file bytes.",
    )
    parser.add_argument(
        "--signer-key-id",
        help="Expected signer key ID bound inside every signature envelope.",
    )
    parser.add_argument("--max-age-days", type=int, default=_DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--list-source-tests", action="store_true",
        help="Print the unique mapped source-test files and exit.",
    )
    args = parser.parse_args(argv)
    if args.list_source_tests:
        for name in _source_test_files():
            print(name)
        return 0
    if args.receipts or args.g8_receipt:
        missing = [
            name for name, value in (
                ("--trusted-public-key", args.trusted_public_key),
                ("--trusted-key-sha256", args.trusted_key_sha256),
                ("--signer-key-id", args.signer_key_id),
            ) if value is None
        ]
        if missing:
            parser.error(
                "signed receipts require " + ", ".join(missing)
            )
    try:
        source_sha = args.source_sha or _git_sha()
        report = collect(
            junit_path=args.junit,
            source_sha=source_sha,
            runner=args.runner,
            receipts_path=args.receipts,
            g8_receipt_path=args.g8_receipt,
            trusted_public_key=args.trusted_public_key,
            trusted_key_sha256=args.trusted_key_sha256,
            signer_key_id=args.signer_key_id,
            max_age_days=args.max_age_days,
        )
        payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        return 0
    except (CoreAcceptanceError, OSError, ValueError, TypeError,
            json.JSONDecodeError) as error:
        print(
            json.dumps({
                "schema": SCHEMA,
                "result": "COLLECTOR_REFUSED",
                "reason": str(error),
                "core_release_verdict": "NO_GO",
                "release_accepted": False,
                "production_authorized": False,
            }, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
