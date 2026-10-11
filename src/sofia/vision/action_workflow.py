"""Owner-reviewed, capture-before/input/capture-after transaction.

Each step uses a different one-use FIDO2 approval. Screenshot pixels alone
cannot authorize an action, and pixel differences cannot prove the desired
application outcome. Partial failure is explicitly UNCERTAIN and NEVER
auto-retried. Only the separately authenticated local owner invokes this path.
"""
from __future__ import annotations

from dataclasses import dataclass

from sofia.vision.capture import ScreenCaptureService, local_target_id
from sofia.vision.desktop_control import DesktopAction, DesktopInputService
from sofia.vision.journeys import ScreenJourney, ScreenJourneyRequest


@dataclass(frozen=True, slots=True)
class ReviewedScreenAction:
    action: DesktopAction
    before: ScreenJourneyRequest
    after: ScreenJourneyRequest

    def __post_init__(self) -> None:
        if not isinstance(self.action, DesktopAction):
            raise TypeError("a typed, bounded exact GUI operation is required")
        target = local_target_id(
            self.action.host_id, self.action.window_handle, self.action.process_id,
        )
        if not isinstance(self.before, ScreenJourneyRequest) or not isinstance(
            self.after, ScreenJourneyRequest,
        ):
            raise TypeError("two independently approved screen requests required")
        before, after = self.before.permit, self.after.permit
        if (
            self.before.journey is not ScreenJourney.LOOK_AT_WINDOW
            or self.after.journey is not ScreenJourney.LOOK_AT_WINDOW
            or before.target_id != target
            or after.target_id != target
            or before.device_id.casefold() != self.action.host_id.casefold()
            or after.device_id.casefold() != self.action.host_id.casefold()
            or before.principal_id != after.principal_id
            or before.audience_id != after.audience_id
            or before.principal_id != "person:sparks"
            or before.audience_id != "local:text"
            or before.permit_id == after.permit_id
        ):
            raise PermissionError(
                "pre/post screenshots must have distinct owner permits for the exact same original target"
            )


@dataclass(frozen=True, slots=True)
class ScreenActionObservation:
    status: str
    before_digest: str
    after_digest: str | None
    input_submitted: bool
    desired_effect_verified: bool
    reason: str

    def __post_init__(self) -> None:
        if self.status not in {
            "submitted_no_visible_change", "submitted_visual_change_unattributed",
            "uncertain_after_submission", "uncertain_during_submission",
        } or self.desired_effect_verified:
            raise ValueError("pixel comparisons cannot certify desired GUI outcomes")


class ScreenActionWorkflow:
    """Sequential owner-approved real OS capture / one input / new capture."""

    def __init__(self, *, capture_service: ScreenCaptureService,
                 input_service: DesktopInputService) -> None:
        if not isinstance(capture_service, ScreenCaptureService):
            raise TypeError("production capture service required")
        if not isinstance(input_service, DesktopInputService):
            raise TypeError("production SAFE-gated input service required")
        self.capture_service = capture_service
        self.input_service = input_service

    def perform(
        self, review: ReviewedScreenAction, *,
        before_capture_approval_id: str,
        exact_input_approval_id: str,
        after_capture_approval_id: str,
    ) -> ScreenActionObservation:
        if not isinstance(review, ReviewedScreenAction):
            raise TypeError("exact owner-reviewed action required")
        tokens = (before_capture_approval_id, exact_input_approval_id,
                  after_capture_approval_id)
        if (any(not isinstance(x, str) or not x.strip() for x in tokens)
            or len(set(tokens)) != 3):
            raise PermissionError("three unique one-use owner approvals required")
        # No input happens at all if owner picker, permission, privacy or STOP
        # refuses the initial independently observed real window.
        before = self.capture_service.capture_once(
            review.before, approval_id=before_capture_approval_id,
        )
        digest = before.evidence.receipt.digest_sha256
        try:
            result = self.input_service.execute(
                review.action, approval_id=exact_input_approval_id,
            )
        except (OSError, RuntimeError, PermissionError) as exc:
            # Win32/ydotool may have partially submitted input. Do not infer
            # failure means no effect, and never issue a hidden retry.
            return ScreenActionObservation(
                status="uncertain_during_submission",
                before_digest=digest, after_digest=None,
                input_submitted=False, desired_effect_verified=False,
                reason="input result uncertain; operator review before any replay",
            )
        if result.get("status") != "os_input_submitted" or result.get("effect_verified") is not False:
            raise PermissionError("untrusted or prematurely certified input receipt")
        try:
            after = self.capture_service.capture_once(
                review.after, approval_id=after_capture_approval_id,
            )
        except (OSError, RuntimeError, PermissionError):
            return ScreenActionObservation(
                status="uncertain_after_submission",
                before_digest=digest, after_digest=None,
                input_submitted=True, desired_effect_verified=False,
                reason="a verified post-action observation is unavailable",
            )
        post = after.evidence.receipt.digest_sha256
        if post == digest:
            status = "submitted_no_visible_change"
            reason = "image unchanged; operation's effect remains unverified"
        else:
            status = "submitted_visual_change_unattributed"
            reason = "image changed; cannot attribute desired effect without independent semantic check"
        return ScreenActionObservation(
            status=status, before_digest=digest, after_digest=post,
            input_submitted=True, desired_effect_verified=False,
            reason=reason,
        )


    def perform_staged(
        self, review: ReviewedScreenAction, *,
        approve_capture, approve_input,
    ) -> ScreenActionObservation:
        """Authorize separately at each effect boundary, never in advance.

        FIDO2 challenges expire quickly; getting three bearer approvals
        before the first capture is not reliable. This method invokes the
        independent owner WebAuthn ceremony immediately before each separate
        OS capture or exact input. A model callback cannot grant authority:
        each returned token is independently verified/consumed by SAFE.
        """
        if not isinstance(review, ReviewedScreenAction):
            raise TypeError("owner-reviewed exact action required")
        if not callable(approve_capture) or not callable(approve_input):
            raise TypeError("verified owner authorization callbacks required")
        before_token = approve_capture(review.before)
        if not isinstance(before_token, str) or not before_token:
            raise PermissionError("initial owner capture approval missing")
        before = self.capture_service.capture_once(
            review.before, approval_id=before_token,
        )
        digest = before.evidence.receipt.digest_sha256
        input_token = approve_input(review.action)
        if not isinstance(input_token, str) or input_token in {"", before_token}:
            raise PermissionError("new action-bound owner approval required")
        try:
            result = self.input_service.execute(
                review.action, approval_id=input_token,
            )
        except (OSError, RuntimeError, PermissionError, TimeoutError):
            return ScreenActionObservation(
                status="uncertain_during_submission",
                before_digest=digest, after_digest=None,
                input_submitted=False, desired_effect_verified=False,
                reason="input effect uncertain; operator review required before any replay",
            )
        if result.get("status") != "os_input_submitted" or result.get("effect_verified") is not False:
            raise PermissionError("untrusted input receipt claimed effect verification")
        try:
            after_token = approve_capture(review.after)
            if (not isinstance(after_token, str) or
                after_token in {"", before_token, input_token}):
                raise PermissionError("new post-action screenshot approval required")
            after = self.capture_service.capture_once(
                review.after, approval_id=after_token,
            )
        except (OSError, RuntimeError, PermissionError, TimeoutError):
            return ScreenActionObservation(
                status="uncertain_after_submission",
                before_digest=digest, after_digest=None,
                input_submitted=True, desired_effect_verified=False,
                reason="post-action owner capture or visual evidence unavailable",
            )
        post = after.evidence.receipt.digest_sha256
        changed = post != digest
        return ScreenActionObservation(
            status=("submitted_visual_change_unattributed" if changed
                    else "submitted_no_visible_change"),
            before_digest=digest, after_digest=post,
            input_submitted=True, desired_effect_verified=False,
            reason=("image changed but desired app effect unverified" if changed
                    else "image unchanged; desired app effect unverified"),
        )
