import json

import pytest

from sofia.ops.linux_bootstrap import LinuxBootstrapBundle, render_linux_rollback


pytestmark = pytest.mark.pkg_ops


def bundle():
    return LinuxBootstrapBundle(
        "sofia.whl", "a" * 64, "python", "b" * 64,
        "agent.json", "/opt/sofia-fleet",
    )


def test_linux_bootstrap_is_offline_hash_pinned_atomic_and_health_checked():
    script = bundle().render()
    assert "sha256sum -c" in script
    assert "--no-index --no-deps" in script
    assert "mv -Tf" in script
    assert "systemctl is-active" in script
    assert "http://" not in script and "https://" not in script


def test_linux_bootstrap_receipt_must_match_release_and_artifact():
    value = bundle().verify_receipt(json.dumps({
        "status": "succeeded", "release_id": "release-1",
        "wheel_sha256": "a" * 64, "previous": "",
    }), release_id="release-1")
    assert value["status"] == "succeeded"
    with pytest.raises(RuntimeError, match="does not match"):
        bundle().verify_receipt(json.dumps({
            "status": "succeeded", "release_id": "other",
            "wheel_sha256": "a" * 64,
        }), release_id="release-1")


def test_linux_rollback_restores_previous_and_reverts_failed_rollback():
    script = render_linux_rollback(install_root="/opt/sofia-fleet")
    assert "rollback-target" in script
    assert "current.failed-rollback" in script
    assert "systemctl is-active" in script


@pytest.mark.parametrize("path", ["relative", "/tmp/../etc", "/opt/$ROOT"])
def test_linux_bootstrap_rejects_unsafe_install_root(path):
    with pytest.raises(ValueError, match="safe absolute"):
        LinuxBootstrapBundle(
            "sofia.whl", "a" * 64, "python", "b" * 64,
            "agent.json", path,
        )
