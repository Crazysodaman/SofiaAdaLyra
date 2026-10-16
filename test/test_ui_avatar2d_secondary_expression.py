"""2D puppet honors settled independent facial, eye, ear and tail channels.

Only real checked PNG layers are counted. These are headless canvas tests,
not a claim of 3D integration or supervised Venus visual acceptance.
"""
from dataclasses import replace
from types import SimpleNamespace

from sofia.application.expression_runtime import AvatarExpressionState
from sofia.avatar.vtuber_character_bundle import load_selected_character_sprites
from sofia.avatar.vtuber_character_selection import select_character_parts
from sofia.ui.avatar2d_renderer import _avatar_channel_cues, _character_expression
from sofia.ui.avatar_renderer import AvatarRenderRequest
from test.test_ui_avatar2d_modular import configured


def _request(projection, *, gesture, state, revision=None):
    return AvatarRenderRequest(
        SimpleNamespace(
            decision_id="avatar.combined.1",
            gesture=gesture,
            emotion_labels=("focused",),
            avatar_state=state,
            presentation_revision=(
                projection.source_revision if revision is None else revision
            ),
        ),
        projection,
    )


def _part_digest(public_root, projection, group, **choices):
    chosen=select_character_parts(projection, **choices)
    return next(
        sprite.digest for sprite in load_selected_character_sprites(
            public_root / "character", chosen,
        ) if sprite.group==group
    )


def test_secondary_ears_tail_face_and_gaze_are_actually_painted_together(
    tmp_path, monkeypatch,
):
    renderer, root, canvas, fallback, art, projection = configured(
        tmp_path, monkeypatch,
    )
    avatar=AvatarExpressionState(
        face="smile", gaze="avert-gaze", ears="ear-flick",
        tail="tail-flick", gesture="smile", pose="stand-relaxed",
    )
    request=_request(projection, gesture="smile", state=avatar)
    assert _character_expression(request.decision)=="smile"
    assert _avatar_channel_cues(request.decision)==(
        "ear-flick","tail-flick","left",
    )
    receipts=[]
    renderer.render(request,completed=lambda *event:receipts.append(event))
    start=canvas.final_frame()
    assert _part_digest(
        art, projection,"eye_left",gesture="smile",expression="smile",
        gaze="left",ear_cue="ear-perk",
    ) in start
    assert _part_digest(
        art, projection,"mouth",gesture="smile",expression="smile",
    ) in start
    assert receipts==[]
    root.run()
    active=canvas.final_frame()
    assert active!=start
    assert _part_digest(
        art,projection,"ear_left",gesture="smile",expression="smile",
        ear_cue="ear-relax",tail_cue="tail-flick",gaze="left",
    ) in active
    assert _part_digest(
        art,projection,"tail",gesture="smile",expression="smile",
        ear_cue="ear-relax",tail_cue="tail-flick",gaze="left",
    ) in active
    assert receipts==[]
    root.run()
    end=canvas.final_frame()
    assert end==start  # back to the authored base/raised-ear frame
    root.run()
    assert receipts and receipts[0][1] is True
    assert "3 2D frame(s)" in receipts[0][2]
    assert fallback.calls==[]


def test_primary_ear_flick_uses_real_relaxed_png_not_unavailable_flatten(
    tmp_path, monkeypatch,
):
    renderer,root,canvas,fallback,art,projection=configured(tmp_path,monkeypatch)
    request=AvatarRenderRequest(
        SimpleNamespace(
            decision_id="ear.only",gesture="ear-flick",emotion_labels=(),
            presentation_revision=projection.source_revision,
        ),projection,
    )
    receipts=[]
    renderer.render(request,completed=lambda *v:receipts.append(v))
    root.run()
    assert _part_digest(
        art,projection,"ear_left",gesture="ear-relax",
    ) in canvas.final_frame()
    root.run()
    root.run()
    assert receipts and receipts[0][1] is True
    assert fallback.calls==[]


def test_stale_expression_revision_cannot_paint_or_claim_success(
    tmp_path, monkeypatch,
):
    renderer,root,canvas,fallback,art,projection=configured(tmp_path,monkeypatch)
    current=tuple(canvas.final_frame())
    request=_request(
        projection,gesture="tail-flick",
        state=AvatarExpressionState(
            face=None,gaze=None,ears=None,tail="tail-flick",
            gesture="tail-flick",pose=None,
        ),
        revision=projection.source_revision+1,
    )
    results=[]
    renderer.render(request,completed=lambda *event:results.append(event))
    assert results and results[0][1] is False
    assert "stale" in results[0][2]
    assert canvas.final_frame()==current
    assert fallback.calls==[]
    assert root.pending=={}
