"""The rationalization audit is read-only planning, not package migration.

Source-only tests deliberately avoid granting, signing, installing or invoking
a module; an accepted design recommendation is not release acceptance.
"""
from __future__ import annotations

import json

import pytest

from sofia.modules.catalog_consolidation import (
    candidate_modules, catalog_consolidation_review, consolidation_plans,
)
from sofia.modules.optional_release_audit import (
    EXPECTED_OPTIONAL_IDS, audit_optional_source_tree,
)


def test_six_source_ids_are_unique_and_existing_optional_catalog_members():
    plans = consolidation_plans()
    sources = [plan.source_id for plan in plans]
    assert len(plans) == len(set(sources)) == 6
    assert set(sources) <= EXPECTED_OPTIONAL_IDS


def test_destinations_exist_and_never_self_reference():
    for plan in consolidation_plans():
        assert plan.destination_ids
        assert len(plan.destination_ids) == len(set(plan.destination_ids))
        assert plan.source_id not in plan.destination_ids
        assert set(plan.destination_ids) <= EXPECTED_OPTIONAL_IDS | {"RM-AVATAR2D"}
        assert plan.conditions


def test_exact_approved_six_rationalizations():
    assert {plan.source_id: plan.destination_ids for plan in consolidation_plans()} == {
        "MOD-GENERALIZATION": ("MOD-ML",),
        "MOD-CALENDAR": ("MOD-PRODUCTIVITY",),
        "MOD-PROJECT-FORGE": ("MOD-PRODUCTIVITY", "MOD-CREATIVE"),
        "MOD-FILE-WATCH": ("MOD-IT-OBSERVABILITY",),
        "MOD-DIGITAL-TWIN": ("MOD-HOMELAB", "MOD-WORKSHOP"),
        "MOD-AVATAR-STUDIO": ("MOD-CREATIVE", "RM-AVATAR2D"),
    }


def test_all_legacy_ids_remain_registered_and_no_alias_or_privilege_is_granted():
    result = catalog_consolidation_review(EXPECTED_OPTIONAL_IDS)
    assert result["current_catalog_count"] == 47
    assert result["planned_consolidation_count"] == 6
    assert result["unobserved_source_ids"] == []
    assert result["unobserved_destination_ids"] == []
    assert result["effect"] == "none"
    assert result["approval_for_execution"] is False
    assert result["migration_verified"] is False
    for plan in result["plans"]:
        assert plan["authority_effect"] == "none"
        assert plan["source_retired"] is False
        assert plan["runtime_capabilities_changed"] is False
        assert plan["package_identity_changed"] is False
        assert plan["migration_verified"] is False
    json.dumps(result)


def test_conditional_new_module_ideas_are_not_installed_or_active():
    candidates = candidate_modules()
    assert {item["candidate_id"] for item in candidates} == {
        "MOD-IT-GAME-SERVERS", "MOD-IT-IDENTITY-DIRECTORY",
    }
    for candidate in candidates:
        assert candidate["candidate_id"] not in EXPECTED_OPTIONAL_IDS
        assert candidate["initial_owner"] in EXPECTED_OPTIONAL_IDS
        assert candidate["approved_catalog_entry"] == "false"
        assert candidate["installable"] == "false"


def test_missing_catalog_sources_report_unknown_instead_of_claiming_merger():
    result = catalog_consolidation_review(("MOD-ML",))
    assert "MOD-GENERALIZATION" in result["unobserved_source_ids"]
    assert "MOD-PRODUCTIVITY" in result["unobserved_destination_ids"]
    assert result["effect"] == "none"
    assert result["migration_verified"] is False


@pytest.mark.parametrize("ids", [
    ("MOD-ML", "MOD-ML"), ("",), (None,), (42,), ("MOD-ML", ""),
])
def test_invalid_and_duplicate_catalog_ids_rejected(ids):
    with pytest.raises(ValueError):
        catalog_consolidation_review(ids)


def test_existing_source_preflight_includes_non_authoritative_plans(tmp_path):
    audit = audit_optional_source_tree(tmp_path)
    assert audit["beta_verified"] == 0
    assert audit["expected_optional_modules"] == 47
    assert audit["source_unobserved"] == 47
    assert audit["consolidation_review"]["planned_consolidation_count"] == 6
    assert audit["consolidation_review"]["approval_for_execution"] is False
    assert audit["consolidation_review"]["migration_verified"] is False
    assert audit["consolidation_review"]["effect"] == "none"
