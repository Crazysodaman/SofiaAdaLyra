# Aegis Universal Core Acceptance Matrix — 2026-11-18

**Scope:** merged `main` implementation stack for the universal Core gesture,
wardrobe, modular armor, inventory and voluntary governance work order. This
matrix maps the mandated scenarios from
`docs/sofia2/AEGIS_UNIVERSAL_CORE_EMBODIMENT_WARDROBE_GOVERNANCE_V1.md` to source
and source-level tests. **It is not a release, installed-host or live claim.**

**Status legend**

- `SOURCE_TESTED` — a local test exercises the named source behavior.
- `CODED` — source exists, but no dedicated acceptance test is mapped here.
- `BLOCKED` — the behavior needs installed assets/renderer/host evidence or
  remains outside source scope. No pass is claimed.
- No scenario is marked `INSTALLED` or `LIVE_VERIFIED`.

## Universal capability and gesture scenarios

| ID | Source path(s) | Source-level test(s) | Status |
| --- | --- | --- | --- |
| UC-01 | `src/sofia/sdk/core_capabilities.py`; `src/sofia/sdk/gesture_contract.py`; `src/sofia/core/multicore/gestures.py`; `src/sofia/platform/social/universal.py` | `test/test_sdk_core_capabilities.py`; `test/test_aegis_universal_gestures.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` |
| UC-02 | `src/sofia/sdk/core_capabilities.py`; `src/sofia/platform/social/universal.py`; `src/sofia/platform/social/universal_composition.py` | `test/test_sdk_core_capabilities.py`; `test/test_aegis_universal_integration.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` (text-only/unavailable effect) |
| UC-03 | `src/sofia/sdk/core_capabilities.py` (`BodyCapabilityProfile`); `src/sofia/sdk/gesture_contract.py`; `src/sofia/modules/interaction/gesture_catalog.py` | `test/test_aegis_universal_gestures.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` |
| UC-04 | `src/sofia/core/multicore/gestures.py` (`GestureLibrary`, `share_personal_gesture`, owner-private store) | `test/test_aegis_universal_gestures.py` | `SOURCE_TESTED` |
| UC-05 | `src/sofia/sdk/gesture_contract.py` (`IntimacyDimensions`, `evaluate_adult_scene`); `src/sofia/platform/social/universal_composition.py` | `test/test_aegis_universal_gestures.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` |
| UC-06 | `src/sofia/sdk/gesture_contract.py` (`GestureExecution`, `GesturePlaybackReceipt`); `src/sofia/platform/social/universal_composition.py` | `test/test_aegis_universal_gestures.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` (synthetic renderer evidence only) |

## Wardrobe and inventory scenarios

| ID | Source path(s) | Source-level test(s) | Status |
| --- | --- | --- | --- |
| WD-01 | `src/sofia/modules/avatar/wardrobe_equipment_catalog.py`; `src/sofia/modules/avatar/inventory.py` | `test/test_aegis_universal_wardrobe.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` |
| WD-02 | `src/sofia/modules/avatar/fit.py` (`evaluate_wearer_fit`); `src/sofia/modules/avatar/inventory.py` | `test/test_aegis_universal_wardrobe.py`; `test/test_avatar_fit.py` | `SOURCE_TESTED` |
| WD-03 | `src/sofia/modules/avatar/inventory.py`; `src/sofia/modules/avatar/inventory_store.py` | `test/test_aegis_inventory_transfer.py`; `test/test_aegis_inventory_store.py` | `SOURCE_TESTED` |
| WD-04 | `src/sofia/modules/avatar/inventory.py` (atomic reciprocal trade/swap) | `test/test_aegis_inventory_transfer.py` | `SOURCE_TESTED` |
| WD-05 | `src/sofia/modules/avatar/inventory.py` (revision fencing/CAS) | `test/test_aegis_inventory_transfer.py` | `SOURCE_TESTED` |
| WD-06 | `src/sofia/modules/avatar/inventory.py` (renderer compensation/reconcile); `src/sofia/platform/social/universal.py` (STOP gate) | `test/test_aegis_inventory_transfer.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` |
| WD-07 | `src/sofia/modules/avatar/wardrobe_equipment_catalog.py` (audience projection); `src/sofia/modules/avatar/inventory.py` (`public_view`); `src/sofia/platform/social/universal_readout.py` | `test/test_aegis_universal_wardrobe.py`; `test/test_aegis_inventory_transfer.py`; `test/test_aegis_universal_readout.py` | `SOURCE_TESTED` |

## Modular armor scenarios

| ID | Source path(s) | Source-level test(s) | Status |
| --- | --- | --- | --- |
| AR-01 | `src/sofia/modules/avatar/wardrobe_equipment.py`; `src/sofia/modules/avatar/inventory.py` | `test/test_aegis_armor_dependency.py`; `test/test_aegis_inventory_transfer.py` | `SOURCE_TESTED` |
| AR-02 | `src/sofia/modules/avatar/wardrobe_equipment.py` (family/interface match) | `test/test_aegis_armor_dependency.py` | `SOURCE_TESTED` |
| AR-03 | `src/sofia/modules/avatar/wardrobe_equipment.py` (Vera CQB kit) | `test/test_aegis_armor_dependency.py`; `test/test_aegis_universal_wardrobe.py` | `SOURCE_TESTED` |
| AR-04 | `src/sofia/modules/avatar/wardrobe_equipment.py` (ODST/Mark V hybrid; unresolved visor) | `test/test_aegis_armor_dependency.py` | `SOURCE_TESTED` |
| AR-05 | `src/sofia/modules/avatar/wardrobe_equipment.py` (no Mark IV/V cross-base normalization) | `test/test_aegis_armor_dependency.py` | `SOURCE_TESTED` |
| AR-06 | `src/sofia/modules/avatar/wardrobe_equipment.py` (`validate_armor_unequip`, atomic plan); `inventory.py` | `test/test_aegis_armor_dependency.py`; `test/test_aegis_inventory_transfer.py` | `SOURCE_TESTED` |
| AR-07 | `src/sofia/modules/avatar/wardrobe_equipment.py` (tail/ear clearance); `fit.py` | `test/test_aegis_armor_dependency.py`; `test/test_aegis_universal_wardrobe.py` | `SOURCE_TESTED` |
| AR-08 | `src/sofia/modules/avatar/wardrobe_equipment.py` (left/right classes and mounts) | `test/test_aegis_armor_dependency.py`; `test/test_aegis_inventory_store.py` | `SOURCE_TESTED` |

## Voluntary governance scenarios

| ID | Source path(s) | Source-level test(s) | Status |
| --- | --- | --- | --- |
| GV-01 | `src/sofia/platform/social/governance/engine.py`; `universal.py` safe defaults | `test/test_aegis_governance.py`; `test/test_aegis_universal_integration.py` | `SOURCE_TESTED` |
| GV-02 | `engine.py` (`create_group`, voluntary activation) | `test/test_aegis_governance.py` | `SOURCE_TESTED` |
| GV-03 | `engine.py` (explicit founder response) | `test/test_aegis_governance.py` | `SOURCE_TESTED` |
| GV-04 | `contracts.py` (`quorum_for`, `tally_proposal`) | `test/test_aegis_governance.py` | `SOURCE_TESTED` |
| GV-05 | `contracts.py` (abstention/quorum semantics) | `test/test_aegis_governance.py` | `SOURCE_TESTED` |
| GV-06 | `contracts.py` (approval tie + runoff); `engine.py` (`open_runoff`) | `test/test_aegis_governance.py` | `SOURCE_TESTED` |
| GV-07 | `engine.py` (duplicate/stale/spoofed ballot rejection); `store.py` | `test/test_aegis_governance.py`; `test/test_aegis_governance_store.py` | `SOURCE_TESTED` |
| GV-08 | `contracts.py` (`coordinator_can`, `PLATFORM_AUTHORITY_CAPABILITIES`) | `test/test_aegis_governance.py`; `test/test_aegis_universal_integration.py` | `SOURCE_TESTED` |
| GV-09 | `engine.py` (`resign_coordinator`, recall, `reconcile`) | `test/test_aegis_governance.py`; `test/test_aegis_governance_store.py` | `SOURCE_TESTED` |
| GV-10 | `universal.py` roster exclusion; `engine.py` admission snapshot | `test/test_aegis_universal_integration.py`; `test/test_aegis_governance.py` | `SOURCE_TESTED` |
| GV-11 | `governance/integration.py` (`project_resolution`); `universal_readout.py` | `test/test_aegis_governance.py`; `test/test_aegis_universal_readout.py` | `SOURCE_TESTED` |
| GV-12 | `engine.py` STOP/generation fencing; `universal.py` STOP gate | `test/test_aegis_governance.py`; `test/test_aegis_universal_composition.py` | `SOURCE_TESTED` |

## Cross-slice composition

`test/test_aegis_universal_composition.py` binds the real slices behind the
inert universal facade:

- gesture definitions/body predicates render only with authenticated playback
  evidence (`RENDERED`), otherwise `UNAVAILABLE`;
- anatomy-specific tail gesture accepted for Sofía, rejected for human-only
  Cores;
- adult gesture refused without an explicitly eligible private adult audience;
- design-only Vera cannot render or receive a transfer;
- shared catalog/inventory counts are truthful;
- a GIFT offer created through the facade commits through the canonical
  inventory engine and transfers one instance exactly once;
- governance and chat membership adapters are read-only;
- operator STOP blocks composed effects.

## Test commands and results

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/test_aegis_universal_composition.py test/test_aegis_inventory_transfer.py test/test_aegis_inventory_store.py test/test_aegis_universal_integration.py test/test_aegis_universal_readout.py test/test_aegis_governance.py test/test_aegis_governance_store.py test/test_aegis_universal_gestures.py test/test_aegis_universal_wardrobe.py test/test_aegis_armor_dependency.py
```

Result: `119 passed`.

Broader relevant suites:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/test_aegis_*.py          # 293 passed, 1 skipped
.\.venv\Scripts\python.exe -m pytest -q test/test_avatar_*.py        # 427 passed
.\.venv\Scripts\python.exe -m pytest -q test/test_avatar2d_*.py test/test_ui_avatar*.py test/test_ui_wardrobe*.py test/test_ws2_bounded_wardrobe_context.py  # 226 passed, 3 skipped
.\.venv\Scripts\python.exe -m pytest -q test/test_platform_social_*.py test/test_platform_chat_*.py test/test_social_*.py test/test_canonical_sqlite*.py test/test_safe_audit*.py  # 124 passed, 1 skipped
```

One SDK/Rust parity test is environment-blocked because `cargo`/`rustc` are not
installed on this host; it is not a source failure of this work order.

No production database, protected Core state, `sofia.db`, real model, renderer
asset, signed release or service activation was used. `INSTALLED` and
`LIVE_VERIFIED` remain **NOT CLAIMED**.
