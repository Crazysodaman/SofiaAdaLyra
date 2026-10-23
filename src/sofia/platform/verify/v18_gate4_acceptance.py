"""Independent Gate 4 acceptance receipts, separate from historical source claims.

A certificate is meaningful only when signed with an independently approved
Ed25519 reviewer key provisioned OUTSIDE the repository. An unchecked reviewer
name, a source file, a GitHub CI badge, or a self-issued signature is not a
task acceptance certificate. Never persist private key material.
"""
from __future__ import annotations

import base64
import binascii
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.verify.v18_roadmap import RoadmapIntegrityError, _within

REGISTRY_PATH = "docs/development/v18-gate4-independent-acceptance.json"
REGISTRY_SCHEMA = "sofia.v18-independent-gate4-acceptance-v1"
_KEY_ENV = "SOFIA_GATE4_TRUSTED_REVIEWER_KEYS"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = {
    "task_id", "reviewed_revision", "original_requirement_sha256",
    "gate4_proof_sha256", "ci_run_id", "review_evidence_path",
    "review_evidence_sha256", "decision", "all_original_requirements_verified",
    "independent_test_coverage_verified", "original_host_trials_verified_if_required",
}


def _decode(value: object, length: int) -> bytes:
    if not isinstance(value, str):
        raise RoadmapIntegrityError("review signature or key must be text")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RoadmapIntegrityError("malformed review signature or public key") from exc
    if len(decoded) != length:
        raise RoadmapIntegrityError("incorrect review signature or public key length")
    return decoded


def _trusted_keys() -> dict[str, bytes]:
    """Owner-provisioned external trust anchors. Missing means NO awards."""
    raw = os.environ.get(_KEY_ENV)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise RoadmapIntegrityError("trusted reviewer key configuration is not JSON") from exc
    if not isinstance(value, dict) or len(value) > 20:
        raise RoadmapIntegrityError("invalid trusted reviewer configuration")
    keys = {}
    for reviewer, public_key in value.items():
        if not isinstance(reviewer, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{3,80}", reviewer):
            raise RoadmapIntegrityError("invalid independent reviewer ID")
        keys[reviewer] = _decode(public_key, 32)
    return keys


def load_review_receipts(root: Path) -> tuple[dict[str, dict], dict[str, bytes]]:
    """Parse strict ledger, but never use a self-declared reviewer as trust."""
    registry = json.loads(_within(root, REGISTRY_PATH).read_text(encoding="utf-8"))
    if not isinstance(registry, dict) or set(registry) != {"schema", "certificates"}:
        raise RoadmapIntegrityError("invalid independent acceptance registry fields")
    if registry["schema"] != REGISTRY_SCHEMA:
        raise RoadmapIntegrityError("unknown independent acceptance schema")
    certificates = registry["certificates"]
    if not isinstance(certificates, list) or len(certificates) > 780:
        raise RoadmapIntegrityError("invalid independent acceptance certificate count")
    mapped = {}
    for item in certificates:
        if not isinstance(item, dict) or set(item) != {"reviewer_id", "statement", "signature"}:
            raise RoadmapIntegrityError("invalid independent acceptance certificate")
        statement = item["statement"]
        if not isinstance(statement, dict) or set(statement) != _REQUIRED:
            raise RoadmapIntegrityError("incomplete independent acceptance statement")
        task_id = statement.get("task_id")
        if not isinstance(task_id, str) or task_id in mapped:
            raise RoadmapIntegrityError("invalid or duplicated accepted task ID")
        mapped[task_id] = item
    return mapped, _trusted_keys()


def _git_blob(root: Path, path: str) -> bytes:
    _within(root, path)
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:" + path],
            cwd=root, capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RoadmapIntegrityError("review source cannot be read from HEAD") from exc
    if result.returncode != 0 or len(result.stdout) > 2_000_000:
        raise RoadmapIntegrityError("review source absent or too large")
    return result.stdout


def authenticate_review(
    root: Path, *,
    task_id: str, original_requirement: str, proofs: list[dict],
    certificate: dict | None, trusted_keys: dict[str, bytes],
) -> bool:
    """Fail closed unless a pinned independent signer verified this exact task."""
    if certificate is None or len(proofs) != 4:
        return False
    reviewer = certificate["reviewer_id"]
    public_key = trusted_keys.get(reviewer)
    if public_key is None:
        # A certificate in Git is NOT authority to provision its own key.
        return False
    statement = certificate["statement"]
    final = proofs[-1]
    ci = final["ci"]
    expected = {
        "task_id": task_id,
        "reviewed_revision": final["revision"],
        "original_requirement_sha256": sha256(
            original_requirement.encode("utf-8")
        ).hexdigest(),
        "gate4_proof_sha256": final["sha256"],
        "ci_run_id": ci["run_id"],
    }
    if any(statement.get(key) != value for key, value in expected.items()):
        raise RoadmapIntegrityError(task_id + ": independent receipt contradicts source")
    if not _SHA.fullmatch(statement["reviewed_revision"]):
        raise RoadmapIntegrityError("independent review revision is invalid")
    if not _DIGEST.fullmatch(statement["review_evidence_sha256"]):
        raise RoadmapIntegrityError("independent review document hash is invalid")
    if (
        statement["decision"] != "accepted_gate4"
        or statement["all_original_requirements_verified"] is not True
        or statement["independent_test_coverage_verified"] is not True
        or statement["original_host_trials_verified_if_required"] is not True
    ):
        raise RoadmapIntegrityError(task_id + ": independent acceptance conditions incomplete")
    envelope = {
        "reviewer_id": reviewer,
        "statement": statement,
    }
    payload = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            _decode(certificate["signature"], 64), payload
        )
    except (InvalidSignature, ValueError) as exc:
        raise RoadmapIntegrityError(task_id + ": independent review signature invalid") from exc
    reviewed_blob = _git_blob(root, statement["review_evidence_path"])
    if sha256(reviewed_blob).hexdigest() != statement["review_evidence_sha256"]:
        raise RoadmapIntegrityError(task_id + ": reviewed acceptance file changed")
    return True
