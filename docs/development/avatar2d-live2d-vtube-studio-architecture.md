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


## Automatic reconnection after explicit owner approval (2026-10-18)

VTube Studio's **official** API stores a reusable plugin permission token.
When VTS or the Sofía client reconnects, the plugin can use the **same**
token with `AuthenticationRequest`. No new
`AuthenticationTokenRequest` popup is necessary unless the owner
revokes or resets that approval.

**The VTS Plugins panel showing "connected" does not prove that our
Python client saved the token.** When the first request timed out, the
owner may have approved the popup after the Python caller exited.
Verify the DPAPI credential **without displaying the secret**:

```powershell
git pull --ff-only
python -m pytest -q test/test_avatar2d_vtube_studio_bridge.py
python -m sofia.avatar.vtube_studio_bridge --credential-status --port 9996
```

- `token_saved: true`: run the one-shot, no-popup auth test:
  `python -m sofia.avatar.vtube_studio_bridge --reconnect --port 9996`.
  This may report `model_loaded: false`, which is fine until Sofía's
  Cubism model exists.
- `token_saved: false`: with VTS running, rerun
  `python -m sofia.avatar.vtube_studio_bridge --pair --port 9996`
  once, approve the normal popup, and wait for the Python command to
  report `paired: true`. Never assume authorization was persisted
  just because the external VTS UI shows the plugin name.

The adapter also supports an **opt-in continuously reconnecting,
read-only owner-session watcher**:

```powershell
python -m sofia.avatar.vtube_studio_bridge --watch --port 9996 --interval 10
```

This process waits for VTS if it is not open, authenticates using the
stored DPAPI token as soon as it becomes available, and periodically
reads API status. On disconnect it retries with a 10-second delay.
It **never** requests a new token, opens an approval popup, starts VTube
Studio, activates a model, writes to sofia.db, injects a head angle,
enables tracking, or switches garments. Press Ctrl+C to stop it.
If authorization is revoked, it stops rather than pestering the owner
with repeated dialogs.

### Optional automatic launch after Windows sign-in

After the one-shot reconnect and focused tests pass on Venus, the owner
can use **Task Scheduler**, running in the *same interactive Windows
user session* that approved VTube Studio:

1. Task Scheduler → Create Task → General: e.g. `Sofía VTS Reconnect`;
   **Run only when user is logged on**, not SYSTEM/LocalService.
2. Trigger: **At log on** of the owner Windows account.
3. Action: `Start a program`; executable is the Python virtual
   environment's `pythonw.exe` in the local Sofía checkout (copy the
   confirmed path with `(Get-Command pythonw.exe).Source` while venv
   is active).
4. Arguments:
   `-m sofia.avatar.vtube_studio_bridge --watch --port 9996 --interval 10`.
   Set **Start in** to the Sofía checkout without quotes.
5. Settings: If already running, **do not start a new instance**.
   Do not enable highest privileges. Save and manually start the task
   once to confirm it connects after VTube Studio is launched.
6. Disable/delete the task to opt out; it is not necessary for the
   current Tk fallback or Sofía's cognition.

This logs into the VTube Studio API whenever the **already-open**
application is ready. It does **not** auto-launch VTube Studio. On this
Venus setup, the owner launches VTube Studio via the official
`start_without_steam.bat` to avoid Steam disconnecting a different PC
running a game. Any future VTube Studio autostart must deliberately use
that standalone launcher and remain an independent opt-in.

A future Sofía desktop startup controller can call
`watch_saved_connection` instead of the separate scheduled-task
watcher, with existing game/presentation and shutdown policies.
**Do not run both**: only one process should own the VTS connection.
Because Windows DPAPI is user-bound, the LocalService canonical
runtime cannot decrypt or impersonate an interactive user's saved token.

Official source: https://github.com/DenchiSoft/VTubeStudio/blob/master/README.md#authentication


## On-demand VTube Studio hosting (owner decision: 2026-10-18)

**Owner choice:** VTube Studio should **not** start at Windows login and should **not** remain open when Sofía doesn't need her avatar. Sofía may open and gracefully close only her **own** VTube Studio process. She may discover the app on any local drive, with a per-host override. Never rely on the Steam default C: location.

Code added on `main`:
- `src/sofia/avatar/vtube_studio_host.py`: portable Steam-library finder and explicit, owner-safe process lifecycle.
- `src/sofia/avatar/vtube_studio_demand.py`: verified covered-public-rig + owner enablement + activity/stop policy deciding when a host may launch or close the app.
- `test/test_avatar2d_vtube_studio_host.py`, `test/test_avatar2d_vtube_studio_demand.py`: unit tests with simulated Steam locations, PID ownership and policy.
- `pip install -e '.[vtube-studio]'` now includes `psutil` for process identity checking.

### Host selection and discovery

VTS can live on **C:, D:, E:, H:, or any other installed Steam library drive**. The finder reads:
- Steam's per-user registry installation directory;
- Steam `steamapps/libraryfolders.vdf` (modern `path` and legacy numeric layouts);
- common Steam/SteamLibrary directory layouts on mounted drives;
- optional explicit `--install-dir` and `SOFIA_VTS_INSTALL_DIR` environment override.

The finder requires the real `VTube Studio.exe` and `start_without_steam.bat` together in the directory. It does **not** recursively crawl every file on an entire disk, install software, read private files, or fetch executable content. An unusual portable location can be supplied explicitly:

```powershell
python -m sofia.avatar.vtube_studio_host --discover
python -m sofia.avatar.vtube_studio_host --discover --install-dir 'E:\SteamLibrary\steamapps\common\VTube Studio'
```

### Reversible, manual launch/close testing

Only from the Windows desktop user session, not LocalService:

```powershell
git pull --ff-only
python -m pip install -e '.[vtube-studio]'
python -m pytest -q test/test_avatar2d_vtube_studio_host.py test/test_avatar2d_vtube_studio_demand.py
python -m sofia.avatar.vtube_studio_host --discover
python -m sofia.avatar.vtube_studio_host --launch
```

- If VTS is **already running** in the user's desktop session, the command reports `reused_existing` and **never** marks it owned.
- Otherwise the tool calls the **official** `start_without_steam.bat` (avoiding the other computer's Steam game conflict) and watches for a verified, exact new VTube Studio process. Only one unambiguous new process in the validated directory is recorded. If recognition fails, it refuses the authority to close that process.
- To request app closure, run `python -m sofia.avatar.vtube_studio_host --close`. It sends Windows `WM_CLOSE` **only** when recorded process PID, creation timestamp, executable path, Windows session and hostname match the current process. It does not kill a manually opened instance and never force-kills a VTS process. It may report `no_app_window_found` or `graceful_close_requested`; if VTS displays a confirmation dialog, the user remains in control.
- Only non-secret process-identification metadata is stored in the current Windows profile under `%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\VTubeStudio\launched_instance.json`. This is separate from the DPAPI-protected authorization token.
- **DO NOT enable a Task Scheduler autostart of VTS or of the old always-on `--watch` command for this on-demand policy.** VTS runs only while requested. The read-only `--watch` remains a manual debugging aid.

### When Sofía is actually allowed to summon her avatar

A future interactive-host UI integration can call `handle_avatar_demand` after verifying **all** these facts from canonical runtime authority:
1. Owner has enabled VTS avatar mode for this Windows user and target host.
2. There is an active visible avatar surface/request.
3. A reviewed, covered PUBLIC Live2D rig is installed for that host.
4. The current public wardrobe/presentation is verified covered.
5. Host isn't in protected gaming/busy resource mode.
6. The owner hasn't stopped or hidden the avatar.

When conditions cease to hold, only an owned instance may be closed. A user-owned pre-existing instance remains untouched. The demand policy is **coded but not yet called by the production UI** because Sofía does not have an approved installed Live2D model; do not falsely mark automatic show/hide as active. Owner may test `--launch` and `--close` manually now.

### Multiple computers

This finder is **local to the machine running the code**. Sofía can find VTS on Venus, the alternate Windows GPU machine, or another PC **only if** its Sofía owner-session host agent/code runs there. It does not browse another PC's drives from Artemis, share files or create a remote desktop agent by itself. Remote lifecycle needs an already authenticated host broker with explicit user-session dispatch and separate audit/consent.

Each machine's VTube Studio installation and configured API port are independent (Venus currently reports **9996**). **DPAPI-protected plugin tokens cannot be copied or automatically transferred between Windows hosts/accounts.** Pair once with VTube Studio on each new host, with the user approving the popup locally. No silent enrollment.

### Remaining verification

Source and fake-process tests have been committed, but **the exact checkout/Windows host runtime tests still require Venus execution**. Validate the actual BAT launch behavior, process name/executable, user-session window control, and Windows Store/Steam Library installation layout. **No new images were generated, no model was fabricated, no service/startup policy was changed, and no production avatar was activated** by these commits.

Official VTS standalone launch: https://github.com/DenchiSoft/VTubeStudio/wiki/Starting-without-Steam


### 2026-10-18 Windows BAT working-directory fix

The first owner-hosted --launch on Venus exposed an uncaught real Windows
launcher defect despite 19 green simulated tests. Sofía ran in
`H:\Users\Crazysodaman\Programing\SofiaAdaLyra` and correctly located
VTube Studio at `E:\SteamLibrary\steamapps\common\VTube Studio`.
However, `os.startfile(full_batch_path)` passed only the BAT filename,
so ShellExecute used Sofía's **H: current working directory**, while the
official BAT internally runs `START ./"VTube Studio.exe" -nosteam`.
Windows therefore showed *cannot find ./"VTube Studio.exe"*.

**Fix on main:** invoke the BAT with an explicit current directory:
`os.startfile(str(root / "start_without_steam.bat"), cwd=str(root))`.
This requires no global `os.chdir`, which would disrupt other concurrent
Sofía operations. Also do not report `started_by_sofia: true` unless a
new exact matching VTS process was verified; otherwise return
`launch_not_verified` or `ambiguous_instance_ownership` with
`may_close: false`. Unit tests now assert a Steam install on another
drive, H: working directory preservation, and refusal to record an
unsuccessful launch.

On Venus: dismiss the Windows error, `git pull --ff-only`, run
`python -m pytest -q test/test_avatar2d_vtube_studio_host.py
test/test_avatar2d_vtube_studio_demand.py` (as one PowerShell command),
then, **only if no VTS instance is open**,
`python -m sofia.avatar.vtube_studio_host --launch`.
Require `launched_owned`; if it reports `reused_existing`, it will
**not** own or close that existing instance. When a verified owned
instance is open, `--close` sends WM_CLOSE (never force-kills).
This new patch itself has not yet been accepted on Venus.


### 2026-10-18 owner-confirmed real Venus process test

Real Windows evidence from the owner:
- `python -m sofia.avatar.vtube_studio_host --launch` reported
  `launched_owned`, `started_by_sofia: true`, `may_close: true`,
  PID `23864`. This verifies VTS was found on `E:\SteamLibrary`,
  launched from H: without the previous BAT current-directory error, and
  positively associated with the recorded Sofía-owned process.
- `--close` returned `graceful_close_requested`,
  `close_sent: true`, PID `23864`. This **confirms WM_CLOSE
  dispatch**, not independently that the process exited.
- New read-only command `python -m sofia.avatar.vtube_studio_host --status`
  reports the process table state, running instance count, whether
  Sofía's recorded process remains alive, and whether it's safe to
  request a close. Run after the close command to verify actual exit.
- New tests verify `--status` doesn't confuse requested shutdown
  with a confirmed exit or treat a separately opened user instance
  as owned. Windows run of these **new** tests is still pending.

The desktop `ExclusiveAvatarRenderer` on `src/sofia/ui/desktop.py`
currently owns the legacy Tk 2D backend. The new VTS host-demand policy
is separate and **NOT YET WIRED to a visual session lifecycle**. Do
not automatically launch the bare VTS app with no approved Cubism model,
and never claim that receiving a `graceful_close_requested` receipt
proves an avatar was rendered or VTS exited.
