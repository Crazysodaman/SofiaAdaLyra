"""D-007 isolated source-level socket ACL contract tests.

Run: python test/fixtures/aegis_debian_vm/socket_contract_check.py

Extract the exact _native_management_socket function from the real guest
probe AST; never import/execute that script because it is deliberately guarded
by an explicit disposable VM kernel marker. No systemd, privileged OS state,
socket, archive extraction, production service or Core is touched.
This is a unit contract, NOT installed-host integration evidence.
"""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
import stat
from types import SimpleNamespace as NS
import unittest


class FakePath:
    def __init__(self, *segments):
        self.path = PurePosixPath(*map(str, segments))

    def __truediv__(self, segment):
        return FakePath(self.path, segment)

    def __str__(self):
        return str(self.path)

    def read_text(self):
        if str(self.path).endswith("/status"):
            return "Name:\tpython\nGroups:\t1002 1003\nState:\tS (sleeping)\n"
        raise AssertionError("no file read permitted outside synthetic /proc status")


def actual_function(*, runtime="aegis", mode=0o700, directory_gid=None,
                    socket_mode=None, socket_gid=None, worker_group=True,
                    uid=1001, unit_user="aegis"):
    """Construct a mock environment around the ACTUAL guest source function."""
    source_path = Path(__file__).with_name("probe.py")
    code = ast.parse(source_path.read_text(encoding="utf-8"))
    found = [n for n in code.body if isinstance(n, ast.FunctionDef)
             and n.name == "_native_management_socket"]
    assert len(found) == 1, "exact source function moved or duplicated"
    program = compile(ast.fix_missing_locations(
        ast.Module(body=found, type_ignores=[])), str(source_path), "exec")
    runtime_mode = mode
    expected_directory_gid = 1002 if directory_gid is None else directory_gid
    expected_socket_mode = (0o600 if mode == 0o700 else 0o660) if socket_mode is None else socket_mode
    expected_socket_gid = expected_directory_gid if socket_gid is None else socket_gid

    class ProcPath(FakePath):
        def read_text(self):
            if str(self.path) == "/proc/456/status":
                groups = "1002 1003" if worker_group else "1002"
                return f"Name:\tpython\nGroups:\t{groups}\n"
            raise AssertionError("unexpected file read")

    def lstat(path):
        item = str(path)
        if item == "/run/" + runtime:
            return NS(st_mode=stat.S_IFDIR | runtime_mode,
                      st_uid=uid, st_gid=expected_directory_gid)
        if item == f"/run/{runtime}/mgmt-3.sock":
            return NS(st_mode=stat.S_IFSOCK | expected_socket_mode,
                      st_uid=uid, st_gid=expected_socket_gid)
        raise AssertionError("unexpected filesystem inspection: " + item)

    def command(*args):
        assert args[:3] == ("systemctl", "show", "aegis-platform.service")
        return "\n".join([
            "User=" + unit_user,
            "Group=aegis",
            "RuntimeDirectory=" + runtime,
            "RuntimeDirectoryMode=" + format(runtime_mode, "04o"),
        ]) + "\n"

    env = {
        "Path": ProcPath, "UNIT": "aegis-platform.service",
        "stat": stat, "os": NS(lstat=lstat),
        "pwd": NS(getpwnam=lambda name: NS(pw_uid=1001, pw_gid=1002)),
        "grp": NS(getgrnam=lambda name: NS(gr_gid=1003)),
        "command": command,
    }
    exec(program, env)
    return env["_native_management_socket"]


class NativeManagementSocketContract(unittest.TestCase):
    ready = {"management_listening": True, "generation": 3, "worker_pid": 456}

    def test_private_installer_runtime(self):
        self.assertEqual(str(actual_function()(self.ready)), "/run/aegis/mgmt-3.sock")

    def test_enrolled_explicit_supplementary_group(self):
        read = actual_function(runtime="aegis-platform", mode=0o750,
                               directory_gid=1003)
        self.assertEqual(str(read(self.ready)), "/run/aegis-platform/mgmt-3.sock")

    def test_unreviewed_runtime_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(runtime="tmp", mode=0o700)(self.ready)

    def test_group_exposure_on_private_runtime_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(runtime="aegis", mode=0o750, directory_gid=1003)(self.ready)

    def test_installer_runtime_world_access_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(mode=0o755)(self.ready)

    def test_service_owner_wrong_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(uid=9999)(self.ready)

    def test_private_wrong_runtime_gid_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(directory_gid=9999)(self.ready)

    def test_enrolled_socket_gid_mismatch_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(runtime="aegis-platform", mode=0o750,
                            directory_gid=1003, socket_gid=1002)(self.ready)

    def test_private_world_socket_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(socket_mode=0o666)(self.ready)

    def test_enrolled_worker_not_member_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(runtime="aegis-platform", mode=0o750,
                            directory_gid=1003, worker_group=False)(self.ready)

    def test_forged_unit_user_denied(self):
        with self.assertRaises(AssertionError):
            actual_function(unit_user="root")(self.ready)

    def test_missing_listener_ready_denied(self):
        with self.assertRaises(AssertionError):
            actual_function()({**self.ready, "management_listening": False})

    def test_forged_boolean_generation_denied(self):
        with self.assertRaises(AssertionError):
            actual_function()({**self.ready, "generation": True})


if __name__ == "__main__":
    unittest.main(verbosity=2)
