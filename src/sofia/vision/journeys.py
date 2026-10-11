"""Four explicit privacy/authority journeys for a real OS-picked screen target.

The owner-visible journey is NOT the OS picker or a frame. A platform capture
adapter must return genuine bytes from the exact chosen window. This module
cannot open windows, read pixels, navigate UI, execute clicks or watch ambient
screens without independent interactive OS permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from enum import Enum
from hashlib import sha256
from contextlib import closing
from pathlib import Path
from uuid import uuid4
import json

from sofia.vision.consent import (
    ScreenObservationPermit,ScreenObservationReceipt,
    propose_screen_permit,receipt_from_permitted_bytes,
)
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

class ScreenJourney(str,Enum):
    LOOK_AT_WINDOW="look_at_approved_window"
    SHOW_CHANGES="show_me_what_changed"
    WATCH_ONE_APP="watch_one_app_briefly"
    NAVIGATE_GUIDANCE="help_me_navigate"

@dataclass(frozen=True,slots=True)
class ScreenJourneyPolicy:
    journey:ScreenJourney
    snapshot_only:bool
    max_seconds:int
    permits_interactive_watching:bool
    permits_mouse_keyboard:bool=False
    permits_background_capture:bool=False
    permits_unselected_windows:bool=False
    permits_private_history_in_memory:bool=False

_POLICIES={
    ScreenJourney.LOOK_AT_WINDOW:ScreenJourneyPolicy(
        ScreenJourney.LOOK_AT_WINDOW,True,30,False,
    ),
    ScreenJourney.SHOW_CHANGES:ScreenJourneyPolicy(
        ScreenJourney.SHOW_CHANGES,True,45,False,
    ),
    ScreenJourney.WATCH_ONE_APP:ScreenJourneyPolicy(
        ScreenJourney.WATCH_ONE_APP,False,180,True,
    ),
    ScreenJourney.NAVIGATE_GUIDANCE:ScreenJourneyPolicy(
        ScreenJourney.NAVIGATE_GUIDANCE,True,30,False,
    ),
}

def journey_policy(journey:ScreenJourney)->ScreenJourneyPolicy:
    if not isinstance(journey,ScreenJourney):
        raise TypeError("typed screen journey required")
    return _POLICIES[journey]


@dataclass(frozen=True,slots=True)
class ScreenJourneyRequest:
    journey:ScreenJourney
    permit:ScreenObservationPermit
    requested_by_owner_ui:bool
    os_picker_confirmed:bool=False
    actual_capture_available:bool=False

    def __post_init__(self):
        if not isinstance(self.journey,ScreenJourney) or not isinstance(
            self.permit,ScreenObservationPermit,
        ):
            raise TypeError("scoped typed screen journey required")
        if not self.requested_by_owner_ui or self.os_picker_confirmed:
            raise PermissionError(
                "user journey request cannot claim OS picker permission"
            )
        if self.actual_capture_available:
            raise PermissionError("proposing capture does not mean pixels exist")


def propose_owner_screen_journey(
    *,journey:ScreenJourney,principal_id:str,audience_id:str,
    device_id:str,target_id:str,purpose:str,at:datetime,
)->ScreenJourneyRequest:
    policy=journey_policy(journey)
    permit=propose_screen_permit(
        principal_id=principal_id,audience_id=audience_id,
        device_id=device_id,target_id=target_id,purpose=purpose,
        kind="snapshot" if policy.snapshot_only else "bounded_follow",
        at=at,duration_seconds=policy.max_seconds,
    )
    return ScreenJourneyRequest(
        journey=journey,permit=permit,requested_by_owner_ui=True,
    )


@dataclass(frozen=True,slots=True)
class ScreenFrameEvidence:
    journey:ScreenJourney
    receipt:ScreenObservationReceipt
    audience_id:str
    device_id:str
    observed_at:datetime
    observation_source:str="os_interactive_picker_genuine_frame"
    semantic_content_verified:bool=False
    authorized_action:bool=False
    pixel_content_persisted:bool=False

    def __post_init__(self):
        if (
            self.observation_source!="os_interactive_picker_genuine_frame"
            or not self.receipt.actual_frame_available
            or self.semantic_content_verified or self.authorized_action
            or self.pixel_content_persisted
        ):
            raise PermissionError("a frame hash cannot imply scene semantics/actions")


def accept_actual_picked_frame(
    request:ScreenJourneyRequest,*,pixel_bytes:bytes,at:datetime,
    actual_os_picker_selected_target_id:str,
    confirmed_interactive_os_picker:bool,
    protected_surface:bool=False,
)->ScreenFrameEvidence:
    """Only host UI and capture backend may provide verified picker facts."""
    if not isinstance(request,ScreenJourneyRequest):
        raise TypeError("original owner journey request required")
    if (
        not confirmed_interactive_os_picker
        or actual_os_picker_selected_target_id!=request.permit.target_id
    ):
        raise PermissionError("real OS picker target/consent not observed")
    receipt=receipt_from_permitted_bytes(
        request.permit,frame=pixel_bytes,at=at,
        os_picker_consented=True,protected_surface=protected_surface,
    )
    return ScreenFrameEvidence(
        journey=request.journey,receipt=receipt,
        audience_id=request.permit.audience_id,
        device_id=request.permit.device_id,
        observed_at=at,
    )


@dataclass(frozen=True,slots=True)
class ScreenChangedReceipt:
    first_receipt_id:str
    second_receipt_id:str
    same_selected_window:bool
    pixel_digest_changed:bool
    semantic_change_observed:bool=False
    authorized_action:bool=False


def compare_two_approved_observations(
    first:ScreenFrameEvidence,second:ScreenFrameEvidence,
)->ScreenChangedReceipt:
    """Pixel SHA-256 comparison is not proof of meaningful visual change."""
    if not all(isinstance(x,ScreenFrameEvidence) for x in (first,second)):
        raise TypeError("two real receipt-backed frames required")
    if (
        first.journey!=ScreenJourney.SHOW_CHANGES
        or second.journey!=ScreenJourney.SHOW_CHANGES
        or first.audience_id!=second.audience_id
        or first.device_id!=second.device_id
        or first.receipt.target_id!=second.receipt.target_id
        or second.observed_at<=first.observed_at
    ):
        raise PermissionError("screen diffs require same approved target and audience")
    return ScreenChangedReceipt(
        first_receipt_id=first.receipt.permit_id,
        second_receipt_id=second.receipt.permit_id,
        same_selected_window=True,
        pixel_digest_changed=(
            first.receipt.digest_sha256!=second.receipt.digest_sha256
        ),
    )


class ScreenJourneyReceiptStore:
    """Bounded canonical digest receipts only, never the actual pixels."""
    def __init__(self,state_path:Path|str):
        self._guard=CanonicalSQLiteGuard(Path(state_path))
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS vision_observed_frame("
                "permit_id TEXT PRIMARY KEY,journey TEXT NOT NULL,"
                "audience_id TEXT NOT NULL,device_id TEXT NOT NULL,"
                "target_hash TEXT NOT NULL,digest_sha256 TEXT NOT NULL,"
                "observed_at TEXT NOT NULL,has_pixels INTEGER NOT NULL DEFAULT 0)"
            )
    def record(self,evidence:ScreenFrameEvidence)->None:
        if not isinstance(evidence,ScreenFrameEvidence):
            raise TypeError("real approved frame receipt required")
        target_hash=sha256(evidence.receipt.target_id.encode()).hexdigest()
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute(
                "SELECT digest_sha256 FROM vision_observed_frame WHERE permit_id=?",
                (evidence.receipt.permit_id,),
            ).fetchone()
            if existing is not None:
                if existing[0]!=evidence.receipt.digest_sha256:
                    raise PermissionError("observation evidence cannot be rewritten")
                return
            db.execute(
                "INSERT INTO vision_observed_frame VALUES(?,?,?,?,?,?,?,0)",
                (evidence.receipt.permit_id,evidence.journey.value,
                 evidence.audience_id,evidence.device_id,
                 target_hash,evidence.receipt.digest_sha256,
                 evidence.observed_at.astimezone(timezone.utc).isoformat()),
            )
            db.execute(
                "DELETE FROM vision_observed_frame WHERE permit_id NOT IN "
                "(SELECT permit_id FROM vision_observed_frame "
                "ORDER BY observed_at DESC LIMIT 256)"
            )
    def status(self,*,audience_id:str)->dict:
        with closing(self._guard.connect(timeout=10)) as db:
            rows=db.execute(
                "SELECT journey,observed_at FROM vision_observed_frame "
                "WHERE audience_id=? ORDER BY observed_at DESC LIMIT 12",
                (audience_id,),
            ).fetchall()
        return {
            "observations":tuple({
                "journey":kind,"observed_at":when,"actual_frame_receipt":True,
            } for kind,when in rows),
            "pixel_storage":False,
            "raw_screens_as_memory":False,
            "screen_control_authorized":False,
            "semantic_changes_proven":False,
        }
