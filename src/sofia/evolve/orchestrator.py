"""Governed bridge from EVOLVE code proposals through DEV and VERIFY."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from sofia.dev.capability import DevToolService
from sofia.dev.git_workspace import GitWorkspace

from .code import CodeEvolutionProposal
from .lifecycle import (
    EvolutionEvidence,
    EvolutionLifecycleStore,
    EvolutionProposalStatus,
)


class CandidateVerificationRunner(Protocol):
    def verify(self, *, expected_paths: tuple[str, ...]) -> dict[str, Any]: ...


class SubprocessCandidateVerificationRunner:
    """Run the fixed candidate gate; no caller-supplied commands are accepted."""

    def __init__(self, workspace: Path, *, timeout_seconds: int = 1800) -> None:
        if not isinstance(workspace, Path) or not workspace.is_dir():
            raise ValueError("candidate verification workspace must exist")
        if type(timeout_seconds) is not int or not 60 <= timeout_seconds <= 7200:
            raise ValueError("candidate verification timeout must be in 60..7200")
        self.workspace = workspace.resolve()
        self.timeout_seconds = timeout_seconds

    def verify(self, *, expected_paths: tuple[str, ...]) -> dict[str, Any]:
        if not expected_paths:
            raise ValueError("candidate verification requires reviewed changed paths")
        before = GitWorkspace(self.workspace).changed_paths()
        if before != tuple(sorted(set(expected_paths))):
            raise RuntimeError(
                "candidate workspace changes do not match reviewed DEV paths"
            )
        with TemporaryDirectory(prefix="sofia-evolve-verify-") as temp:
            evidence_path = Path(temp) / "candidate-evidence.json"
            result = subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "sofia.verify.gate",
                    "--phase",
                    "candidate",
                    "--evidence-path",
                    str(evidence_path),
                ),
                cwd=self.workspace,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            if not evidence_path.is_file():
                detail = (result.stderr or result.stdout).strip()[-1000:]
                raise RuntimeError(
                    "candidate verification produced no evidence"
                    + (f": {detail}" if detail else "")
                )
            document = json.loads(evidence_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise RuntimeError("candidate verification evidence must be an object")
            if document.get("phase") != "candidate":
                raise RuntimeError("candidate verification returned the wrong phase")
            if bool(document.get("accepted")) != (result.returncode == 0):
                raise RuntimeError("candidate verification exit status contradicts evidence")
            after = GitWorkspace(self.workspace).changed_paths()
            if after != before:
                raise RuntimeError("candidate verification changed tracked proposal scope")
            document["reviewed_changed_paths"] = list(before)
            return document


class CodeEvolutionOrchestrator:
    """Join canonical EVOLVE evidence to DEV without inheriting DEV authority."""

    def __init__(
        self,
        *,
        lifecycle: EvolutionLifecycleStore,
        dev_service: DevToolService,
        verifier: CandidateVerificationRunner,
    ) -> None:
        if not isinstance(lifecycle, EvolutionLifecycleStore):
            raise TypeError("lifecycle must be EvolutionLifecycleStore")
        if not isinstance(dev_service, DevToolService):
            raise TypeError("dev_service must be DevToolService")
        if not callable(getattr(verifier, "verify", None)):
            raise TypeError("candidate verifier must implement verify")
        self.lifecycle = lifecycle
        self.dev_service = dev_service
        self.verifier = verifier

    def _code_proposal(
        self,
        proposal_id: str,
        *,
        now: datetime,
    ) -> CodeEvolutionProposal:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        proposal = self.lifecycle.proposal_object(proposal_id)
        if not isinstance(proposal, CodeEvolutionProposal):
            raise TypeError("operation requires a canonical code proposal")
        moment = now.astimezone(timezone.utc)
        if moment < proposal.created_at.astimezone(timezone.utc):
            raise RuntimeError("code proposal is not active yet")
        if moment >= proposal.expires_at.astimezone(timezone.utc):
            raise RuntimeError("code proposal expired")
        return proposal

    def build_candidate(self, proposal_id: str, *, now: datetime) -> dict[str, Any]:
        proposal = self._code_proposal(proposal_id, now=now)
        record = self.lifecycle.get_proposal(proposal_id)
        if record.status not in {
            EvolutionProposalStatus.PROPOSED,
            EvolutionProposalStatus.UNDER_REVIEW,
        }:
            raise RuntimeError("code proposal is not ready to build")
        candidate = self.dev_service.build(
            {
                "proposal_id": proposal.proposal_id,
                "base_sha": proposal.base_sha,
                "prompt": proposal.prompt,
                "allowed_paths": list(proposal.allowed_paths),
                "tests": list(proposal.tests),
            }
        )
        patch = candidate.get("patch", "")
        evidence_id = f"dev-candidate:{proposal.proposal_id}"
        evidence = EvolutionEvidence(
            evidence_id=evidence_id,
            kind="dev-candidate",
            source_ref=f"dev:candidate:{proposal.proposal_id}",
            summary="DEV built an isolated candidate within the proposal scope.",
            payload={
                "base_sha": candidate["base_sha"],
                "changed_paths": list(candidate["changed_paths"]),
                "allowed_paths": list(candidate["allowed_paths"]),
                "tests_passed": candidate["tests_passed"],
                "tests": list(candidate.get("tests", proposal.tests)),
                "iterations": int(candidate.get("iterations", 1)),
                "verification_output_sha256": candidate.get(
                    "verification_output_sha256"
                ),
                "patch_sha256": sha256(patch.encode("utf-8")).hexdigest(),
                "risk": "isolated_candidate_only",
                "rollback": "discard durable candidate; production workspace unchanged",
                "isolation": {
                    "detached_worktree": True,
                    "environment_scrubbed": True,
                    "network_isolation": False,
                    "security_boundary": "host process authority remains authoritative",
                },
            },
            observed_at=now,
            recorded_at=now,
        )
        self.lifecycle.record_evidence(evidence)
        self.lifecycle.attach_evidence(proposal_id, evidence_id)
        self.lifecycle.transition(
            proposal_id,
            expected=(record.status,),
            status=EvolutionProposalStatus.CANDIDATE_BUILT,
            now=now,
        )
        return {**candidate, "evidence_id": evidence_id}

    def apply_candidate(
        self,
        proposal_id: str,
        *,
        approval_id: str,
        now: datetime,
    ) -> dict[str, Any]:
        self._code_proposal(proposal_id, now=now)
        record = self.lifecycle.get_proposal(proposal_id)
        if record.status is not EvolutionProposalStatus.CANDIDATE_BUILT:
            raise RuntimeError("only a built code candidate can be applied")
        result = self.dev_service.apply(
            {"proposal_id": proposal_id, "approval_id": approval_id}
        )
        self.lifecycle.transition(
            proposal_id,
            expected=(EvolutionProposalStatus.CANDIDATE_BUILT,),
            status=EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION,
            now=now,
        )
        return result

    def verify_candidate(self, proposal_id: str, *, now: datetime) -> dict[str, Any]:
        self._code_proposal(proposal_id, now=now)
        record = self.lifecycle.get_proposal(proposal_id)
        if record.status is not EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION:
            raise RuntimeError("only an applied code candidate can be verified")
        candidate_evidence = self.lifecycle.get_evidence(
            f"dev-candidate:{proposal_id}"
        )
        changed_paths = candidate_evidence.payload.get("changed_paths")
        if not isinstance(changed_paths, list) or not all(
            isinstance(item, str) for item in changed_paths
        ):
            raise RuntimeError("DEV candidate evidence lacks reviewed changed paths")
        document = self.verifier.verify(expected_paths=tuple(changed_paths))
        encoded = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        evidence_id = f"verify-candidate:{sha256(encoded).hexdigest()[:32]}"
        evidence = EvolutionEvidence(
            evidence_id=evidence_id,
            kind="candidate-verification",
            source_ref=f"verify:candidate:{document.get('git_revision', 'unknown')}",
            summary=(
                "Candidate verification accepted."
                if document.get("accepted") is True
                else "Candidate verification rejected; rollback is required."
            ),
            payload=document,
            observed_at=now,
            recorded_at=now,
        )
        self.lifecycle.record_evidence(evidence)
        self.lifecycle.attach_evidence(proposal_id, evidence_id)
        status = (
            EvolutionProposalStatus.VERIFIED
            if document.get("accepted") is True
            else EvolutionProposalStatus.ROLLBACK_REQUIRED
        )
        self.lifecycle.transition(
            proposal_id,
            expected=(EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION,),
            status=status,
            now=now,
        )
        return {"evidence_id": evidence_id, **document}

    def commit_candidate(
        self,
        proposal_id: str,
        *,
        approval_id: str,
        message: str,
        now: datetime,
    ) -> dict[str, Any]:
        self._code_proposal(proposal_id, now=now)
        if self.lifecycle.get_proposal(proposal_id).status is not EvolutionProposalStatus.VERIFIED:
            raise RuntimeError("candidate must pass VERIFY before commit")
        result = self.dev_service.commit(
            {
                "proposal_id": proposal_id,
                "approval_id": approval_id,
                "message": message,
            }
        )
        self.lifecycle.transition(
            proposal_id,
            expected=(EvolutionProposalStatus.VERIFIED,),
            status=EvolutionProposalStatus.COMMITTED_PENDING_RELEASE,
            now=now,
        )
        return result

    def rollback_candidate(
        self,
        proposal_id: str,
        *,
        approval_id: str,
        now: datetime,
    ) -> dict[str, Any]:
        self._code_proposal(proposal_id, now=now)
        allowed = (
            EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION,
            EvolutionProposalStatus.VERIFIED,
            EvolutionProposalStatus.ROLLBACK_REQUIRED,
        )
        if self.lifecycle.get_proposal(proposal_id).status not in allowed:
            raise RuntimeError("code candidate is not rollback-eligible")
        result = self.dev_service.rollback(
            {"proposal_id": proposal_id, "approval_id": approval_id}
        )
        self.lifecycle.transition(
            proposal_id,
            expected=allowed,
            status=EvolutionProposalStatus.ROLLED_BACK,
            now=now,
        )
        return result
