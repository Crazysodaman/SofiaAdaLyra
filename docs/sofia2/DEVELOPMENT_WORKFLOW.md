# Sofía 2.0 local development and publication workflow

**Current owner decision:** OpenCode is the sole active implementation agent for Sofía 2.0, starting Core B00 through B08 sequentially, then expanding the non-Core module backlog. Its local development model and effort selection do not themselves certify correctness. This document updates process intent, not runtime authority.

## Environment roles

- **OpenCode:** local edit, inspect, targeted test, diagnose, integrate, collect change evidence and report incomplete requirements.
- **Owner:** controls consequential approval, Git checkpoints, production updates, protected changes and release activation.
- **GitHub main:** authoritative reviewed code history and documentation checkpoints; current local dirty trees may be ahead of remote.
- **Independent review:** checks published code and matching test/CI evidence. It does not infer status from an agent summary.
- **Sofía at runtime:** cannot assume OpenCode's development authority, Git push credentials or canonical writer rights.

## One writer and safe parallelism

Only OpenCode edits the active Sofía 2.0 working tree. Read-only audits or documentation updates may occur separately. If two agents are ever used, each requires separate cloned/worktree roots and an explicit integration owner; never edit the same working directory simultaneously.

The owner may push source checkpoints during development after files are quiescent. A remote documentation-only update **does not automatically appear in a live local OpenCode checkout**. To incorporate it, first ask the agent to finish its current edit and preserve all uncommitted changes, then fetch and reconcile safely. Never use `git reset --hard`, unreviewed force push, or automatic rebase over a dirty worktree.

## Development cycle

1. Check `git branch --show-current`, `git rev-parse HEAD`, `git status --short`; note OS, Python, test tools and base SHA.
2. Audit the next requirement against code and original task text; avoid placeholders and duplicate owners.
3. Make one coherent, reversible implementation slice with integration and tests.
4. Run focused tests and affected integration tests, then source/security audit.
5. Record actual pass/fail/skip counts, commands, environment, diff inventory and unresolved issues.
6. Prepare a sanitized checkpoint, excluding state DB, tokens, signing keys, sessions, model private data and caches.
7. Obtain owner authorization for commit/push (and separate authorization for any deployment).
8. Push `main` without force. Independently inspect the remote SHA and any CI check run.
9. Continue to next eligible batch. If interrupted, resume from exact source and evidence, not prior agent assertions.

## Gate evidence

L1 Unknown; L2 audited/partial; L3 production-coded; L4 tests actually passed and integration reviewed; L5 exact-revision CI. Tasks needing host trials keep their own acceptance state. A passing local command is not CI. A committed change is not installed software. Tool call success is not the same as an observed external result.

## Protected boundaries

No agent may on its own change the Constitution, escalate privileges, enroll identities, move the canonical DB, execute destructive migrations, initiate live deployments, silently switch the runtime model, modify the single-writer authority, or bypass SAFE and operator STOP. Capability and module discovery do not imply installation or run permission.

## OpenCode handoff note

The Core spec and any prior Codex B00/B01 work may exist only in another local workspace. OpenCode must verify which copy exists, safely import reviewed source when approved, and re-audit B00/B01. Do not treat uncommitted or privately uploaded material as already on GitHub.

## Current non-Core development strategy

Core B00–B08 is the primary implementation track. Non-Core architecture and contracts may be fleshed out in documentation in parallel. Non-Core **coding** must respect the one-active-writer rule and should commence only with explicit scoped work after shared module interfaces are stable or during approved independent batches.

Priority after stable module seam: platform safety and module lifecycle → desktop/Discord/2D avatar release bundles → speech/mobile → research/creative/productivity → host/robot/train integrations → advanced training/evaluation. The owner may change this prioritization without renumbering the original 780 requirements.
