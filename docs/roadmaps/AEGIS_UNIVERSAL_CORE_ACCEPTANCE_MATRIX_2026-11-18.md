# Aegis Universal Core Acceptance Matrix — 2026-11-18

**Scope:** integration/QA branch `aegis/universal-integration` based on `main` commit
`1a1c13b9`. This matrix maps the mandated scenarios from
`docs/sofia2/AEGIS_UNIVERSAL_CORE_EMBODIMENT_WARDROBE_GOVERNANCE_V1.md` to source
and tests that exist in **this worktree**. It is not a release claim.

**Status legend**

- `SOURCE_TESTED` — a test in this worktree exercises the named source behavior.
- `CODED` — source exists, but no dedicated acceptance test in this worktree.
- `BLOCKED` — the behavior belongs to another ownership slice, is not present in
  this worktree, or requires installed/live evidence. No pass is claimed.

A source-green result is not installed-host or live verification. No scenario is
marked `INSTALLED` or `LIVE_VERIFIED`.

## Universal capability and gesture scenarios

| ID | Source path(s) | Test path(s) | Status |
| --- | --- | --- | --- |
| UC-01 | `src/sofia/platform/social/universal.py`; `src/sofia/sdk/core_capabilities.py`; `src/sofia/core/multicore/profiles.py`; `src/sofia/core/multicore/vera.py` | `test/test_aegis_universal_integration.py::test_roster_is_exactly_the_reviewed_intended_participants`; `test/test_aegis_universal_readout.py::test_all_four_readouts_declare_every_capability_family_but_none_effective` | `SOURCE_TESTED` |
| UC-02 | `src/sofia/platform/social/universal.py`; `src/sofia/sdk/core_capabilities.py` | `test/test_aegis_universal_integration.py::test_unsupported_renderer_returns_unavailable_without_render_claim`; `test/test_aegis_universal_readout.py::test_unsupported_renderers_are_unavailable_not_rendered` | `SOURCE_TESTED` (integration / unavailable-effect portion only) |
| UC-03 | Gesture slice A (not present here) | None in this worktree | `BLOCKED` |
| UC-04 | Gesture slice A (not present here) | None in this worktree | `BLOCKED` |
| UC-05 | Gesture slice A; private audience guard in `src/sofia/platform/social/universal.py` only | `test/test_aegis_universal_integration.py::test_private_group_audience_requires_independent_membership_evidence` covers the audience guard only | `BLOCKED` (full adult/private refusal and consent model not present) |
| UC-06 | Gesture slice A (not present here); receipt contract in `src/sofia/sdk/core_capabilities.py` | `test/test_aegis_universal_integration.py::test_supported_renderer_returns_only_the_adapter_receipt` covers the integration receipt boundary only | `BLOCKED` (real gesture renderer not present) |

## Wardrobe scenarios

| ID | Source path(s) | Test path(s) | Status |
| --- | --- | --- | --- |
| WD-01 | Wardrobe slice B; adapters in `src/sofia/platform/social/universal_integration.py` | `test/test_aegis_universal_integration.py::test_wardrobe_catalog_adapter_counts_without_exposing_items` covers catalog counting only | `BLOCKED` |
| WD-02 | Wardrobe/fit slice B (not present here) | None in this worktree | `BLOCKED` |
| WD-03 | Inventory slice C (not present here); contract in `src/sofia/modules/avatar/inventory_contract.py` | None in this worktree | `BLOCKED` |
| WD-04 | Inventory slice C (not present here); contract in `src/sofia/modules/avatar/inventory_contract.py` | None in this worktree | `BLOCKED` |
| WD-05 | Inventory slice C (not present here) | None in this worktree | `BLOCKED` |
| WD-06 | Inventory slice C; STOP gate in `src/sofia/platform/social/universal.py` | `test/test_aegis_universal_integration.py::test_operator_stop_blocks_effects_before_adapters_are_reached` covers the STOP gate only | `BLOCKED` (mid-transfer reconciliation not present) |
| WD-07 | Readout redaction in `src/sofia/platform/social/universal_readout.py`; private audience guard in `src/sofia/platform/social/universal.py` | `test/test_aegis_universal_readout.py::test_payload_is_json_safe_and_contains_no_private_audience_detail`; `test/test_aegis_universal_integration.py::test_private_group_audience_requires_independent_membership_evidence` | `BLOCKED` (readout/audience guard only; garment content projection not present) |

## Armor scenarios

| ID | Source path(s) | Test path(s) | Status |
| --- | --- | --- | --- |
| AR-01 | Armor slice B; shared validation in `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |
| AR-02 | Armor slice B; `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |
| AR-03 | Armor slice B; `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |
| AR-04 | Armor slice B; `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |
| AR-05 | Armor slice B; `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |
| AR-06 | Armor slice B; `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |
| AR-07 | Armor/fit slice B (not present here) | None in this worktree | `BLOCKED` |
| AR-08 | Armor slice B; `src/sofia/modules/avatar/wardrobe_equipment.py` | None in this worktree | `BLOCKED` |

## Governance scenarios

| ID | Source path(s) | Test path(s) | Status |
| --- | --- | --- | --- |
| GV-01 | Governance slice D; shared contracts in `src/sofia/platform/social/governance/contracts.py`; safe default in `src/sofia/platform/social/universal.py` | `test/test_aegis_universal_integration.py::test_safe_defaults_are_deny_or_unavailable` covers the unavailable default only | `BLOCKED` |
| GV-02 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-03 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-04 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-05 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-06 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-07 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-08 | Shared guard in `src/sofia/platform/social/governance/contracts.py`; readout in `src/sofia/platform/social/universal_readout.py` | `test/test_aegis_universal_integration.py::test_elected_coordinator_never_grants_platform_authority` covers the contract guard only | `BLOCKED` (authorization path not composed here) |
| GV-09 | Governance slice D; `src/sofia/platform/social/governance/contracts.py` | None in this worktree | `BLOCKED` |
| GV-10 | Roster exclusion in `src/sofia/platform/social/universal.py`; governance slice D for voting | `test/test_aegis_universal_integration.py::test_source_never_allocates_uuids_or_activates_twins`; `test/test_aegis_universal_integration.py::test_roster_rejects_twins_missing_cores_and_uuid_cloning` | `BLOCKED` (roster exclusion only; ballot roster not present) |
| GV-11 | Readout redaction in `src/sofia/platform/social/universal_readout.py`; private audience guard in `src/sofia/platform/social/universal.py` | `test/test_aegis_universal_readout.py::test_payload_is_json_safe_and_contains_no_private_audience_detail`; `test/test_aegis_universal_integration.py::test_private_group_audience_requires_independent_membership_evidence` | `BLOCKED` (readout/audience guard only; governance broadcast path not present) |
| GV-12 | STOP gate in `src/sofia/platform/social/universal.py`; governance slice D for elections | `test/test_aegis_universal_integration.py::test_operator_stop_blocks_effects_before_adapters_are_reached` covers gesture/transfer STOP only | `BLOCKED` (mid-election reconciliation not present) |

## Test commands actually run in this worktree

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/test_aegis_universal_integration.py test/test_aegis_universal_readout.py test/test_core_multicore_profiles.py test/test_core_multicore_identity.py test/test_platform_social_integration_adapters.py test/test_platform_social_autonomy_safety.py test/test_sdk_compatibility.py test/test_core_multicore_vera.py
```

Result: `96 passed`.

No production database, protected Core state, `sofia.db`, or another slice's
source file was read or modified by this worktree.
