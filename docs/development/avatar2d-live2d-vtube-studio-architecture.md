# Sofía 2D: Live2D Cubism + VTube Studio architecture (owner-selected)

**Decision: 2026-10-18. Branch: main. Status: design chosen; adapter scaffold coded; no Live2D model has been rigged, loaded, or accepted on Venus.**

## Selected stack

- **Art master:** editable, organized, layered PSD (RGB, 8-bit/channel, sRGB). Keep a separate editable authoring document and build a clean Cubism import PSD. Adobe Photoshop and CLIP STUDIO PAINT PSDs are the formats confirmed in Live2D documentation; Krita exports require a real compatibility check, not an assumption.
- **Rig and export:** Live2D Cubism Editor. Full skull/neck/body/fox-ear/tail parent-child deformers, artmeshes, face-angle parameters, calibrated mouth/eye shapes, hair and tail physics. Preserve `.cmo3`/source PSD; export `.moc3`, `.model3.json`, atlas textures, and `.physics3.json`. Validate target Cubism SDK compatibility with current VTube Studio.
- **Display engine:** VTube Studio on Windows Venus. It owns the rendered animated model and VTube Studio's model settings. Sofía does **not** try to render `.moc3` in Tk or copy source sprites into `Public-V2`.
- **Control plane:** Sofía Python runtime, the ONLY authority for emotions, expression events, owner permissions, current wardrobe IDs, approved presentation and voice-playback facts.
- **Adapter:** `src/sofia/avatar/vtube_studio_bridge.py`, owner-opt-in WebSocket to **127.0.0.1** only (configurable local port, default 8001). Authentication uses the explicit VTube Studio approval popup and locally DPAPI-encrypted token. No API connection occurs on import or startup. Model/parameter/hotkey actions are separately gated. Existing Python/Tk public renderer remains the tested fallback.
- **External app boundary:** VTube Studio is a different application/window from the existing desktop UI. A movable desktop overlay and any window embedding, placement, screen capture or gaming policy require separate design and host verification; do not claim VTube Studio can be silently embedded into Tk.

## Trust and control

1. In VTube Studio, owner manually enables **Allow Plugin API access**; `--status` may read availability without authentication.
2. Owner explicitly runs `--pair` once and clicks **Allow** on the VTube Studio popup. The resulting per-plugin token is DPAPI-encrypted in their Windows user profile under:
   `%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\VTubeStudio\vts_token.dpapi`.
   Never print it, commit it, copy it between hosts or bypass permission. VTube Studio can revoke the plugin from its settings; Windows reinstallation requires re-pairing.
3. Client may read model identity and advertised input parameters after authentication. Until a reviewed rig and parameter map exist, it must **not** send movement, lip-sync or garment hotkeys.
4. Inject only a reviewed owner-allowlisted parameter that exists in the current VTS parameter list, using `InjectParameterDataRequest`. VTS states that values must be refreshed **at least once per second** while control is desired. A future bounded scheduler must be cancelable and stop on gaming, disconnect, consent/revision changes, stale speech, application stop, or model change.
5. Distinguish VTS tracking INPUT names (example: `FaceAngleX`) from Live2D Cubism model PARAMETERS (example conventional `ParamAngleX`). They need verified mappings configured in VTube Studio. Do **not** assume sending a Cubism ID directly to `InjectParameterDataRequest` controls the model.
6. Trigger expression/hair/outfit hotkeys ONLY after exact model hotkey IDs and wardrobe-to-hotkey mappings have been reviewed and allowlisted. Don't infer from an imported PNG filename or an LLM proposal.
7. Keep one canonical Sofía presentation writer. No API or renderer is allowed to authorize nude/private presentation or disclose protected art. VTube Studio is a potentially screen-recorded/streamed external process; **initial model MUST be public-safe and covered**. A later private presentation requires a separately designed authenticated display boundary, not a VTS hotkey.

## Live2D asset master: topology to lock before generating new art

**One coordinated master, not dissimilar separately generated head images.**

```text
Character
  Background/TailRoot: rear 7-pose tail meshes with pelvis attachment
  BodyRoot
    Torso/shoulders with covered base garment
    NeckUnderlay: painted through all expected head poses, no exposed hole
    Collar / shirt / jacket meshes, wardrobe attachments
    HeadRoot: all face/hair/ears follow head pivot
      BackHairRoot: large crown + back body/hair strands, no gap at scalp
      FoxEarLeftRoot, FoxEarRightRoot: NO human ears on skull
      FaceBase: single head/neck outline, no duplicate bust silhouette
      Nose/cheek/chin shading: true separated artist paint
      EyeLeftRoot: sclera, iris, upper/lower lids, lashes, highlights
      EyeRightRoot: same independent parts
      BrowLeft, BrowRight: C/soft neutral style, separately deformable
      MouthRoot: consistent center/width/vertical anchor
        upper/lower lip, inside, tongue, teeth, A/E/I/O/U/M states
      BangsRoot: forehead framing, highlights, deformable front tips
      LeftSideLock/RightSideLock: swaying distinct from back hair
      Head-attached accessories
```

**Do not erase the original canonical full-body PNG**. Create a separately exported neck/body underlay and a detached head from the editable master; paint hidden neck/scalp/face pixels that become visible when rotated. Test +/- 12 degree head tilt, small nod and -30..+30 degree face angle deformation (angles are initial *design targets*, not demonstrated or supported animation yet), then inspect edge seams at extremes. Ear pivots follow skull but have independent deformation.

**Hair:** review approximately 8% added visual crown volume. This is a proposed art change, NOT a universal image scale; keep shared anchors for six alternate styles. Finish skin/nose/cheeks and **consistent mouth proportions/anchor** first.

**Mouth:** Use shared neutral-lip width and center; mouth-open varies HEIGHT and interior content. Approve extremes for A/E/O/M and round intermediate frames without mouth width jumping or duplicate contours. Actual animation from audio must come from verified playback events with bounded frame delivery. VTube Studio mic/voice settings are independent of Sofía's output and should not be silently assumed to reflect her speech.

**Cubism import:** each moving painted part needs enough extra covered/hidden texture to survive mesh deformation. Merge line/fill into the final *import* part where the Cubism PSD guide requires it; keep separate edit layers in the art master. Watch for line-edge color bleeding, layer masks and unsupported PSD blending. The Cubism export must include physics registered with the model.

## Wardrobe planning, before manufacturing hundreds of items

Original wardrobe IDs, visual garment descriptions, public/private classifications, and slot matrix remain authoritative. VTS can toggle pre-rigged expression/item/hotkeys; it cannot magically take Sofía's 295 old standalone unfitted PNGs as 295 automatically rigged garments. For V1, rig ONE approved public default outfit as part of the model. Next, implement a reviewed model-asset or hotkey mapping for a **small capsule wardrobe** with matching mesh + physics per garment. Refuse unsupported or stale outfit IDs; keep the current Tk public fallback until coverage and presentation rules are proven. Plan alternative hairstyles and seasonal sets as model variations that must retain head/neck anchors.

## Engineering milestones and evidence

| Milestone | What constitutes proof | Status |
| --- | --- | --- |
| VTS API adapter | Local status, opt-in pairing, owner token encryption, response validation, fake-socket tests | Code on main, **Venus tests pending** |
| VTS connection smoke | In Venus VTube Studio API mode: `--status`, explicit `--pair`, `--model` | **Not performed** |
| Live2D art topology | Reviewed PSD with real hidden skin, mouth/lip parts, independent eyes/brows, hair, ears, tail, covered body | **Not yet drawn** |
| Cubism model | Reproducible `.cmo3` source and supported `.moc3/.model3.json/.physics3.json` export | **Not created** |
| VTS visible puppet | Loaded model, tilt/turn, blinking, mouth, ear, tail and hair physics demonstrated on Venus | **Not verified** |
| Sofía-driven animation | Authenticated event-to-parameter mapping, no false voice receipts, pause/disconnect safe, actual displayed-frame evidence | **Not wired** |
| Wardrobe v1 | Owner-approved public garment changes follow deformations without tears and no private leaks | **Not verified** |
| Gaming runtime | Venus CPU/GPU memory/frame timings + idle/game model-unload tests + host-safe fallback | **Not measured** |

Existing 57 original PNGs plus Batches 09–13 remain approved/review **source material**, not Cubism `.moc3` or a VTube Studio rig. Never mark them production-compatible just because PNG file hashes or offline Tk tests pass.

## On Venus: first safe local API check

1. Install/start VTube Studio, open its settings, enable **Allow Plugin API access**. The actual port number is displayed there; default is 8001.
2. In existing Sofía repo PowerShell:

```powershell
git pull --ff-only
python -m pip install -e '.[vtube-studio]'
pytest -q test/test_avatar2d_vtube_studio_bridge.py
python -m sofia.avatar.vtube_studio_bridge --status
```

3. With VTS running and **only when ready to approve plugin access**, invoke `python -m sofia.avatar.vtube_studio_bridge --pair`, confirm the **Sofia Ada Lyra** popup within 90 seconds. Re-enrollment must be explicit (existing DPAPI credential causes refusal, not silent replacement).
4. Run `python -m sofia.avatar.vtube_studio_bridge --model` to inspect the currently loaded model; it may report `loaded: false` until a Live2D model is installed. No motion is sent by these three CLI modes.

If VTS shows a different local API port, pass `--port <port>` to each command. Don't make the API publicly reachable or forward it over Cloudflare; it's for the local Windows host only.

## Primary sources (official)

- API specification and consent: https://github.com/DenchiSoft/VTubeStudio/blob/master/README.md
- Plugin permissions / default local API port: https://github.com/DenchiSoft/VTubeStudio/wiki/Plugins
- VTube Studio loading .moc3 models: https://github.com/DenchiSoft/VTubeStudio/wiki/Loading-your-own-Models
- Cubism PSD import requirements: https://docs.live2d.com/en/cubism-editor-manual/psd-import/
- Cubism PSD caveats (8-bit RGB, sRGB, blend/masks): https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/
- Cubism export / physics: https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/
- VTube Studio terms: https://store.steampowered.com/eula/1325860_eula_0
