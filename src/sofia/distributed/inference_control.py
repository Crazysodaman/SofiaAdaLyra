"""Durable admission and audit boundary for remote Fleet inference.

Prompts and model responses are never written to the inference ledger. The
controller requires active enrollment, an approved endpoint, an exact human
grant, authenticated peer identity, and a fresh advertised inference
capability before sending cognitive content to a remote worker.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Protocol
from uuid import UUID, uuid4

from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.config.model import ProviderConfiguration
from sofia.distributed.capabilities import (
    CapabilityInventory,
    inventory_is_current,
)
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.model import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.inference import (
    RemoteInferenceRequest,
    RemoteInferenceResponse,
)


_CAPABILITY = "llm.inference"
_OPERATION = "chat"


class RemoteInferenceDenied(PermissionError):
    """Remote cognition was denied before an inference result was accepted."""


class RemoteInferenceUncertain(RuntimeError):
    """A remote inference may have completed, but no valid response was accepted."""


class RemoteInferenceTransport(Protocol):
    def authenticate(self, enrollment: NodeEnrollment) -> bool: ...
    def discover(self, enrollment: NodeEnrollment) -> CapabilityInventory: ...
    def infer(
        self,
        enrollment: NodeEnrollment,
        request: RemoteInferenceRequest,
    ) -> RemoteInferenceResponse: ...


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("remote inference time must be timezone-aware")
    return value.astimezone(timezone.utc)


class DurableInferenceLedger:
    """Content-free one-shot inference audit ledger."""

    _FINAL = frozenset(
        {
            "denied_after_reserve",
            "reported_success",
            "uncertain",
        }
    )

    def __init__(self, path: Path | str) -> None:
        target = Path(path)
        if str(path) == ":memory:":
            raise ValueError("durable inference ledger cannot be in-memory")
        if not target.parent.exists():
            raise FileNotFoundError(
                "inference ledger parent directory must exist"
            )
        self.path = target
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS remote_inference_ledger (
                    request_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    grant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=3)
        db.execute("PRAGMA busy_timeout=3000")
        return db

    def reserve(
        self,
        request: RemoteInferenceRequest,
        *,
        now: datetime,
    ) -> None:
        if not isinstance(request, RemoteInferenceRequest):
            raise TypeError("request must be RemoteInferenceRequest")
        moment = _utc(now)
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    """
                    INSERT INTO remote_inference_ledger (
                        request_id,node_id,grant_id,provider,model,
                        observed_at,status
                    )
                    VALUES (?,?,?,?,?,?,'reserved')
                    """,
                    (
                        str(request.request_id),
                        str(request.node_id),
                        str(request.grant_id),
                        request.provider.provider,
                        request.provider.model,
                        moment.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RemoteInferenceDenied(
                "duplicate remote inference request ID"
            ) from exc

    def finalize(self, request_id: UUID, *, status: str) -> None:
        if not isinstance(request_id, UUID):
            raise TypeError("request_id must be UUID")
        if status not in self._FINAL:
            raise ValueError("invalid remote inference final status")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """
                UPDATE remote_inference_ledger
                SET status=?
                WHERE request_id=? AND status='reserved'
                """,
                (status, str(request_id)),
            )
            if changed.rowcount != 1:
                raise RuntimeError(
                    "remote inference request has no active reservation"
                )

    def status(self, request_id: UUID) -> str | None:
        if not isinstance(request_id, UUID):
            raise TypeError("request_id must be UUID")
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT status FROM remote_inference_ledger
                WHERE request_id=?
                """,
                (str(request_id),),
            ).fetchone()
        return None if row is None else str(row[0])


class DurableRemoteInferenceControl:
    """Perform one authenticated, exact-grant remote cognitive request."""

    def __init__(
        self,
        *,
        transport: RemoteInferenceTransport,
        identity_path: Path | str,
        endpoint_path: Path | str,
        authorization_path: Path | str,
        ledger_path: Path | str,
        max_inventory_age: timedelta = timedelta(minutes=5),
    ) -> None:
        if not isinstance(max_inventory_age, timedelta) or (
            max_inventory_age <= timedelta(0)
        ):
            raise ValueError("max_inventory_age must be positive")
        self.transport = transport
        self.identities = DurableNodeIdentityRegistry(identity_path)
        self.endpoints = DurableEndpointPolicy(endpoint_path)
        self.authorization = DurableRemoteAuthorization(authorization_path)
        self.ledger = DurableInferenceLedger(ledger_path)
        self.max_inventory_age = max_inventory_age

    def infer(
        self,
        *,
        node_id: UUID,
        provider: ProviderConfiguration,
        request: CognitiveRequest,
        now: datetime,
        request_id: UUID | None = None,
    ) -> CognitiveResponse:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be UUID")
        if not isinstance(provider, ProviderConfiguration):
            raise TypeError("provider must be ProviderConfiguration")
        if not isinstance(request, CognitiveRequest):
            raise TypeError("request must be CognitiveRequest")
        moment = _utc(now)
        inference_id = request_id or uuid4()
        if not isinstance(inference_id, UUID):
            raise TypeError("request_id must be UUID or None")

        enrollment = self.identities.get(node_id)
        if enrollment is None:
            raise RemoteInferenceDenied(
                "node is not actively enrolled"
            )
        endpoint = self.endpoints.get(node_id)
        if endpoint is None:
            raise RemoteInferenceDenied(
                "node has no active approved endpoint"
            )
        grant = self.authorization.find_active(
            node_id=node_id,
            capability=_CAPABILITY,
            operation=_OPERATION,
            now=moment,
        )
        if grant is None:
            raise RemoteInferenceDenied(
                "no active exact-scope human grant for remote inference"
            )

        remote = RemoteInferenceRequest(
            request_id=inference_id,
            node_id=node_id,
            grant_id=grant.grant_id,
            provider=provider,
            request=request,
        )
        self.ledger.reserve(remote, now=moment)
        try:
            if self.transport.authenticate(enrollment) is not True:
                raise RemoteInferenceDenied(
                    "remote inference peer authentication failed"
                )
            inventory = self.transport.discover(enrollment)
            if (
                not isinstance(inventory, CapabilityInventory)
                or inventory.node_id != node_id
                or not inventory_is_current(
                    inventory,
                    now=moment,
                    max_age=self.max_inventory_age,
                    max_future_skew=timedelta(seconds=5),
                )
                or not inventory.advertises(_CAPABILITY, _OPERATION)
            ):
                raise RemoteInferenceDenied(
                    "remote inference capability inventory is invalid, stale, or absent"
                )
        except RemoteInferenceDenied:
            self.ledger.finalize(
                remote.request_id,
                status="denied_after_reserve",
            )
            raise
        except Exception as exc:
            self.ledger.finalize(
                remote.request_id,
                status="denied_after_reserve",
            )
            raise RemoteInferenceDenied(
                "remote inference peer admission failed"
            ) from exc

        try:
            response = self.transport.infer(enrollment, remote)
        except Exception as exc:
            self.ledger.finalize(
                remote.request_id,
                status="uncertain",
            )
            raise RemoteInferenceUncertain(
                "remote inference outcome is unknown"
            ) from exc

        if (
            not isinstance(response, RemoteInferenceResponse)
            or response.request_id != remote.request_id
            or response.node_id != node_id
        ):
            self.ledger.finalize(
                remote.request_id,
                status="uncertain",
            )
            raise RemoteInferenceUncertain(
                "remote inference returned a mismatched response"
            )
        self.ledger.finalize(
            remote.request_id,
            status="reported_success",
        )
        return response.response

    def close(self) -> None:
        self.identities.close()
        self.endpoints.close()
        self.authorization.close()
