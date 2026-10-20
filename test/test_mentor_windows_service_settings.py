"""No real Windows SCM operations during MENTOR service-setting tests."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sofia.mentor.__main__ import main
from sofia.mentor.windows_service_settings import (
    FLAG_OPTION, ROOT_OPTION, SERVICE, MentorServiceSettingsError,
    configure_custom_service_settings, decode_options,
    disable_custom_service_settings, load_custom_service_settings,
    service_settings_status, validate_root, _read_registry_option,
    _reject_service_network_path,
)


class MentorServiceSettingsTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        profile = self.root / "src/sofia/personality/personality.json"
        monitor = self.root / "src/sofia/mentor/behavior_monitor.py"
        profile.parent.mkdir(parents=True)
        monitor.parent.mkdir(parents=True)
        profile.write_text('{"name":"Sofía","traits":[]}', encoding="utf-8")
        monitor.write_text("# source marker", encoding="utf-8")

    def test_legacy_unconfigured_service_stays_disabled(self):
        config = decode_options("", "")
        self.assertFalse(config.enabled)
        self.assertEqual(config.environment()["SOFIA_MENTOR_BEHAVIOR_ENABLED"], "false")
        self.assertNotIn("SOFIA_MENTOR_SOURCE_ROOT", config.environment())

    def test_enabled_validates_root_and_exposes_only_two_variables(self):
        settings = decode_options("true", str(self.root))
        self.assertTrue(settings.enabled)
        env = settings.environment()
        self.assertEqual(set(env), {
            "SOFIA_MENTOR_BEHAVIOR_ENABLED", "SOFIA_MENTOR_SOURCE_ROOT"
        })
        self.assertEqual(env["SOFIA_MENTOR_BEHAVIOR_ENABLED"], "true")
        self.assertEqual(Path(env["SOFIA_MENTOR_SOURCE_ROOT"]), self.root.resolve())

    def test_invalid_settings_are_not_enabled(self):
        for flag in ("perhaps", "TrueX", "enabled", "secret"):
            with self.assertRaises(MentorServiceSettingsError):
                decode_options(flag, str(self.root))
        with self.assertRaises(MentorServiceSettingsError):
            decode_options("true", str(self.root / "missing"))

    def test_plan_never_calls_scm(self):
        answer = configure_custom_service_settings(root=self.root, apply=False,
            setter=lambda *a: self.fail("must not write registry"))
        self.assertEqual(answer["operation"], "preview")
        self.assertFalse(answer["will_restart"])
        self.assertFalse(answer["will_change_state_path"])

    def test_apply_sets_source_first_then_enable_no_restart(self):
        written = []
        def save(*args):
            written.append(args)
        result = configure_custom_service_settings(
            root=self.root, apply=True, setter=save,
        )
        self.assertEqual(written[0], (SERVICE, ROOT_OPTION, str(self.root.resolve())))
        self.assertEqual(written[1], (SERVICE, FLAG_OPTION, "true"))
        self.assertEqual(result["operation"], "configured_not_restarted")
        self.assertFalse(result["will_restart"])
        self.assertFalse(result["will_change_state_path"])

    def test_disable_only_changes_mentor_flag(self):
        writes = []
        disabled = disable_custom_service_settings(
            apply=True, setter=lambda *args: writes.append(args),
        )
        self.assertEqual(writes, [(SERVICE, FLAG_OPTION, "false")])
        self.assertFalse(disabled["will_restart"])

    def test_read_only_status_refuses_running_service_certification(self):
        values = {FLAG_OPTION: "true", ROOT_OPTION: str(self.root)}
        def get(service, key, default):
            self.assertEqual(service, SERVICE)
            return values.get(key, default)
        report = service_settings_status(getter=get)
        self.assertTrue(report["configured_enabled"])
        self.assertEqual(report["running_service_has_reloaded_settings"], "unknown")
        self.assertEqual(report["running_release_has_monitor_code"], "unknown")
        self.assertEqual(report["runtime_review_count"], "unknown")

    def test_root_must_be_real_checkout_not_link_to_elsewhere(self):
        with self.assertRaises(MentorServiceSettingsError):
            validate_root(self.root / "none")
        link = Path(self.tmp.name) / "alias"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(MentorServiceSettingsError):
            validate_root(link)

    def test_read_only_registry_reader_does_not_create_keys(self):
        class Key:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        class ReadOnlyRegistry:
            HKEY_LOCAL_MACHINE = "HKLM"
            KEY_QUERY_VALUE = 1
            def __init__(self):
                self.opened = []
            def OpenKey(self, hive, path, reserved, access):
                self.opened.append((hive, path, reserved, access))
                return Key()
            def QueryValueEx(self, key, option):
                return ("true" if option == FLAG_OPTION else str(self_root), 1)
        self_root = self.root
        reg = ReadOnlyRegistry()
        self.assertEqual(
            _read_registry_option(SERVICE, FLAG_OPTION, "", registry=reg), "true"
        )
        self.assertEqual(len(reg.opened), 1)
        self.assertEqual(
            reg.opened[0],
            ("HKLM", "SYSTEM" + chr(92) + "CurrentControlSet"
             + chr(92) + "Services" + chr(92) + SERVICE
             + chr(92) + "Parameters", 0, 1),
        )
        self.assertFalse(hasattr(reg, "RegCreateKey"))
        self.assertFalse(hasattr(reg, "SetValue"))

    def test_missing_options_return_disabled_without_writes(self):
        class ReadOnlyRegistry:
            HKEY_LOCAL_MACHINE = 1
            KEY_QUERY_VALUE = 2
            @staticmethod
            def OpenKey(*args):
                raise FileNotFoundError("missing parameters")
        self.assertEqual(_read_registry_option(
            SERVICE, FLAG_OPTION, "", registry=ReadOnlyRegistry
        ), "")
        self.assertFalse(decode_options("", "").enabled)

    def test_read_only_registry_denial_is_sanitized_not_traceback(self):
        class NoAccess:
            HKEY_LOCAL_MACHINE = 1
            KEY_QUERY_VALUE = 2
            @staticmethod
            def OpenKey(*args):
                raise PermissionError("private registry details")
        with self.assertRaises(MentorServiceSettingsError) as ctx:
            _read_registry_option(SERVICE, FLAG_OPTION, "", registry=NoAccess)
        self.assertIn("denied", str(ctx.exception))
        self.assertNotIn("private registry details", str(ctx.exception))

    def test_network_share_not_valid_as_windows_local_system_source(self):
        for name in (
            chr(92)*2 + "Server" + chr(92) + "Share" + chr(92) + "Sofia",
            "//Server/Share/Sofia",
            chr(92)*2 + "?" + chr(92) + "UNC" + chr(92) + "Server",
        ):
            with self.subTest(name=name), self.assertRaisesRegex(
                MentorServiceSettingsError, "network share"
            ):
                _reject_service_network_path(Path(name))
        # Reject before even probing the share.
        with self.assertRaisesRegex(MentorServiceSettingsError, "network share"):
            validate_root(chr(92)*2 + "Server" + chr(92) + "Share" + chr(92) + "Sofia")

    def test_cli_enable_requires_double_opt_in_no_registry_call(self):
        with patch("sofia.mentor.__main__.configure_custom_service_settings",
                   side_effect=AssertionError("never enable without approval")):
            self.assertEqual(main([
                "behavior-service", "--action", "enable",
                "--source-root", str(self.root),
            ]), 2)

    def test_cli_plan_only_and_does_not_touch_scm(self):
        with patch("sofia.mentor.__main__.configure_custom_service_settings",
                   wraps=configure_custom_service_settings) as fn:
            output = StringIO()
            with redirect_stdout(output):
                status = main([
                    "behavior-service", "--action", "plan",
                    "--source-root", str(self.root),
                ])
        self.assertEqual(status, 0)
        self.assertFalse(fn.call_args.kwargs["apply"])
        self.assertIn('"will_restart": false', output.getvalue())

    def test_cli_status_can_be_mocked_without_pywin32(self):
        with patch("sofia.mentor.__main__.service_settings_status", return_value={
            "schema": "sofia.mentor.service-settings.v1", "configured_enabled": False
        }):
            out = StringIO()
            with redirect_stdout(out):
                code = main(["behavior-service", "--action", "status"])
        self.assertEqual(code, 0)
        self.assertIn("configured_enabled", out.getvalue())


if __name__ == "__main__":
    import unittest
    unittest.main()
