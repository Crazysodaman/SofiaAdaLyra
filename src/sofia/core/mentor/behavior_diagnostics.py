"""Owner-local diagnostic for passive MENTOR behavior review, with no network.

A CLI environment is not Sofía's Windows Service environment. Never infer a
running service configuration, idle state, or attached conversation hook from
the current shell. Report what this process can genuinely establish.
"""
from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from .behavior_history import default_local_path, read_counts
from .behavior_monitor import behavior_monitor_enabled


def diagnose_behavior(*, root: Path | str = ".",
                      history_path: Path | str | None = None) -> dict[str, Any]:
    """Return configuration/preflight facts scoped ONLY to this CLI process."""
    root = Path(root).resolve(strict=True)
    source = root / "src" / "sofia" / "core" / "personality" / "personality.json"
    local = default_local_path() if history_path is None else Path(history_path)
    try:
        enabled = behavior_monitor_enabled()
        flag_valid = True
    except ValueError:
        enabled = False
        flag_valid = False
    profile_exists = source.is_file() and not source.is_symlink()
    stored = local.exists() and local.is_file() and not local.is_symlink()
    try:
        counts = read_counts(local)
        reviewed = counts["reviewed_turns"]
        history_readable = True
    except (OSError, ValueError, TypeError):
        reviewed = None
        history_readable = False
    source_root_set = bool(os.environ.get("SOFIA_MENTOR_SOURCE_ROOT", "").strip())
    configured_root = (
        Path(os.environ["SOFIA_MENTOR_SOURCE_ROOT"]).expanduser()
        if source_root_set else root
    )
    try:
        configured_profile = configured_root.resolve(strict=True) / (
            "src/sofia/core/personality/personality.json"
        )
        configured_root_valid = (
            configured_profile.is_file() and not configured_profile.is_symlink()
        )
    except (OSError, ValueError):
        configured_root_valid = False
    blockers = []
    if not flag_valid:
        blockers.append("invalid_enable_flag_in_current_shell")
    elif not enabled:
        blockers.append("monitor_disabled_in_current_shell")
    if not profile_exists:
        blockers.append("profile_missing_from_selected_checkout")
    if not configured_root_valid:
        blockers.append("configured_profile_root_not_found")
    if not history_readable:
        blockers.append("local_score_file_unreadable")
    if reviewed == 0:
        blockers.append("no_completed_review_in_current_account")
    return {
        "schema": "sofia.core.mentor.behavior-diagnosis.v1",
        "checked_context": "current_cli_process_only",
        "runtime_service_environment_verified": False,
        "runtime_conversation_hook_attached_verified": False,
        "runtime_pending_turns_visible": False,
        "runtime_idle_scheduler_verified": False,
        "monitor_enabled_in_current_shell": enabled,
        "enable_flag_valid": flag_valid,
        "repository_personality_profile_present": profile_exists,
        "source_root_env_set_in_current_shell": source_root_set,
        "source_root_profile_resolves_in_current_shell": configured_root_valid,
        "local_score_file_exists_for_this_account": stored,
        "local_score_file_readable": history_readable,
        "completed_reviews_in_this_account": reviewed,
        "diagnostic_flags": blockers,
        "next_checks": [
            "Confirm Sofía's running process or Windows service was restarted with SOFIA_MENTOR_BEHAVIOR_ENABLED=true.",
            "Confirm SOFIA_MENTOR_SOURCE_ROOT points to the checkout used by that runtime.",
            "Complete a genuine Sofía conversation while the monitor is enabled.",
            "Wait for an admitted idle window: no gaming, no busy/unknown host, and at least five minutes without conversation.",
            "Check SofiaApplication.mentor_behavior_snapshot from the running application to distinguish observed/pending/reviewed/failed counts.",
            "If Sofía runs as another Windows account, inspect that account's local score history through approved administration.",
            "Use behavior-smoke with the local critic while idle to validate model JSON separately from runtime conversation wiring.",
        ],
        "privacy": {
            "no_private_turns_read": True, "no_outbound_network": True,
            "no_source_or_score_files_modified": True,
        },
    }
