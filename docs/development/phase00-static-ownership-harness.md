# Phase 00: canonical code ownership audit harness

Status: **implemented but not executed** at the owner's instruction (no tests / no code execution). New CLI runs a **read-only static AST scan**; it does not import application modules or open `sofia.db`.

```powershell
python -m sofia.verify.architecture_inventory --root . --output phase00-architecture-inventory.json
```

The resulting JSON names current production source-owner files and identifies only **possible** duplicate function bodies. It records source availability and import counts, **not** reachability, authority or test status. Before removing code, examine runtime/bootstrap callers, Windows service entrypoints, CLI loading, schema/serialized compatibility, historical imports and Fleet version requirements. No production module was deleted during this phase.

See `docs/development/companion-autonomy-contract.md` for canonical owner/consumer/error boundaries and three full paths. The separate `SofiaApplication.latest_companion_decision_trace()` adds a read-only, turn-scoped Matrix projection without creating a second truth ledger. Only a true cross-system causal ID can justify linking an unrelated NEURO state or LIFE outcome.

**Acceptance deferred:** static audit output review, test collection, full release, Venus live, Artemis canary and long-duration host evaluation.
