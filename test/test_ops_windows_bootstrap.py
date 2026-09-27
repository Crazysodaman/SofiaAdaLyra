import json
from pathlib import Path
from uuid import UUID

import pytest

from sofia.ops.bootstrap import AgentPackage, BootstrapCandidate
from sofia.ops.windows_bootstrap import (
    WindowsCimBootstrapInstaller,
    _safe_windows_path,
    render_installer,
    sha256_file,
)


NODE_ID = UUID("cedf5c64-f3f5-46e0-8c5b-4f85089fcaba")


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    (bundle / "certs").mkdir(parents=True)
    (bundle / "state").mkdir()
    (bundle / "agent.json").write_text("{}", encoding="utf-8")
    for name in ("fleet-ca.pem", "artemis-server.pem", "artemis-server-key.pem"):
        (bundle / "certs" / name).write_text(name, encoding="utf-8")
    wheel = tmp_path / "sofia_ada_lyra-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"reviewed-wheel")
    return bundle, wheel


def _package(wheel: Path) -> AgentPackage:
    return AgentPackage(
        "sofia-fleet-agent",
        "0.1.0",
        sha256_file(wheel),
        str(wheel),
    )


def _candidate() -> BootstrapCandidate:
    return BootstrapCandidate(
        host_id="Artemis",
        platform="windows",
        architecture="x86_64",
        discovery_source="test",
        inside_approved_scope=True,
        trusted_bootstrap_available=True,
    )


def test_windows_paths_are_absolute_and_reject_command_breakout():
    assert _safe_windows_path(r"H:\Fleet\Artemis", "stage") == r"H:\Fleet\Artemis"
    with pytest.raises(ValueError):
        _safe_windows_path('H:\\Fleet\\"bad"', "stage")
    with pytest.raises(ValueError):
        _safe_windows_path("H:\\Fleet\\bad\npath", "stage")
    with pytest.raises(ValueError):
        _safe_windows_path(r"relative\path", "stage")


def test_rendered_installer_is_hash_pinned_and_local_subnet_scoped():
    script = render_installer(
        stage_path=r"H:\Users\Crazysodaman\FleetTransfer\ArtemisAgent",
        install_root=r"C:\ProgramData\SofiaAdaLyra\FleetAgent",
        wheel_name="sofia_ada_lyra-0.1.0-py3-none-any.whl",
        package_sha256="a" * 64,
        node_id=NODE_ID,
        listen_port=7443,
    )
    assert "$ExpectedHash = '" + ("a" * 64) + "'" in script
    assert "Get-FileHash -Algorithm SHA256" in script
    assert "-RemoteAddress LocalSubnet" in script
    assert "sofia.distributed.agent_main" in script
    assert "bootstrap-receipt.json" in script


def test_prepare_stage_copies_only_reviewed_bundle_and_generated_installer(tmp_path: Path):
    bundle, wheel = _bundle(tmp_path)
    stage = tmp_path / "stage"
    installer = WindowsCimBootstrapInstaller(
        host="Artemis",
        credential_user=r"Artemis\Administrator",
        bundle_directory=bundle,
        wheel_path=wheel,
        controller_stage_directory=stage,
        remote_stage_path=r"H:\Users\Crazysodaman\FleetTransfer\ArtemisAgent",
        node_id=NODE_ID,
        launcher=lambda *_: None,
    )

    generated = installer.prepare_stage(_package(wheel))

    assert generated == stage / "install.ps1"
    assert (stage / "agent.json").is_file()
    assert (stage / "certs" / "fleet-ca.pem").is_file()
    assert (stage / "certs" / "artemis-server.pem").is_file()
    assert (stage / "certs" / "artemis-server-key.pem").is_file()
    assert (stage / wheel.name).read_bytes() == b"reviewed-wheel"


def test_prepare_stage_rejects_changed_wheel(tmp_path: Path):
    bundle, wheel = _bundle(tmp_path)
    package = _package(wheel)
    wheel.write_bytes(b"tampered")
    installer = WindowsCimBootstrapInstaller(
        host="Artemis",
        credential_user=r"Artemis\Administrator",
        bundle_directory=bundle,
        wheel_path=wheel,
        controller_stage_directory=tmp_path / "stage",
        remote_stage_path=r"H:\Fleet\Artemis",
        node_id=NODE_ID,
        launcher=lambda *_: None,
    )
    with pytest.raises(RuntimeError, match="hash"):
        installer.prepare_stage(package)


def test_install_requires_matching_verified_remote_receipt(tmp_path: Path):
    bundle, wheel = _bundle(tmp_path)
    stage = tmp_path / "stage"

    def launcher(host, user, installer_path):
        assert host == "Artemis"
        assert user == r"Artemis\Administrator"
        assert installer_path.endswith(r"\install.ps1")
        (stage / "bootstrap-receipt.json").write_text(
            json.dumps(
                {
                    "status": "verified",
                    "host_id": "Artemis",
                    "node_id": str(NODE_ID),
                    "package_sha256": sha256_file(wheel),
                    "process_id": 1234,
                    "listen_port": 7443,
                    "python_version": "Python 3.14.2",
                }
            ),
            encoding="utf-8",
        )

    installer = WindowsCimBootstrapInstaller(
        host="Artemis",
        credential_user=r"Artemis\Administrator",
        bundle_directory=bundle,
        wheel_path=wheel,
        controller_stage_directory=stage,
        remote_stage_path=r"H:\Fleet\Artemis",
        node_id=NODE_ID,
        launcher=launcher,
        timeout_seconds=1,
    )
    receipt = installer.install(_candidate(), _package(wheel))
    assert receipt.verified is True
    assert receipt.sha256 == sha256_file(wheel)


def test_install_rejects_wrong_node_receipt(tmp_path: Path):
    bundle, wheel = _bundle(tmp_path)
    stage = tmp_path / "stage"

    def launcher(*_):
        (stage / "bootstrap-receipt.json").write_text(
            json.dumps(
                {
                    "status": "verified",
                    "host_id": "Artemis",
                    "node_id": "11111111-1111-1111-1111-111111111111",
                    "package_sha256": sha256_file(wheel),
                    "process_id": 1234,
                    "listen_port": 7443,
                    "python_version": "Python 3.14.2",
                }
            ),
            encoding="utf-8",
        )

    installer = WindowsCimBootstrapInstaller(
        host="Artemis",
        credential_user=r"Artemis\Administrator",
        bundle_directory=bundle,
        wheel_path=wheel,
        controller_stage_directory=stage,
        remote_stage_path=r"H:\Fleet\Artemis",
        node_id=NODE_ID,
        launcher=launcher,
        timeout_seconds=1,
    )
    with pytest.raises(RuntimeError, match="node identity"):
        installer.install(_candidate(), _package(wheel))
