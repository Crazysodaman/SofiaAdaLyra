from __future__ import annotations

from pathlib import Path
import re

import pytest


MODULE_PACKAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "act": ("pkg_act",),
    "action": ("pkg_act",),
    "application": ("pkg_core",),
    "authority": ("pkg_safe",),
    "authorization": ("pkg_safe",),
    "avatar": ("pkg_avatar",),
    "body": ("pkg_body",),
    "capability": ("pkg_safe",),
    "clean": ("pkg_clean",),
    "codebase": ("pkg_dev",),
    "cognition": ("pkg_core",),
    "composition": ("pkg_core",),
    "config": ("pkg_core",),
    "constitution": ("pkg_core", "pkg_safe"),
    "continuity": ("pkg_core",),
    "conversation": ("pkg_core",),
    "dev": ("pkg_dev",),
    "discord": ("pkg_ui", "pkg_social", "pkg_net"),
    "distributed": ("pkg_net", "pkg_ops"),
    "embodiment": ("pkg_avatar",),
    "emotion": ("pkg_core",),
    "environment": ("pkg_environment",),
    "evolve": ("pkg_evolve", "pkg_safe"),
    "filesystem": ("pkg_dev",),
    "habits": ("pkg_habit",),
    "identity": ("pkg_core",),
    "integrate": ("pkg_integrate",),
    "integrations": ("pkg_integrate",),
    "interaction": ("pkg_interact",),
    "knowledge": ("pkg_know",),
    "machine": ("pkg_ops",),
    "memory": ("pkg_mem",),
    "mobile": ("pkg_ui", "pkg_net"),
    "net": ("pkg_net",),
    "neuro": ("pkg_core",),
    "operational": ("pkg_core",),
    "ops": ("pkg_ops",),
    "personality": ("pkg_core",),
    "rel": ("pkg_rel",),
    "run": ("pkg_run",),
    "runtime": ("pkg_core",),
    "safe": ("pkg_safe",),
    "self_model": ("pkg_core",),
    "social": ("pkg_social",),
    "state": ("pkg_core",),
    "system": ("pkg_ops",),
    "ui": ("pkg_ui",),
    "voice": ("pkg_voice",),
    "verify": ("pkg_verify",),
}

FILENAME_PACKAGE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("test_discord_", ("pkg_ui", "pkg_social", "pkg_net")),
    ("test_interaction_", ("pkg_interact",)),
    ("test_memory_", ("pkg_mem",)),
    ("test_environment_", ("pkg_environment",)),
    ("test_avatar_", ("pkg_avatar",)),
    ("test_embodiment_", ("pkg_avatar",)),
    ("test_machine_", ("pkg_ops",)),
    ("test_ops_", ("pkg_ops",)),
    ("test_run_", ("pkg_run",)),
    ("test_dev_", ("pkg_dev",)),
    ("test_evolve_", ("pkg_evolve",)),
    ("test_know_", ("pkg_know",)),
    ("test_act_", ("pkg_act",)),
    ("test_action_", ("pkg_act",)),
    ("test_ui_", ("pkg_ui",)),
    ("test_voice_", ("pkg_voice",)),
    ("test_distributed_", ("pkg_net", "pkg_ops")),
    ("test_system_", ("pkg_ops",)),
    ("test_safe_", ("pkg_safe",)),
    ("test_filesystem_", ("pkg_dev", "pkg_safe")),
    ("test_authority", ("pkg_safe",)),
    ("test_authorization", ("pkg_safe",)),
    ("test_capability_", ("pkg_safe",)),
    ("test_constitution_", ("pkg_core", "pkg_safe")),
    ("test_conversation_", ("pkg_core",)),
    ("test_cognitive_", ("pkg_core",)),
    ("test_continuity_", ("pkg_core",)),
    ("test_personality_", ("pkg_core",)),
    ("test_runtime", ("pkg_core",)),
    ("test_application", ("pkg_core",)),
    ("test_identity", ("pkg_core",)),
    ("test_reflection_", ("pkg_rel", "pkg_core")),
    ("test_thought_", ("pkg_rel", "pkg_core")),
    ("test_current_emotional_state", ("pkg_rel", "pkg_core")),
    ("test_emotional_", ("pkg_rel", "pkg_core")),
    ("test_model_evaluation_harness.py", ("pkg_verify", "pkg_core")),
    ("test_package_grouping.py", ("pkg_verify",)),
    ("test_module_entrypoint.py", ("pkg_core",)),
)

_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:from|import)\s+sofia\.([A-Za-z_][A-Za-z0-9_]*)"
)


def _explicit_package_markers(path: Path) -> frozenset[str]:
    """Return only ownership proven by imports or explicit filename rules."""
    markers: set[str] = set()
    try:
        source = path.read_text(encoding="utf-8-sig")
    except OSError:
        source = ""

    for module in _IMPORT_RE.findall(source):
        markers.update(MODULE_PACKAGE_MARKERS.get(module, ()))

    name = path.name
    for prefix, owned_markers in FILENAME_PACKAGE_MARKERS:
        if name.startswith(prefix):
            markers.update(owned_markers)

    return frozenset(markers)


def _package_markers(path: Path) -> frozenset[str]:
    """Return package markers used by pytest collection.

    The fallback keeps ad-hoc external fixtures compatible. Repository audit
    tests use _explicit_package_markers so unclassified tests cannot hide here.
    """
    markers = _explicit_package_markers(path)
    return markers or frozenset({"pkg_core"})


def pytest_collection_modifyitems(items) -> None:
    """Attach package ownership without moving historical test files.

    Tests may own multiple package markers when they intentionally verify
    cross-package contracts. This keeps targeted package runs useful while
    preserving git history and stable paths during the current cleanup.
    """
    for item in items:
        path = Path(str(item.path))
        package_markers = _package_markers(path)
        for marker in sorted(package_markers):
            item.add_marker(getattr(pytest.mark, marker))
        if len(package_markers) > 1:
            item.add_marker(pytest.mark.cross_package)
