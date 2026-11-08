# AG-D024 | GUI/TUI/CLI parity review

**Status:** OWNER-DESIRED, DETAILED DESIGN CAPTURED (2026-11-08).
**Target release:** Platform 1.0 expanded shakedown (owner directive 2026-11-08).

Created by the owner directive scheduling GUI/TUI management functionality
into the expanded Platform 1.0 shakedown. It defines HOW parity of the three
clients (GUI, TUI, CLI) over one authenticated management API is reviewed;
implementation sequencing lives in the
[batches document](../development/AEGIS_UI_SHAKEDOWN_BATCHES_2026-11-08.md).

## Parity dimensions

1. **Operation parity:** every management operation available to any client is
   available through the same versioned management API with identical request
   semantics, approval requirements and receipt records. No client gets an
   operation the others lack (essential shakedown functionality: live status,
   Platform settings, Core Manager, Module Manager, Security/Approvals,
   Updates/Recovery, Diagnostics).
2. **Authority parity:** service-side authorization is identical for all
   clients. No display-name-only or UI-only grant. Protected operations
   require the same fresh owner proof regardless of client.
3. **State presentation parity:** the same observation vocabulary and stale/
   disconnected semantics appear on all clients; a client must label
   (`STALE`, `UNKNOWN`, `DISCONNECTED`) rather than infer. Live status and
   reconnect handling behave equivalently in GUI and TUI.
4. **Receipt parity:** an effect performed from GUI, TUI or CLI leaves the
   same durable receipt fields (excluding presentation-only differences), so
   later audits never depend on which client acted.
5. **Install parity:** GUI and TUI are independently installable; installing
   one never requires installing or starting the other; headless hosts need
   neither.

## Review protocol

* Each UI batch closing a shakedown row must document a parity table: every
  management API operation consumed, by which clients, at which source SHA.
* Parity gaps are recorded as explicit row evidence against the acceptance
  tracker; a row without its parity table stays NOT TESTED.
* Diff review compares the received request fingerprint parameters between
  clients for identical operation packs (same capability, same parameters).
* Negative checks repeat across clients: revoked session, stale host,
  disconnected Platform, operator STOP engaged; all must deny everywhere.

## Out of scope for minimum shakedown

Advanced personal SofA-a Workbench, the full Model Manager and autonomous
Core self-management are excluded from minimum Platform-only release
requirements by the owner directive and are never parity obligations of
rows 31-38.
