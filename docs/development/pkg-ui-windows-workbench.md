# PKG-UI Windows workbench slice

**Date:** 2026-09-26. **Historical branch:** `feature/pkg-ui-windows-workbench`.
**Baseline:** PR #115 foundation at `381ac9a`.
**Status:** **accepted and merged to `main` via PR #116 at `7f072861`.** The feature branch is retired/safe to delete after local cleanup because the accepted content is on `main`.

## Desktop shell

Launch with:

```powershell
python -m sofia.ui
```

The shell uses Python's standard-library Tkinter stack and adds no Python
runtime dependency. It opens one canonical `SofiaApplication`, uses
`SofiaApplication.text_ui`, and does not create a duplicate runtime,
identity, memory system, personality, or conversation.

Implemented behavior:

- chronological persisted chat history;
- multiline composer;
- Enter sends and Shift+Enter inserts a newline;
- durable unsent draft recovery;
- generation/startup work off the Tk event thread;
- window remains text-first with no AVATAR renderer dependency;
- closing during an in-flight operation waits for the current operation rather
  than claiming unsupported model cancellation;
- launch imports Tk lazily so headless package/tests remain usable;
- history and composer surfaces use shallow 45-degree chamfered HUD frames;
- Send uses a matching chamfered Canvas control rather than a square ttk button;
- a curated Quick Tools dropdown loads reviewed read-only-first prompts into the
  composer without auto-executing them.

## Adaptive theme

The desktop can adapt its presentation from already trusted Sofía state:

- ENVIRONMENT: local time/daylight and only **current** cached weather;
- AVATAR: public-safe current outfit and appearance projection;
- emotion: the scoped, decaying modeled emotional state already used by the
  active conversation.

The policy is deterministic code, not an LLM-selected arbitrary CSS/color
surface. It never writes emotion, outfit, environment, memory, identity, or
authority state. It performs no extra weather/network refresh solely to repaint
the window.

Examples of bounded adaptation:

- night uses a darker panel;
- lounge presentation uses a warmer/crimson accent;
- engineer presentation retains violet/cyan engineering accents;
- rain/storm/snow/cloud conditions adjust secondary accents;
- strong warmth/fondness can warm the primary accent;
- curiosity/determination keep cyan/green focus accents;
- sadness/concern use a muted violet/cyan treatment;
- frustration/anger use a bounded warm warning accent with **no flashing**.

An **Adaptive theme** toggle immediately returns to the canonical violet/cyan/
green palette when disabled. Layout, text contrast, and interaction semantics do
not change with emotion. Chamfer outlines and the Send control follow the active
palette.

## Quick Tools

The desktop header includes a curated dropdown for frequently useful checks:
Tool Catalog, System, Hardware, Processes, Network, Services, Storage, Fleet,
Environment, and Current Outfit.

Selecting an item only loads its reviewed prompt into the composer. It does not
execute a capability, bypass authority, or silently send a message. The user
still presses Send, after which the canonical conversation/cognitive tool path
decides what authorized capability is available. A quick-tool prompt is saved as
the current unsent draft so it can survive a normal restart.

## Boundaries

- no animation, avatar renderer, voice, microphone, camera, browser, arbitrary
  OS keyboard/mouse control, or proactive send;
- no fake Stop button before actual provider/runtime cancellation exists;
- UI theme is expressive presentation only, never evidence that Sofía feels a
  particular emotion;
- private AVATAR presentation is not exposed because the desktop currently uses
  the runtime's public-safe presentation projection;
- SOCIAL principal/audience work remains a separate prerequisite before future
  multi-user/private UI scopes.

## Acceptance

Focused:

```powershell
pytest -q test/test_ui_desktop.py test/test_ui_desktop_worker.py test/test_ui_desktop_controller.py test/test_ui_desktop_application.py test/test_ui_theme.py test/test_ui_quick_tools.py
```

UI regression:

```powershell
pytest -q test/test_ui_delivery.py test/test_ui_drafts.py test/test_ui_text_client.py test/test_ui_workbench.py test/test_ui_application.py
```

Emotion/environment/avatar regression:

```powershell
pytest -q test/test_current_emotional_state.py test/test_emotional_conversation_integration.py test/test_avatar_presentation_routine.py test/test_avatar_wardrobe_routine.py test/test_environment_service.py
```

Acceptance completed on Windows. Evidence included focused desktop/theme/Quick Tools and AVATAR checks, a **90/90** integration repair gate, supervised live launch/use, and a final full repository `pytest -q` reported passing before PR #116 merged.

The accepted live checks covered startup, normal send, composer clear, current outfit self-fact grounding, adaptive-theme presentation, shallow chamfered history/composer/Send rendering, Quick Tools prompt loading without auto-send, and clean shutdown.
