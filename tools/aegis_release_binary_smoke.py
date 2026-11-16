"""Opt-in live smoke for a test-signed Aegis Platform release *binary*.

This tool is deliberately NOT collected by pytest.  It proves process and
health behavior of the exact release-built Rust service against the release
wheels, using a disposable virtual environment and disposable Platform state.

It never installs an OS service, never touches production state, never uses
the network, and never copies private key material.  The bundle is verified
with its own released verifier and a caller-supplied trusted public key.

Example::

    python tools/aegis_release_binary_smoke.py \
        --release-dir .../relcand-.../windows-x86_64 \
        --trusted-public-key .../aegis-test-disposable.key.pub.pem \
        --signer-key-id aegis-test-disposable \
        --expected-source-sha 662b9b25... \
        --evidence .../evidence.json

Exit status 0 means the release binary reached READY, survived continued
health heartbeats, denied a duplicate supervisor, shut down cleanly via a
graceful console control event, and advanced its RUN generation on restart.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

SERVICE_SCHEMA = "aegis.platform.service-control.v1"
EVIDENCE_SCHEMA = "aegis.platform.release-binary-smoke.v1"
WINDOWS_TARGET = "windows-x86_64"
CREATE_NEW_PROCESS_GROUP = 0x00000200
CTRL_BREAK_EVENT = 1
STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# A released Platform wheel declares these runtime prerequisites.  They are
# seeded offline from an already-installed host environment; no additional
# sofia wheel (and specifically no Core or Ollama) is copied or installed.
_DEPENDENCY_PREFIXES = (
    "cryptography", "cffi", "pycparser", "tzdata",
    "win32", "win32com", "win32comext", "pywin32_system32",
)
_DEPENDENCY_FILES = {"pywin32.pth", "pywin32.version.txt"}
_FORBIDDEN_PREFIXES = ("sofia", "ollama")


class SmokeError(RuntimeError):
    pass


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def select_dependency_entries(source: Path) -> list[Path]:
    """Return only local runtime prerequisite entries from ``source``.

    Core/Ollama and every other unrelated package is excluded by construction.
    """
    selected: list[Path] = []
    if not source.is_dir():
        return selected
    for entry in source.iterdir():
        name = entry.name
        lowered = name.lower()
        if lowered.startswith(_FORBIDDEN_PREFIXES):
            continue
        if name in _DEPENDENCY_FILES:
            selected.append(entry)
            continue
        if lowered.endswith(".dist-info") and lowered.startswith(_DEPENDENCY_PREFIXES):
            selected.append(entry)
            continue
        if name.startswith(_DEPENDENCY_PREFIXES):
            selected.append(entry)
            continue
        if lowered.startswith("_cffi_backend.") and lowered.endswith(".pyd"):
            selected.append(entry)
    return sorted(selected, key=lambda item: item.name.lower())


def build_binary_args(
    binary: Path, python: Path, identity_home: Path, state: Path,
    platform_id: str, public_key_sha256: str,
) -> list[str]:
    """Exact ordered argv accepted by the Rust service configuration parser."""
    return [
        str(binary), "--python", str(python),
        "--identity-home", str(identity_home), "--state", str(state),
        "--platform-id", platform_id,
        "--public-key-sha256", public_key_sha256,
    ]


def validate_ready(reply: object, *, process_pid: int, platform_id: str) -> dict:
    """Bind the supervisor READY line to this process and installed Platform."""
    if not isinstance(reply, dict):
        raise SmokeError("readiness line is not a JSON object")
    if reply.get("schema") != SERVICE_SCHEMA:
        raise SmokeError("readiness schema differs")
    if reply.get("phase") != "ready":
        raise SmokeError("service did not report ready phase")
    if reply.get("platform_id") != platform_id:
        raise SmokeError("readiness platform id differs")
    generation = reply.get("generation")
    if type(generation) is not int or generation < 1:
        raise SmokeError("readiness generation is not a positive integer")
    if reply.get("supervisor_pid") != process_pid:
        raise SmokeError("readiness supervisor pid differs")
    worker_pid = reply.get("worker_pid")
    if type(worker_pid) is not int or worker_pid <= 0 or worker_pid == process_pid:
        raise SmokeError("readiness worker pid is invalid")
    if reply.get("operator_stop") is not False:
        raise SmokeError("operator STOP is active")
    if reply.get("management_listening") is not True:
        raise SmokeError("authenticated management listener is not ready")
    return {
        "schema": reply["schema"],
        "phase": reply["phase"],
        "platform_id": reply["platform_id"],
        "generation": generation,
        "supervisor_pid": reply["supervisor_pid"],
        "worker_pid": worker_pid,
        "operator_stop": reply["operator_stop"],
        "management_listening": reply["management_listening"],
    }


def validate_restart_generation(first: dict, second: dict) -> None:
    if second["generation"] <= first["generation"]:
        raise SmokeError(
            "restart generation did not advance "
            f"({first['generation']} -> {second['generation']})"
        )


class _Collector:
    def __init__(self, stream) -> None:
        self.lines: list[str] = []
        self.ready: dict | None = None
        self._event = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(stream,), daemon=True)
        self._thread.start()

    def _run(self, stream) -> None:
        for line in stream:
            text = line.rstrip("\n")
            self.lines.append(text)
            try:
                value = json.loads(text)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict) and value.get("phase") == "ready" and self.ready is None:
                self.ready = value
                self._event.set()
        self._event.set()

    def wait_ready(self, timeout: float) -> dict | None:
        self._event.wait(max(0.0, timeout))
        return self.ready

    def join(self, timeout: float = 5.0) -> None:
        self._thread.join(timeout)


def _run(cmd: list[str], *, env: dict | None = None, timeout: float = 300) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SmokeError(f"command failed to run: {cmd[0]}: {exc}") from exc


def _require_success(proc: subprocess.CompletedProcess, label: str) -> str:
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-1200:]
        raise SmokeError(f"{label} failed with exit {proc.returncode}: {detail}")
    return proc.stdout


def _python_version(python: Path) -> str:
    proc = _run([str(python), "-I", "-c", "import sys;print(sys.version.split()[0])"])
    return _require_success(proc, "python version").strip()


def _site_packages(python: Path) -> Path:
    proc = _run([
        str(python), "-I", "-c",
        "import sysconfig;print(sysconfig.get_paths()['purelib'])",
    ])
    return Path(_require_success(proc, "site-packages discovery").strip())


def _create_venv(host_python: Path, destination: Path) -> Path:
    proc = _run([str(host_python), "-m", "venv", str(destination)], timeout=300)
    _require_success(proc, "venv creation")
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise SmokeError(f"disposable venv interpreter missing: {python}")
    return python


def _pip_env() -> dict:
    env = os.environ.copy()
    env.update({
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        "PIP_NO_CACHE_DIR": "1",
    })
    return env


def _bundle_wheels(assets: Path) -> tuple[Path, Path]:
    sdk = sorted(assets.glob("sofia_sdk-*.whl"))
    platform = sorted(assets.glob("sofia_platform-*.whl"))
    if len(sdk) != 1 or len(platform) != 1:
        raise SmokeError("bundle must contain exactly one SDK and one Platform wheel")
    return sdk[0], platform[0]


def _install_bundle_wheels(python: Path, sdk: Path, platform: Path) -> dict:
    proc = _run([
        str(python), "-m", "pip", "install", "--no-index", "--no-deps",
        "--disable-pip-version-check", "--no-input", str(sdk), str(platform),
    ], env=_pip_env(), timeout=300)
    _require_success(proc, "offline bundle wheel install")
    listing = _run([
        str(python), "-m", "pip", "list", "--format=json",
        "--disable-pip-version-check",
    ], env=_pip_env())
    _require_success(listing, "pip list")
    return {"pip_install_stdout": proc.stdout.strip(), "pip_list": json.loads(listing.stdout)}


def _seed_dependencies(source: Path, destination: Path) -> list[str]:
    copied: list[str] = []
    for entry in select_dependency_entries(source):
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)
        copied.append(entry.name)
    return copied


_IMPORT_PROBE = r"""
import importlib.util as u, json
result = {
    "sofia_sdk_present": u.find_spec("sofia.sdk") is not None,
    "sofia_core_present": u.find_spec("sofia.core") is not None,
    "ollama_present": u.find_spec("ollama") is not None,
    "platform_service_import": False,
    "win32security_import": False,
}
try:
    import sofia.platform.run.platform_service  # noqa: F401
    result["platform_service_import"] = True
except Exception as exc:
    result["platform_service_error"] = type(exc).__name__ + ": " + str(exc)
try:
    import win32security  # noqa: F401
    result["win32security_import"] = True
except Exception as exc:
    result["win32security_error"] = type(exc).__name__ + ": " + str(exc)
print(json.dumps(result, sort_keys=True))
"""


def _probe_import_isolation(python: Path) -> dict:
    proc = _run([str(python), "-I", "-c", _IMPORT_PROBE], timeout=120)
    return json.loads(_require_success(proc, "isolated import probe"))


_PROVISION = r"""
import json
import sys
from pathlib import Path

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.state.private_file import ensure_owner_private_directory

root = Path(sys.argv[1]).absolute()
ensure_owner_private_directory(root)
identity_home = root / "identity"
identity = InstallationIdentityStore(identity_home).initialize()
state = root / "platform.db"
PlatformLocalStore(
    state,
    roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
    host_identity=identity.identity.canonical_uuid,
    create=True,
)
print(json.dumps({
    "platform_id": identity.identity.canonical_uuid,
    "serial": identity.identity.serial,
    "public_key_sha256": identity.public_key_sha256,
    "identity_home": str(identity_home),
    "state": str(state),
}, sort_keys=True))
"""


def _provision(python: Path, work_root: Path, run_root: Path) -> dict:
    script = work_root / "_provision_platform_state.py"
    script.write_text(_PROVISION, encoding="utf-8")
    proc = _run([str(python), "-I", str(script), str(run_root)], timeout=120)
    return json.loads(_require_success(proc, "disposable identity/state provisioning"))


def _verify_release(
    python: Path, release_dir: Path, *, trusted_public_key: Path | None,
    signer_key_id: str | None, expected_source_sha: str, target: str,
    minimum_revision: int,
) -> dict:
    if trusted_public_key is None:
        return {"result": "UNVERIFIED_NO_TRUST_ROOT", "exit_code": None}
    signature = json.loads((release_dir / "release-signature.json").read_text(encoding="utf-8"))
    args = [
        str(python), "-I", "-m", "sofia.platform.ops.platform_release",
        "--manifest", str(release_dir / "release-manifest.json"),
        "--assets-root", str(release_dir / "assets"),
        "--trusted-public-key", str(trusted_public_key),
        "--signer-key-id", signer_key_id or signature["signer_key_id"],
        "--signature", signature["signature_b64"],
        "--expected-source-sha", expected_source_sha,
        "--target", target,
        "--minimum-revision", str(minimum_revision),
    ]
    proc = _run(args, timeout=180)
    parsed: dict
    try:
        parsed = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise SmokeError(
            "release verifier produced no JSON: "
            + (proc.stderr or proc.stdout or "").strip()[-800:]
        ) from exc
    parsed["exit_code"] = proc.returncode
    if proc.returncode != 0 or parsed.get("result") != "VERIFIED_PLATFORM_RELEASE_BYTES":
        raise SmokeError(f"release verification denied: {_canonical_json(parsed)}")
    return parsed


def _spawn(argv: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
        creationflags=CREATE_NEW_PROCESS_GROUP,
    )


def _worker_alive(pid: int) -> bool:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _send_graceful_control(pid: int) -> bool:
    return bool(ctypes.windll.kernel32.GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid))


def _stop_service(proc: subprocess.Popen, collector: _Collector, timeout: float) -> dict:
    if proc.poll() is None:
        if not _send_graceful_control(proc.pid):
            raise SmokeError("could not send graceful console control event")
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise SmokeError("service did not shut down within its drain deadline")
    collector.join()
    stderr = proc.stderr.read() if proc.stderr is not None else ""
    return {"exit_code": code, "stderr": stderr, "stdout_lines": list(collector.lines)}


def _start_and_ready(
    binary: Path, python: Path, identity_home: Path, state: Path,
    platform_id: str, public_key_sha256: str, timeout: float,
) -> tuple[subprocess.Popen, _Collector, dict]:
    argv = build_binary_args(
        binary, python, identity_home, state, platform_id, public_key_sha256,
    )
    proc = _spawn(argv)
    collector = _Collector(proc.stdout)
    reply = collector.wait_ready(timeout)
    if reply is None:
        proc.kill()
        proc.wait()
        collector.join()
        stderr = proc.stderr.read() if proc.stderr is not None else ""
        raise SmokeError(f"service did not reach READY: {stderr.strip()[-800:]}")
    try:
        ready = validate_ready(reply, process_pid=proc.pid, platform_id=platform_id)
    except SmokeError:
        proc.kill()
        proc.wait()
        raise
    return proc, collector, ready


_SCM_PROBE = r"""
import json
result = {}
try:
    import win32service
except Exception as exc:
    print(json.dumps({"import_error": type(exc).__name__ + ": " + str(exc)}))
    raise SystemExit(0)
for name, accessor in (
    ("CREATE_SERVICE", lambda: win32service.SC_MANAGER_CREATE_SERVICE),
    ("ALL_ACCESS", lambda: win32service.SC_MANAGER_ALL_ACCESS),
):
    try:
        handle = win32service.OpenSCManager(None, None, accessor())
    except Exception as exc:
        result[name] = {
            "ok": False,
            "type": type(exc).__name__,
            "winerror": getattr(exc, "winerror", None),
            "message": str(exc),
        }
    else:
        result[name] = {"ok": True}
        win32service.CloseServiceHandle(handle)
print(json.dumps(result, sort_keys=True))
"""


def _scm_probe(python: Path) -> dict:
    proc = _run([str(python), "-I", "-c", _SCM_PROBE], timeout=120)
    return json.loads(_require_success(proc, "read-only SCM probe"))


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _execute(args: argparse.Namespace) -> tuple[dict, Path, Path]:
    release_dir = args.release_dir.absolute()
    manifest_path = release_dir / "release-manifest.json"
    signature_path = release_dir / "release-signature.json"
    assets = release_dir / "assets"
    binary = assets / "aegis-platform-service.exe"
    for required in (manifest_path, signature_path, assets, binary):
        if not required.exists():
            raise SmokeError(f"release bundle is incomplete: missing {required}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "aegis.platform.release.v1":
        raise SmokeError("unexpected release manifest schema")
    if manifest.get("target") != WINDOWS_TARGET:
        raise SmokeError("this smoke supports only the windows-x86_64 release target")
    expected_source_sha = args.expected_source_sha or manifest["source_sha"]
    target = args.target or manifest["target"]
    signature = json.loads(signature_path.read_text(encoding="utf-8"))
    signer_key_id = args.signer_key_id or signature.get("signer_key_id")

    if args.work_root is None:
        work_root = Path(tempfile.mkdtemp(prefix="aegis-release-binary-smoke-"))
    else:
        work_root = args.work_root.absolute()
        if work_root.exists() and any(work_root.iterdir()):
            raise SmokeError(f"work root must be absent or empty: {work_root}")
        work_root.mkdir(parents=True, exist_ok=True)
    venv_dir = work_root / "venv"
    run_root = work_root / "run"

    evidence: dict = {
        "schema": EVIDENCE_SCHEMA,
        "created_at": _utc(),
        "result": "FAILED",
        "release_dir": str(release_dir),
        "release_id": manifest.get("release_id"),
        "source_sha": manifest.get("source_sha"),
        "target": manifest.get("target"),
        "version": manifest.get("version"),
        "revision": manifest.get("revision"),
        "manifest_sha256": _sha256_file(manifest_path),
        "binary": {
            "path": str(binary),
            "sha256": _sha256_file(binary),
            "size_bytes": binary.stat().st_size,
            "expected_sha256": next(
                asset["reference"]["sha256"] for asset in manifest["assets"]
                if asset["kind"] == "service"
            ),
        },
        "network_used": False,
        "os_service_created": False,
        "production_state_touched": False,
    }
    evidence_path = (
        args.evidence.absolute() if args.evidence is not None
        else work_root.with_name(work_root.name + "-evidence.json")
    )

    try:
        if evidence["binary"]["sha256"] != evidence["binary"]["expected_sha256"]:
            raise SmokeError("release service binary digest differs from manifest")
        host_python = args.host_python.absolute()
        if not host_python.is_file():
            raise SmokeError(f"host python is unavailable: {host_python}")
        venv_python = _create_venv(host_python, venv_dir)
        sdk, platform_wheel = _bundle_wheels(assets)
        installed = _install_bundle_wheels(venv_python, sdk, platform_wheel)
        dependency_source = (
            args.dependency_source.absolute() if args.dependency_source is not None
            else _site_packages(host_python)
        )
        seeded = _seed_dependencies(dependency_source, _site_packages(venv_python))
        isolation = _probe_import_isolation(venv_python)
        if isolation.get("sofia_core_present") is not False:
            raise SmokeError("disposable venv unexpectedly exposes sofia.core")
        if isolation.get("ollama_present") is not False:
            raise SmokeError("disposable venv unexpectedly exposes ollama")
        if isolation.get("sofia_sdk_present") is not True:
            raise SmokeError("released SDK wheel is not importable")
        if isolation.get("platform_service_import") is not True:
            raise SmokeError(
                "released Platform service module is not importable: "
                + str(isolation.get("platform_service_error"))
            )
        if isolation.get("win32security_import") is not True:
            raise SmokeError(
                "offline Windows ACL dependency is not importable: "
                + str(isolation.get("win32security_error"))
            )
        verification = _verify_release(
            venv_python, release_dir,
            trusted_public_key=(
                args.trusted_public_key.absolute()
                if args.trusted_public_key is not None else None
            ),
            signer_key_id=signer_key_id,
            expected_source_sha=expected_source_sha,
            target=target,
            minimum_revision=args.minimum_revision,
        )
        provisioned = _provision(venv_python, work_root, run_root)
        platform_id = provisioned["platform_id"]
        public_key_sha256 = provisioned["public_key_sha256"]
        identity_home = Path(provisioned["identity_home"])
        state = Path(provisioned["state"])

        first_proc, first_collector, first_ready = _start_and_ready(
            binary, venv_python, identity_home, state, platform_id,
            public_key_sha256, args.ready_timeout,
        )
        first_worker_alive = _worker_alive(first_ready["worker_pid"])
        time.sleep(max(0.0, args.status_observation_seconds))
        still_running = first_proc.poll() is None
        worker_still_alive = _worker_alive(first_ready["worker_pid"])
        if not still_running or not worker_still_alive:
            raise SmokeError(
                "service did not remain healthy during continued status heartbeats"
            )

        duplicate = _spawn(build_binary_args(
            binary, venv_python, identity_home, state, platform_id,
            public_key_sha256,
        ))
        try:
            duplicate_out, duplicate_err = duplicate.communicate(timeout=args.duplicate_timeout)
        except subprocess.TimeoutExpired:
            duplicate.kill()
            duplicate_out, duplicate_err = duplicate.communicate()
            raise SmokeError("duplicate supervisor was not denied")
        duplicate_denied = duplicate.returncode != 0
        if not duplicate_denied:
            raise SmokeError("duplicate supervisor was allowed to coexist")

        first_stop = _stop_service(first_proc, first_collector, args.shutdown_timeout)
        if first_stop["exit_code"] != 0:
            raise SmokeError(
                f"first service did not shut down cleanly: {first_stop['exit_code']}"
            )
        if detail := first_stop["stderr"].strip():
            raise SmokeError(f"first service wrote unexpected stderr: {detail}")

        second_proc, second_collector, second_ready = _start_and_ready(
            binary, venv_python, identity_home, state, platform_id,
            public_key_sha256, args.ready_timeout,
        )
        validate_restart_generation(first_ready, second_ready)
        second_worker_alive = _worker_alive(second_ready["worker_pid"])
        second_stop = _stop_service(second_proc, second_collector, args.shutdown_timeout)
        if second_stop["exit_code"] != 0:
            raise SmokeError(
                f"restarted service did not shut down cleanly: {second_stop['exit_code']}"
            )
        if detail := second_stop["stderr"].strip():
            raise SmokeError(f"restarted service wrote unexpected stderr: {detail}")

        scm = _scm_probe(venv_python)
        scm_denied = all(
            scm.get(name, {}).get("ok") is False
            for name in ("CREATE_SERVICE", "ALL_ACCESS")
        )
        blockers = []
        if scm_denied:
            errors = {
                name: scm.get(name, {}).get("winerror")
                for name in ("CREATE_SERVICE", "ALL_ACCESS")
            }
            blockers.append(
                "installed Windows SCM service remains blocked: OpenSCManager "
                f"denied with winerror {errors['CREATE_SERVICE']} "
                f"(ALL_ACCESS winerror {errors['ALL_ACCESS']}); no service was created"
            )

        evidence.update({
            "result": "LIVE_SERVICE_SMOKE_PASSED",
            "verification": verification,
            "venv": {
                "python": str(venv_python),
                "python_version": _python_version(venv_python),
                "bundle_wheels_installed": [sdk.name, platform_wheel.name],
                "bundle_wheels_pip_install": installed["pip_install_stdout"],
                "bundle_wheels_pip_list": installed["pip_list"],
                "dependency_source": str(dependency_source),
                "dependency_seed": seeded,
                "dependency_seed_is_offline": True,
                "network_used": False,
                "import_isolation": isolation,
            },
            "identity": {
                "platform_id": platform_id,
                "serial": provisioned["serial"],
                "public_key_sha256": public_key_sha256,
                "identity_home": str(identity_home),
                "state": str(state),
            },
            "first_run": {
                **first_ready,
                "worker_alive_at_ready": first_worker_alive,
                "still_running_after_status_heartbeats": still_running,
                "worker_alive_after_status_heartbeats": worker_still_alive,
                "shutdown": first_stop,
                "clean_shutdown": True,
            },
            "duplicate_supervisor": {
                "exit_code": duplicate.returncode,
                "stdout": duplicate_out,
                "stderr": duplicate_err,
                "denied": duplicate_denied,
            },
            "restart": {
                **second_ready,
                "generation_advanced": True,
                "previous_generation": first_ready["generation"],
                "worker_alive_at_ready": second_worker_alive,
                "shutdown": second_stop,
                "clean_shutdown": True,
            },
            "control_surface": {
                "external_request_channel": "none; supervisor owns private child pipes",
                "health_observed_via": "continued internal status heartbeat replies",
                "graceful_control": "GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT)",
            },
            "scm_probe": scm,
            "scm_service_created": False,
            "blockers": blockers,
        })
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        keep = args.keep_work_root
        with contextlib.suppress(ValueError):
            evidence_path.relative_to(work_root)
            keep = True
        if not keep:
            shutil.rmtree(work_root, ignore_errors=True)
    return evidence, evidence_path, work_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True,
                        help="release bundle root containing manifest/assets")
    parser.add_argument("--trusted-public-key", type=Path,
                        help="test public Ed25519 PEM; omit to record UNVERIFIED")
    parser.add_argument("--signer-key-id")
    parser.add_argument("--expected-source-sha")
    parser.add_argument("--target", default=None)
    parser.add_argument("--minimum-revision", type=int, default=1)
    parser.add_argument("--host-python", type=Path, default=Path(sys.executable),
                        help="host interpreter used to create the disposable venv")
    parser.add_argument("--dependency-source", type=Path,
                        help="local site-packages used to seed runtime prerequisites")
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--keep-work-root", action="store_true")
    parser.add_argument("--ready-timeout", type=float, default=20.0)
    parser.add_argument("--status-observation-seconds", type=float, default=3.0)
    parser.add_argument("--duplicate-timeout", type=float, default=25.0)
    parser.add_argument("--shutdown-timeout", type=float, default=40.0)
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("the release binary smoke requires Windows")
    try:
        evidence, evidence_path, _ = _execute(args)
    except SmokeError as exc:
        print(json.dumps({"result": "FAILED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({
        "result": evidence["result"],
        "evidence": str(evidence_path),
        "platform_id": evidence["identity"]["platform_id"],
        "first_generation": evidence["first_run"]["generation"],
        "restart_generation": evidence["restart"]["generation"],
        "first_pid": evidence["first_run"]["supervisor_pid"],
        "duplicate_denied": evidence["duplicate_supervisor"]["denied"],
        "scm": evidence["scm_probe"],
        "blockers": evidence["blockers"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
