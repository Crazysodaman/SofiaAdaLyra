"""Capability-gated creative artifact generation for Project Forge."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import json

from sofia.capability.model import Capability, CapabilityRequest

from .adapters import NativeCreativeAdapter
from .model import ArtifactKind, CreativeRequest
from .service import CreativeService


def creative_request_digest(value: dict[str, object]) -> str:
    """Return the stable digest bound to a Project Forge execution grant."""
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class CreativeArtifactCapability:
    """Narrow host validator; model output cannot supply receipts or authority."""

    capability = Capability(
        name="creative.artifact.create",
        description="Create one bounded artifact in an existing scoped creative project.",
    )

    def __init__(
        self, service: CreativeService, *,
        claim_authorization: Callable[[str, str, str, str], bool],
        finish_authorization: Callable[[str, bool], None],
    ) -> None:
        if not isinstance(service, CreativeService):
            raise TypeError("CreativeService required")
        if not callable(claim_authorization) or not callable(finish_authorization):
            raise TypeError("durable Project Forge authorization callbacks required")
        self.service = service
        self.claim_authorization = claim_authorization
        self.finish_authorization = finish_authorization

    def execute(self, request: CapabilityRequest) -> dict[str, object]:
        if request.capability != self.capability:
            raise ValueError("wrong creative capability")
        value = dict(request.parameters)
        required = {
            "request_id", "project_id", "artifact_id", "kind", "title",
            "owner_principal_id", "author_principal_id", "audience_id",
            "license_id", "specification", "evidence_ref",
        }
        if set(value) != required:
            raise ValueError("creative capability parameters do not match the reviewed schema")
        if value["author_principal_id"] != "sofia":
            raise PermissionError("autonomous creative capability is restricted to Sofía authorship")
        if request.requested_scope != value["project_id"]:
            raise PermissionError("creative capability scope must match the exact project")
        specification = value["specification"]
        if not isinstance(specification, dict):
            raise TypeError("creative specification must be an object")
        request_id = str(value["request_id"])
        if not self.claim_authorization(
            request_id, str(value["project_id"]), str(value["artifact_id"]),
            creative_request_digest(value),
        ):
            raise PermissionError("no unused Project Forge execution grant matches this request")
        creative_request = CreativeRequest(
            request_id=value["request_id"],
            project_id=value["project_id"],
            artifact_id=value["artifact_id"],
            kind=ArtifactKind(value["kind"]),
            title=value["title"],
            owner_principal_id=value["owner_principal_id"],
            author_principal_id=value["author_principal_id"],
            audience_id=value["audience_id"],
            license_id=value["license_id"],
            specification=specification,
            evidence_ref=value["evidence_ref"],
        )
        try:
            revision = self.service.create(
                creative_request, NativeCreativeAdapter(), now=datetime.now(timezone.utc),
            )
        except Exception:
            self.finish_authorization(request_id, False)
            raise
        self.finish_authorization(request_id, True)
        return {
            "artifact_id": revision.artifact_id,
            "project_id": revision.project_id,
            "revision": revision.revision,
            "kind": revision.kind.value,
            "sha256": revision.content_sha256,
            "byte_size": revision.byte_size,
            "media_type": revision.media_type,
            "tool_id": revision.tool_id,
            "tool_version": revision.tool_version,
            "test_summary": revision.test_summary,
            "source_receipt_id": revision.source_receipt_id,
        }
