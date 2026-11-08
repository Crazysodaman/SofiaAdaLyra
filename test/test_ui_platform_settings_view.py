"""Aegis Settings GUI/TUI projection never becomes a settings writer."""
import pytest

from sofia.sdk.platform_settings_view import (
    project_settings_snapshot, render_settings_lines,
)


def scoped_snapshot():
    return {
        "schema_version": 1,
        "revision": 2,
        "effective_revision": 1,
        "values": {
            "location_label": "Workshop",
            "fleet_discovery_enabled": True,
            "discord_owner_user_id": "private-identifier",
            "provider_temperature": 0.7,
        },
        "contracts": {
            "location_label": {"owner": "core", "apply_class": "live"},
            "fleet_discovery_enabled": {
                "owner": "host", "apply_class": "component_restart",
            },
            "discord_owner_user_id": {
                "owner": "core", "apply_class": "component_restart",
            },
            "provider_temperature": {
                "owner": "core", "apply_class": "component_restart",
            },
        },
    }


def test_view_distinguishes_saved_from_applied_and_omits_secret():
    view = project_settings_snapshot(scoped_snapshot())
    lines = "\n".join(render_settings_lines(view))
    assert view.revision == 2 and view.effective_revision == 1
    assert all(item.requires_apply is None for item in view.rows)
    assert "SOURCE TRUST: UNVERIFIED" in lines
    assert "APPLY UNKNOWN" in lines
    assert "[REDACTED]" in lines
    assert "private-identifier" not in lines
    assert "Workshop" in lines


@pytest.mark.parametrize("change", [
    {"revision": True},
    {"effective_revision": 99},
    {"contracts": {}},
    {"schema_version": "1"},
])
def test_malformed_settings_fail_closed(change):
    snapshot = scoped_snapshot()
    snapshot.update(change)
    with pytest.raises(ValueError):
        project_settings_snapshot(snapshot)


def test_control_character_injection_cannot_reach_terminal():
    snapshot = scoped_snapshot()
    snapshot["values"]["location_label"] = "\x1b[31mINJECT\n"
    lines = "\n".join(render_settings_lines(project_settings_snapshot(snapshot)))
    assert "\x1b" not in lines
    assert "INJECT" not in lines
    assert "[TEXT HIDDEN]" in lines


def test_unknown_owner_and_unknown_apply_class_denied():
    snapshot = scoped_snapshot()
    snapshot["contracts"]["location_label"]["owner"] = "self-authorized"
    with pytest.raises(ValueError, match="settings contract"):
        project_settings_snapshot(snapshot)
    snapshot["contracts"]["location_label"]["owner"] = "core"
    snapshot["contracts"]["location_label"]["apply_class"] = "auto-grant"
    with pytest.raises(ValueError, match="settings contract"):
        project_settings_snapshot(snapshot)


def test_fully_effective_snapshot_does_not_claim_any_pending_field():
    snapshot = scoped_snapshot()
    snapshot["effective_revision"] = snapshot["revision"]
    view = project_settings_snapshot(snapshot)
    assert all(item.requires_apply is False for item in view.rows)
    assert "APPLY UNKNOWN" not in "\\n".join(render_settings_lines(view))


def test_untrusted_snapshot_cannot_certify_live_settings_draft():
    snapshot = scoped_snapshot()
    baseline = project_settings_snapshot(snapshot)
    assert baseline.needs_review(baseline)
    snapshot["revision"] = 3
    snapshot["effective_revision"] = 2
    assert baseline.needs_review(project_settings_snapshot(snapshot))



def signed_module_snapshot():
    from sofia.sdk.module_settings import (
        ModuleSettingApplyClass, ModuleSettingField, ModuleSettingType,
        ModuleSettingsContract, module_settings_contract_to_document,
    )
    contract = ModuleSettingsContract(
        "sofia.module.settings.v1", 1, (
            ModuleSettingField(
                "display.mode", "Display", ModuleSettingType.ENUM,
                ModuleSettingApplyClass.LIVE,
                enum_values=("compact", "full"),
            ),
            ModuleSettingField(
                "credential.ref", "Credential", ModuleSettingType.STRING,
                ModuleSettingApplyClass.COMPONENT_RESTART,
                secret_reference=True,
            ),
        ),
    )
    return {
        "module_id": "org.sofia.settings.test",
        "package_digest": "a" * 64,
        "lifecycle": "active",
        "lifecycle_revision": 3,
        "revision": 2,
        "effective_revision": 1,
        "values": {
            "display.mode": "compact",
            "credential.ref": "<protected-secret-reference>",
        },
        "contract": module_settings_contract_to_document(contract),
    }


def test_module_setting_projection_binds_signed_package_identity_and_redacts():
    from sofia.sdk.platform_settings_view import project_module_settings_snapshot
    snapshot = signed_module_snapshot()
    view = project_module_settings_snapshot(snapshot)
    assert view.package_digest == "a" * 64
    assert view.lifecycle_revision == 3
    assert [item.field_id for item in view.rows] == [
        "credential.ref", "display.mode",
    ]
    assert view.rows[0].saved_value == "[REDACTED]"
    assert view.rows[1].saved_value == "compact"
    assert all(item.requires_apply is None for item in view.rows)


def test_reinstall_digest_and_lifecycle_revision_invalidate_module_editor():
    from sofia.sdk.platform_settings_view import project_module_settings_snapshot
    baseline = signed_module_snapshot()
    current = project_module_settings_snapshot(baseline)
    replacement = signed_module_snapshot()
    replacement["package_digest"] = "b" * 64
    assert current.needs_review(project_module_settings_snapshot(replacement))
    replacement = signed_module_snapshot()
    replacement["lifecycle_revision"] += 1
    assert current.needs_review(project_module_settings_snapshot(replacement))


def test_module_ui_never_displays_raw_secret_or_accepts_unknown_field():
    from sofia.sdk.platform_settings_view import project_module_settings_snapshot
    snapshot = signed_module_snapshot()
    snapshot["values"]["credential.ref"] = "secret:owner.private_key"
    with pytest.raises(ValueError, match="unredacted"):
        project_module_settings_snapshot(snapshot)
    snapshot = signed_module_snapshot()
    snapshot["values"]["injected.setting"] = "anything"
    with pytest.raises(ValueError, match="unreviewed"):
        project_module_settings_snapshot(snapshot)
