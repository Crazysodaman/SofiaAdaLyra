"""Format supplied observation and continuity evidence for cognitive context."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from sofia.continuity.model import ContinuityEvent, ContinuityEventKind
from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.system.knowledge import SystemCapabilityKnowledgeRecord


def format_system_capability_record(
    record: SystemCapabilityKnowledgeRecord,
) -> list[str]:
    lines = [
        "",
        f"CAPABILITY: {record.capability.value}",
        f"Result: {record.kind.value}",
    ]

    if record.observed_at is not None:
        lines.append(
            "Observed at: "
            f"{record.observed_at.isoformat()}"
        )

    if record.backend_name is not None:
        lines.append(
            f"Backend: {record.backend_name}"
        )

    if record.error is not None:
        lines.append(
            f"Error: {record.error}"
        )

    if record.evidence is not None:
        lines.append("Evidence:")
        lines.extend(
            format_structured_value(
                record.evidence,
                indent=2,
            )
        )
    else:
        lines.append(
            "Evidence: none"
        )

    return lines



def format_structured_value(
    value: Any,
    indent: int = 0,
) -> list[str]:
    prefix = " " * indent

    if isinstance(value, Mapping):
        lines: list[str] = []

        for key, item in value.items():
            if isinstance(item, (Mapping, tuple, list)):
                lines.append(
                    f"{prefix}{key}:"
                )
                lines.extend(
                    format_structured_value(
                        item,
                        indent=indent + 2,
                    )
                )
            else:
                lines.append(
                    f"{prefix}{key}: {item}"
                )

        if not lines:
            lines.append(
                f"{prefix}{{}}"
            )

        return lines

    if isinstance(value, (tuple, list)):
        if not value:
            return [
                f"{prefix}[]"
            ]

        lines = []

        for item in value:
            if isinstance(item, (Mapping, tuple, list)):
                lines.append(
                    f"{prefix}-"
                )
                lines.extend(
                    format_structured_value(
                        item,
                        indent=indent + 2,
                    )
                )
            else:
                lines.append(
                    f"{prefix}- {item}"
                )

        return lines


    return [
        f"{prefix}{value}"
    ]



def format_continuity_event(
    event: ContinuityEvent,
) -> list[str]:
    lines = [
        "",
        "CONTINUITY EVENT",
        (
            "This is one aggregate event combining deterministic "
            "runtime and workspace continuity evidence."
        ),
        (
            "The event records observed facts only. It does not "
            "establish intent, authorship, cause, or significance."
        ),
        f"Event kind: {event.kind.value}",
        f"Evidence status: {event.evidence_status.value}",
        f"Restart observed: {event.restart_observed}",
        (
            "Workspace changes: "
            f"{event.workspace_change_count}"
        ),
        "",
        (
            "Continuity evidence may be relevant to the conversation, "
            "but it does not need to be announced merely because it "
            "exists."
        ),
        (
            "Do not produce a separate response for each individual "
            "filesystem change. Treat related changes as one coherent "
            "event and mention them only when relevant."
        ),
    ]

    if event.kind is ContinuityEventKind.RUNTIME_RESUMED:
        lines.append(
            "A previous runtime was observed before the current runtime."
        )

    elif (
        event.kind
        is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    ):
        lines.append(
            "A previous runtime was observed and workspace changes "
            "were detected since the previous filesystem observation."
        )

    elif event.kind is ContinuityEventKind.WORKSPACE_CHANGED:
        lines.append(
            "Workspace changes were detected between filesystem "
            "observations."
        )

    elif event.kind is ContinuityEventKind.INITIAL_RUNTIME:
        lines.append(
            "No previous runtime evidence is available."
        )

    elif event.kind is ContinuityEventKind.CONTINUITY_STABLE:
        lines.append(
            "No new continuity or workspace change event was detected."
        )

    if event.workspace_changes is not None:
        lines.extend(
            format_workspace_changes(
                event.workspace_changes
            )
        )

    return lines



def format_workspace_changes(
    event: FilesystemChangeEvent,
) -> list[str]:
    lines = [
        "",
        "WORKSPACE CHANGE EVENT",
        (
            "This event is a deterministic comparison between "
            "filesystem observations."
        ),
        (
            "It records what changed between observations. "
            "It does not establish who caused a change, why it "
            "occurred, or whether it was intentional."
        ),
        (
            "Baseline available: "
            f"{event.baseline_available}"
        ),
        (
            "Changes detected: "
            f"{event.total_changes}"
        ),
    ]

    if not event.baseline_available:
        lines.append(
            "No previous observation exists, so change detection "
            "cannot classify current files as new, modified, or removed."
        )
        return lines

    if event.new:
        lines.append(
            f"New files ({len(event.new)}):"
        )

        for change in event.new:
            lines.append(
                f"- {change.path}"
            )

    if event.modified:
        lines.append(
            f"Modified files ({len(event.modified)}):"
        )

        for change in event.modified:
            lines.append(
                f"- {change.path}"
            )

    if event.removed:
        lines.append(
            f"Removed files ({len(event.removed)}):"
        )

        for change in event.removed:
            lines.append(
                f"- {change.path}"
            )

    if not event.has_changes:
        lines.append(
            "No filesystem changes were detected."
        )

    return lines



def format_filesystem_result(result) -> list[str]:
    lines = [
        "",
        f"Operation: {result.operation.value}",
        f"Result: {result.kind.value}",
        f"Path: {result.path}",
        f"Message: {result.message}",
    ]

    if result.entries:
        lines.append("Entries:")

        for entry in result.entries:
            lines.append(
                f"- {entry}"
            )

    if result.content is not None:
        lines.extend(
            [
                "File content:",
                result.content,
            ]
        )

    return lines
