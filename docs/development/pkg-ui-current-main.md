# PKG-UI current-main rebuild

**Date:** 2026-09-26. **Historical branch:** `feature/pkg-ui-current-main`.
**Baseline:** `main` at `65a59ba` when rebuilt.
**Status:** **foundation accepted and merged via PR #115 at `381ac9a`, then extended by the accepted Windows workbench PR #116 at `7f072861`.** This document is retained as implementation history; current UI status is tracked in `pkg-ui-windows-workbench.md` and the main roadmap.

## Why this branch exists

The older `feature/pkg-ui-foundation` and
`feature/pkg-ui-workbench-offline` branches were 397 commits behind current
`main`. Their useful contracts were treated as source material and rebuilt
on current main rather than directly merged.

Discord remains the already accepted remote text transport. This branch does
not replace or fork Discord, cognition, conversation persistence, INTERACT,
MEM, AVATAR, SOCIAL, ACT, or RUN.

## Current implementation

- `src/sofia/ui/delivery.py`: typed text/voice/avatar presentation planning
  with explicit caller-reported, unverified acknowledgement state. It never
  claims rendering or playback occurred merely because a model requested it.
- `src/sofia/ui/drafts.py`: durable unsent text drafts in the configured
  SQLite state database, scoped by client ID and canonical conversation
  session. Drafts remain outside conversation history and cognition until send.
- `src/sofia/ui/text.py`: text-first client adapter over the existing
  `ConversationService`. It projects exact persisted messages and sends only
  through the canonical conversation path. Failed sends preserve the draft.
- `src/sofia/ui/workbench.py`: rebuilt private workbench objects from the old
  offline UI branch, including source-linked ideas/reflections, explicit
  review/presentation, CAS-style revision checks, replay defense, archive, and
  validated snapshot/restore.
- `SofiaApplication.text_ui`: one local text UI bound to the same runtime and
  conversation service as CLI/Discord. UI draft storage closes and reopens
  across application lifecycle transitions.

## Truth and authority boundaries

A UI client ID is not an authenticated SOCIAL principal. UI does not infer
identity from model text. Unsent drafts are not visible to cognition. Workbench
snapshots are data, not authentication tokens. Presentation acknowledgements
remain unverified until a future trusted renderer/audio adapter supplies a
separately authorized receipt.

No renderer, microphone, camera, browser, general network access, OS keyboard
control, proactive send, voice engine, or avatar animation is enabled here.

## Acceptance commands

Focused:

```powershell
pytest -q test/test_ui_delivery.py test/test_ui_drafts.py test/test_ui_text_client.py test/test_ui_workbench.py test/test_ui_application.py
```

Application/Discord regression:

```powershell
pytest -q test/test_application.py test/test_application_acceptance.py test/test_conversation_loop.py test/test_discord_bridge.py test/test_discord_live.py test/test_discord_entrypoint.py
```

Then run the full repository suite before merge.

## Next UI slices

1. Real generation cancellation/stop only after cognition/provider cancellation exists; do not ship a decorative stop button.
2. Authorized history search and evidence/action-state presentation.
3. Renderer/avatar viewport with authenticated typed acknowledgements after AVATAR and SOCIAL/SAFE boundaries are ready.
4. Voice only with explicit mic/speaker consent and real completion receipts.
5. Mobile/web clients only after their authentication/audience boundaries are defined.
6. Shared workbench persistence/audience integration after SOCIAL principal projection exists.
