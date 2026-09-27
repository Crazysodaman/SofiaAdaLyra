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
    assert "Get-CimInstance Win32_Process" in script
    assert '$_ .CommandLine' not in script
    assert 'sofia.distributed.agent_main' in script
    assert "Stop-Process -Id $ManagedProcess.ProcessId" in script
    assert "Stop-Process -Id $StartedAgent.Id" in script
    assert "icacls.exe" in script
    assert "*S-1-5-18:F" in script
    assert "*S-1-5-32-544:F" in script


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
    active_stage = generated.parent

    assert active_stage.parent == stage.parent
    assert active_stage.name.startswith(stage.name + "-")
    assert generated == active_stage / "install.ps1"
    assert (active_stage / "agent.json").is_file()
    staged_config = json.loads((active_stage / "agent.json").read_text(encoding="utf-8"))
    assert staged_config["listen_port"] == 7443
    assert (active_stage / "certs" / "fleet-ca.pem").is_file()
    assert (active_stage / "certs" / "artemis-server.pem").is_file()
    assert (active_stage / "certs" / "artemis-server-key.pem").is_file()
    assert (active_stage / wheel.name).read_bytes() == b"reviewed-wheel"


def test_prepare_stage_overrides_agent_config_port(tmp_path: Path):
    bundle, wheel = _bundle(tmp_path)
    (bundle / "agent.json").write_text(
        json.dumps({"listen_port": 7443}),
        encoding="utf-8",
    )
    installer = WindowsCimBootstrapInstaller(
        host="Artemis",
        credential_user=r"Artemis\Administrator",
        bundle_directory=bundle,
        wheel_path=wheel,
        controller_stage_directory=tmp_path / "stage",
        remote_stage_path=r"H:\Fleet\Artemis",
        node_id=NODE_ID,
        listen_port=9999,
        launcher=lambda *_: None,
    )
    generated = installer.prepare_stage(_package(wheel))
    staged = json.loads((generated.parent / "agent.json").read_text(encoding="utf-8"))
    assert staged["listen_port"] == 9999


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
        active_stage = installer._active_controller_stage_directory
        assert active_stage is not None
        (active_stage / "bootstrap-receipt.json").write_text(
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
    assert installer._active_controller_stage_directory is not None
    assert not installer._active_controller_stage_directory.exists()


def test_install_rejects_wrong_node_receipt(tmp_path: Path):
    bundle, wheel = _bundle(tmp_path)
    stage = tmp_path / "stage"

    def launcher(*_):
        active_stage = installer._active_controller_stage_directory
        assert active_stage is not None
        (active_stage / "bootstrap-receipt.json").write_text(
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
