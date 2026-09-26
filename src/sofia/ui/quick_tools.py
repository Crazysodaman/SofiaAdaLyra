"""Curated desktop quick-tool prompts.

These are convenience prompts only. Selecting one never executes a capability.
Execution remains an explicit user send through the canonical conversation and
tool-authority path.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuickTool:
    tool_id: str
    label: str
    prompt: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.tool_id, "tool_id"),
            (self.label, "label"),
            (self.prompt, "prompt"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be nonempty")


QUICK_TOOLS: tuple[QuickTool, ...] = (
    QuickTool(
        tool_id="tool-catalog",
        label="Tool Catalog",
        prompt=(
            "List the tools and capabilities currently available to you, "
            "including which have standing authorization. Summarize them by purpose."
        ),
    ),
    QuickTool(
        tool_id="system",
        label="System Summary",
        prompt=(
            "Inspect this computer's operating system, host identity, and uptime, "
            "then summarize the important points."
        ),
    ),
    QuickTool(
        tool_id="hardware",
        label="Hardware Summary",
        prompt=(
            "Inspect this computer's CPU, GPU, memory, storage, network adapters, "
            "and virtualization hardware, then summarize the important points."
        ),
    ),
    QuickTool(
        tool_id="processes",
        label="Running Processes",
        prompt=(
            "Inspect the local running processes and summarize the most relevant "
            "or resource-heavy processes."
        ),
    ),
    QuickTool(
        tool_id="network",
        label="Network Summary",
        prompt=(
            "Inspect the local network interfaces, routes, and DNS configuration, "
            "then summarize the current network state."
        ),
    ),
    QuickTool(
        tool_id="services",
        label="Service Summary",
        prompt=(
            "Inspect local services and summarize notable running, stopped, or "
            "problematic service states."
        ),
    ),
    QuickTool(
        tool_id="storage",
        label="Storage Summary",
        prompt=(
            "Inspect available storage roots and storage usage, then summarize "
            "capacity, free space, and anything that needs attention."
        ),
    ),
    QuickTool(
        tool_id="fleet",
        label="Fleet Overview",
        prompt=(
            "List the machines currently known to your fleet tools and summarize "
            "their current state without making any changes."
        ),
    ),
    QuickTool(
        tool_id="environment",
        label="Environment",
        prompt=(
            "Tell me the current local time, weather, and environmental context "
            "you currently have for this machine, including freshness where relevant."
        ),
    ),
    QuickTool(
        tool_id="presentation",
        label="Current Outfit",
        prompt=(
            "Tell me your current public-safe outfit and appearance presentation "
            "state, including the outfit identifier if available."
        ),
    ),
)


def quick_tool_labels() -> tuple[str, ...]:
    return tuple(tool.label for tool in QUICK_TOOLS)


def quick_tool_by_label(label: str) -> QuickTool:
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label must be nonempty")
    for tool in QUICK_TOOLS:
        if tool.label == label:
            return tool
    raise KeyError(label)
