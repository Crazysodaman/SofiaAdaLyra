"""G2-F: checked-in Windows Fleet canary points at real Platform entrypoints.

Static inspection only. Never invoke provisioning, enrollment, firewall changes,
certificate creation, or a real Fleet endpoint from an automated test.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Setup-SofiaFleetArtemis.ps1"


def test_windows_canary_uses_only_existing_platform_entrypoints():
    source = SCRIPT.read_text(encoding="utf-8")
    expected = {
        "sofia.platform.distributed.pki": 2,
        "sofia.platform.distributed.agent_main": 3,
        "sofia.platform.ops.discovery_canary": 1,
    }
    for module, count in expected.items():
        assert source.count(module) == count, module
        assert (ROOT / "src" / Path(*module.split(".")).with_suffix(".py")).is_file()
    assert "sofia.distributed." not in source
    assert "sofia.ops.discovery_canary" not in source


def test_windows_canary_cannot_be_treated_as_debian_vm_cutover():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Legacy Windows-only Artemis Fleet canary" in source
    assert "independent owner authorization" in source
    assert 'ValidateSet("Prepare", "Artemis", "Verify")' in source
    assert "verified_agent_observed_untrusted_candidate" not in source
