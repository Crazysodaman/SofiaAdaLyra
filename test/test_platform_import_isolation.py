"""Platform foundation and Core Link clients load without sofia.core.

G2-A contract: the Platform state/config foundation, the Core Link client
surface and the portable SDK contracts must be importable while importing
``sofia.core`` is blocked. This validates installed/import contents, not a
role flag: any hidden Core import fails the batch.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ISOLATED_MODULES: tuple[str, ...] = (
    "sofia.sdk",
    "sofia.sdk.contracts",
    "sofia.sdk.state",
    "sofia.sdk.cognition_model",
    "sofia.sdk.cognition",
    "sofia.sdk.core_link",
    "sofia.sdk.module_settings",
    "sofia.sdk.principals",
    "sofia.platform.config",
    "sofia.platform.config.identity_bootstrap",
    "sofia.platform.config.environment",
    "sofia.platform.config.roles",
    "sofia.platform.config.inference_endpoint",
    "sofia.platform.config.model",
    "sofia.platform.config.layout",
    "sofia.platform.config.defaults",
    "sofia.platform.config.user_settings",
    "sofia.platform.config.reviewed_projection",
    "sofia.platform.state",
    "sofia.platform.state.atomic_file",
    "sofia.platform.state.private_file",
    "sofia.platform.state.performance",
    "sofia.platform.state.sqlite_uri",
    "sofia.platform.state.sqlite_access",
    "sofia.platform.state.canonical_sqlite",
    "sofia.platform.state.plane",
    "sofia.platform.state.sqlite_plane",
    "sofia.platform.state.model",
    "sofia.platform.state.namespaces",
    "sofia.platform.state.json_repository",
    "sofia.platform.state.component_schema",
    "sofia.platform.state.path_policy",
    "sofia.platform.state.replication",
    "sofia.platform.state.sdk_facade",
    "sofia.platform.state.factory",
    "sofia.platform.state.platform",
    "sofia.platform.core_link",
    "sofia.platform.core_link.binding",
    "sofia.platform.core_link.access",
    "sofia.platform.core_link.transport",
    "sofia.platform.launcher",
)

_BLOCK_CORE = (
    "import importlib.abc, sys\n"
    "class _BlockCore(importlib.abc.MetaPathFinder):\n"
    "    def find_spec(self, fullname, path=None, target=None):\n"
    "        if fullname == 'sofia.core' or fullname.startswith('sofia.core.'):\n"
    "            raise ImportError(f'blocked sofia.core import: {fullname}')\n"
    "        return None\n"
    "sys.meta_path.insert(0, _BlockCore())\n"
)


def _isolated_import_code() -> str:
    imports = "".join(f"import {module}\n" for module in ISOLATED_MODULES)
    return (
        _BLOCK_CORE
        + imports
        + "leaked = [name for name in sys.modules if name == 'sofia.core' "
        "or name.startswith('sofia.core.')]\n"
        "assert not leaked, leaked\n"
        "print('ISOLATED-OK')\n"
    )


def test_platform_foundation_imports_without_core() -> None:
    repository = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository / "src")
    result = subprocess.run(
        [sys.executable, "-c", _isolated_import_code()],
        capture_output=True, text=True, timeout=120, env=environment,
        cwd=str(repository),
    )
    assert result.returncode == 0, result.stderr
    assert "ISOLATED-OK" in result.stdout


def test_moved_contracts_keep_core_import_paths_compatible() -> None:
    from sofia.core.cognition.model import CognitiveRequest as core_request
    from sofia.core.cognition.model import (
        CognitiveRole as core_role,
        CognitiveToolDefinition as core_tool,
    )
    from sofia.core.cognition.performance import record_sqlite as core_record
    from sofia.core.environment.config import (
        ConfiguredLocation as core_location,
        EnvironmentConfiguration as core_env,
        environment_configuration_from_environ as core_env_from_environ,
    )
    from sofia.core.environment.model import LocationSubject as core_subject
    from sofia.core.identity.model import IdentityBootstrapMode as core_mode
    from sofia.core.social.model import (
        AudienceKind as core_audience,
        PrincipalContext as core_principal,
        ScopeKind as core_scope,
        SocialScope as core_social_scope,
    )

    from sofia.platform.config.environment import (
        ConfiguredLocation as platform_location,
        EnvironmentConfiguration as platform_env,
        LocationSubject as platform_subject,
        environment_configuration_from_environ as platform_env_from_environ,
    )
    from sofia.platform.config.identity_bootstrap import (
        IdentityBootstrapMode as platform_mode,
    )
    from sofia.platform.state.performance import record_sqlite as platform_record
    from sofia.sdk.cognition_model import (
        CognitiveRequest as sdk_request,
        CognitiveRole as sdk_role,
        CognitiveToolDefinition as sdk_tool,
    )
    from sofia.sdk.principals import (
        AudienceKind as sdk_audience,
        PrincipalContext as sdk_principal,
        ScopeKind as sdk_scope,
        SocialScope as sdk_social_scope,
    )

    assert core_request is sdk_request
    assert core_role is sdk_role
    assert core_tool is sdk_tool
    assert core_record is platform_record
    assert core_env is platform_env
    assert core_location is platform_location
    assert core_env_from_environ is platform_env_from_environ
    assert core_subject is platform_subject
    assert core_mode is platform_mode
    assert core_audience is sdk_audience
    assert core_principal is sdk_principal
    assert core_scope is sdk_scope
    assert core_social_scope is sdk_social_scope
