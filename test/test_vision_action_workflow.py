"""Three independently owner-approved steps; never actuates a real desktop."""
from datetime import datetime, timezone
import socket

import pytest

from sofia.vision.action_workflow import (
    ReviewedScreenAction, ScreenActionWorkflow,
)
from sofia.vision.capture import CapturedFrame, ScreenCaptureService, local_target_id
from sofia.vision.desktop_control import DesktopAction, DesktopInputService
from sofia.vision.journeys import (
    ScreenJourney, accept_actual_picked_frame, propose_owner_screen_journey,
)
from sofia.vision.windows_capture import _png_from_bgra


def prepared():
    host = socket.gethostname()
    action = DesktopAction(
        host_id=host, window_handle=42, process_id=55,
        operation="key_press", key="tab",
    )
    target = local_target_id(host, 42, 55)
    kwargs = dict(
        journey=ScreenJourney.LOOK_AT_WINDOW,
        principal_id="person:sparks", audience_id="local:text",
        device_id=host, target_id=target, purpose="Owner reviewed GUI action",
        at=datetime.now(timezone.utc),
    )
    before = propose_owner_screen_journey(**kwargs)
    after = propose_owner_screen_journey(**kwargs)
    assert before.permit.permit_id != after.permit.permit_id
    return ReviewedScreenAction(action, before, after)


class CaptureStub(ScreenCaptureService):
    def __init__(self, *, fail_step=0, unchanged=False):
        self.calls = []
        self.fail_step = fail_step
        self.unchanged = unchanged

    def capture_once(self, request, *, approval_id):
        self.calls.append((request, approval_id))
        if len(self.calls) == self.fail_step:
            raise PermissionError("owner revoked capture")
        pixel = bytes((1, 2, 3, 255)) if (
            len(self.calls) == 1 or self.unchanged
        ) else bytes((4, 5, 6, 255))
        png = _png_from_bgra(pixel, 1, 1)
        evidence = accept_actual_picked_frame(
            request, pixel_bytes=png, at=datetime.now(timezone.utc),
            actual_os_picker_selected_target_id=request.permit.target_id,
            confirmed_interactive_os_picker=True,
        )
        return CapturedFrame(png, evidence)


class InputStub(DesktopInputService):
    def __init__(self, *, failing=False, lying=False):
        self.calls = []
        self.failing = failing
        self.lying = lying

    def execute(self, action, *, approval_id):
        self.calls.append((action, approval_id))
        if self.failing:
            raise OSError("injection partially uncertain")
        return {
            "status": "os_input_submitted",
            "effect_verified": self.lying,
        }


def approvals():
    return dict(
        before_capture_approval_id="fido-before",
        exact_input_approval_id="fido-action",
        after_capture_approval_id="fido-after",
    )


@pytest.mark.parametrize(("unchanged", "expected"), [
    (True, "submitted_no_visible_change"),
    (False, "submitted_visual_change_unattributed"),
])
def test_owner_capture_action_capture_never_claims_semantic_success(
    unchanged, expected,
):
    cap = CaptureStub(unchanged=unchanged)
    inp = InputStub()
    result = ScreenActionWorkflow(
        capture_service=cap, input_service=inp
    ).perform(prepared(), **approvals())
    assert result.status == expected
    assert not result.desired_effect_verified
    assert result.after_digest is not None
    assert result.input_submitted
    assert [id for _, id in cap.calls] == ["fido-before", "fido-after"]
    assert inp.calls[0][1] == "fido-action"


def test_pre_capture_stop_prevents_any_keyboard_or_mouse_submission():
    cap, inp = CaptureStub(fail_step=1), InputStub()
    with pytest.raises(PermissionError):
        ScreenActionWorkflow(
            capture_service=cap, input_service=inp
        ).perform(prepared(), **approvals())
    assert inp.calls == []


def test_post_capture_revocation_is_uncertain_not_automatic_replay():
    cap, inp = CaptureStub(fail_step=2), InputStub()
    result = ScreenActionWorkflow(
        capture_service=cap, input_service=inp
    ).perform(prepared(), **approvals())
    assert result.status == "uncertain_after_submission"
    assert result.input_submitted
    assert result.after_digest is None
    assert len(inp.calls) == 1


def test_partial_input_failure_never_claims_rejection_or_retries():
    cap, inp = CaptureStub(), InputStub(failing=True)
    result = ScreenActionWorkflow(
        capture_service=cap, input_service=inp
    ).perform(prepared(), **approvals())
    assert result.status == "uncertain_during_submission"
    assert not result.desired_effect_verified
    assert len(inp.calls) == 1
    assert len(cap.calls) == 1


def test_reject_same_approval_reused_across_capture_input_and_postcapture():
    cap, inp = CaptureStub(), InputStub()
    args = approvals()
    args["after_capture_approval_id"] = args["before_capture_approval_id"]
    with pytest.raises(PermissionError, match="three unique"):
        ScreenActionWorkflow(
            capture_service=cap, input_service=inp
        ).perform(prepared(), **args)
    assert cap.calls == [] and inp.calls == []


def test_wrong_reused_permit_or_host_is_rejected_before_effect():
    review = prepared()
    from dataclasses import replace
    with pytest.raises(PermissionError):
        ReviewedScreenAction(review.action, review.before, review.before)
    wrong = replace(
        review.action, host_id="different-host"
    )
    with pytest.raises(PermissionError):
        ReviewedScreenAction(wrong, review.before, review.after)


def test_untrusted_input_receipt_cannot_self_verify_its_effect():
    cap, inp = CaptureStub(), InputStub(lying=True)
    with pytest.raises(PermissionError, match="untrusted"):
        ScreenActionWorkflow(
            capture_service=cap, input_service=inp
        ).perform(prepared(), **approvals())
    assert len(cap.calls) == 1
