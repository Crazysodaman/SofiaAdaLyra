"""Real public PNG asset composition in the optional Tk layered2D frontend.

Uses a tiny fake Tk canvas/PhotoImage because GitHub CI need not have an
interactive display server. Real-host pixels are a separate VERIFY gate.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import types

from sofia.avatar.presentation import AudienceScope
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.vtuber_starter_art import generate_public_outfit_art
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.core.embodiment.store import EmbodimentStore
from sofia.ui.avatar_renderer import AvatarRenderRequest
from sofia.ui.avatar2d_renderer import TkLayered2DRenderer


SEED=Path(__file__).resolve().parents[1]/"src/sofia/core.embodiment/avatar.json"


class Root:
    def __init__(self):
        self.pending={}
        self.nextid=0
    def after(self,delay,callback):
        self.nextid+=1
        self.pending[self.nextid]=callback
        return self.nextid
    def after_cancel(self,token):
        self.pending.pop(token,None)
    def run(self):
        for token,callback in tuple(self.pending.items()):
            self.pending.pop(token,None)
            callback()


class Canvas:
    def __init__(self):
        self.painted=[]
        self.deleted=[]
    def delete(self,tag):
        self.deleted.append(tag)
        self.painted.clear()
    def winfo_width(self):
        return 320
    def winfo_viewable(self):
        return True
    def create_image(self,x,y,**kwargs):
        assert "avatar2d" in kwargs["tags"]
        self.painted.append((x,y,kwargs["image"]))
        return len(self.painted)


class FakePhotoImage:
    def __init__(self,*,data,format):
        assert format=="png"
        assert isinstance(data,str) and data
    def subsample(self,x,y):
        assert (x,y)==(2,2)
        return self


class Symbolic:
    backend_name="tk-canvas-avatar-v1"
    def __init__(self):
        self.calls=[]
    def stop(self):
        return None
    def render(self,request,*,completed):
        self.calls.append("fallback_render")
        completed(request.decision.decision_id,True,"symbolic Tk frames")
    def render_idle(self,presentation):
        self.calls.append("fallback_idle")


def env(tmp_path):
    art_root=tmp_path/"art"
    catalog=build_starter_wardrobe()
    generate_public_outfit_art(
        catalog,outfit_id="day.default",
        destination=art_root/"outfits"/"day.default",
    )
    bundle=load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=tmp_path/"sofia.db",
    )
    projection=bundle.authority.projection(AudienceScope.PUBLIC)
    return art_root,projection,tmp_path/"sofia.db"


def test_layered_renderer_composites_real_verified_layers_and_receipts(
    tmp_path,monkeypatch,
):
    monkeypatch.setitem(sys.modules,"tkinter",types.SimpleNamespace(
        PhotoImage=FakePhotoImage,
    ))
    art_root,projection,state=env(tmp_path)
    root=Root()
    canvas=Canvas()
    fallback=Symbolic()
    renderer=TkLayered2DRenderer(
        root=root,canvas=canvas,public_root=art_root,
        state_path=state,fallback=fallback,
    )
    events=[]
    renderer.render(
        AvatarRenderRequest(SimpleNamespace(decision_id="d.1"),projection),
        completed=lambda *event: events.append(event),
    )
    assert len(canvas.painted)>=5
    assert events==[]
    root.run()
    assert len(events)==1
    assert events[0][0]=="d.1" and events[0][1] is True
    assert "verified public PNG" in events[0][2]
    assert fallback.calls==[]
    assert renderer.backend_name.startswith("tk-layered2d")


def test_no_private_asset_resolved_on_missing_public_art(tmp_path,monkeypatch):
    monkeypatch.setitem(sys.modules,"tkinter",types.SimpleNamespace(
        PhotoImage=FakePhotoImage,
    ))
    art_root,projection,state=env(tmp_path)
    (art_root/"outfits"/"day.default"/"manifest.json").unlink()
    fallback=Symbolic()
    renderer=TkLayered2DRenderer(
        root=Root(),canvas=Canvas(),public_root=art_root,
        state_path=state,fallback=fallback,
    )
    events=[]
    renderer.render(
        AvatarRenderRequest(SimpleNamespace(decision_id="d.2"),projection),
        completed=lambda *event: events.append(event),
    )
    assert fallback.calls==["fallback_render"]
    assert events[0][2]=="symbolic Tk frames"


def test_public_renderer_never_draws_nude_projection(tmp_path,monkeypatch):
    from dataclasses import replace
    from sofia.avatar.presentation import AttireMode

    monkeypatch.setitem(sys.modules,"tkinter",types.SimpleNamespace(
        PhotoImage=FakePhotoImage,
    ))
    art_root,projection,state=env(tmp_path)
    fallback=Symbolic()
    canvas=Canvas()
    renderer=TkLayered2DRenderer(
        root=Root(),canvas=canvas,public_root=art_root,
        state_path=state,fallback=fallback,
    )
    denied=replace(projection,audience=AudienceScope.PRIVATE,
                   attire=AttireMode.NUDE,private_fallback_used=False)
    renderer.render_idle(denied)
    assert not canvas.painted
    assert fallback.calls==[]  # no unsafe private symbolic output
    receipts=[]
    renderer.render(
        AvatarRenderRequest(SimpleNamespace(decision_id="private.1"),denied),
        completed=lambda *values: receipts.append(values),
    )
    assert receipts[0][1] is False
    assert fallback.calls==[]


def test_cancel_pending_layered_frame_reports_no_success(tmp_path,monkeypatch):
    monkeypatch.setitem(sys.modules,"tkinter",types.SimpleNamespace(
        PhotoImage=FakePhotoImage,
    ))
    art_root,projection,state=env(tmp_path)
    root=Root()
    renderer=TkLayered2DRenderer(
        root=root,canvas=Canvas(),public_root=art_root,
        state_path=state,fallback=Symbolic(),
    )
    events=[]
    renderer.render(
        AvatarRenderRequest(SimpleNamespace(decision_id="d.3"),projection),
        completed=lambda *event: events.append(event),
    )
    assert renderer.stop()=="d.3"
    root.run()
    assert events==[]
