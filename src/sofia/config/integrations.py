"""Environment-backed configuration for optional read-only service tools."""
from __future__ import annotations

import os
from typing import Mapping

from sofia.integrate.adapters import (
    GitHubRepositoryAdapter,
    HomeAssistantAdapter,
    HyperVAdapter,
    JmriAdapter,
    PortainerAdapter,
)
from sofia.integrate.observation_capability import ExternalObservationCapability


def create_external_observation_capabilities(
    environ: Mapping[str, str] | None = None,
) -> tuple[ExternalObservationCapability, ...]:
    values = os.environ if environ is None else environ
    result: list[ExternalObservationCapability] = []

    ha_url = values.get("SOFIA_HOME_ASSISTANT_URL", "").strip()
    ha_token = values.get("SOFIA_HOME_ASSISTANT_TOKEN", "").strip()
    if ha_url and ha_token:
        result.append(
            ExternalObservationCapability(
                capability_name="external.observe.home_assistant",
                tool_name="inspect_home_assistant",
                description="Inspect configured Home Assistant API and entity state. Read-only.",
                adapter=HomeAssistantAdapter(ha_url, ha_token),
            )
        )

    portainer_url = values.get("SOFIA_PORTAINER_URL", "").strip()
    portainer_key = values.get("SOFIA_PORTAINER_API_KEY", "").strip()
    if portainer_url and portainer_key:
        result.append(
            ExternalObservationCapability(
                capability_name="external.observe.portainer",
                tool_name="inspect_portainer",
                description="Inspect configured Portainer environments. Read-only.",
                adapter=PortainerAdapter(portainer_url, portainer_key),
            )
        )

    jmri_url = values.get("SOFIA_JMRI_URL", "").strip()
    if jmri_url:
        result.append(
            ExternalObservationCapability(
                capability_name="external.observe.jmri",
                tool_name="inspect_jmri",
                description="Inspect configured JMRI roster information. Read-only.",
                adapter=JmriAdapter(jmri_url),
            )
        )

    github_owner = values.get("SOFIA_GITHUB_OWNER", "").strip()
    github_repo = values.get("SOFIA_GITHUB_REPOSITORY", "").strip()
    github_token = values.get("SOFIA_GITHUB_TOKEN", "").strip() or None
    if github_owner and github_repo:
        result.append(
            ExternalObservationCapability(
                capability_name="external.observe.github",
                tool_name="inspect_github",
                description="Inspect configured GitHub repository metadata and open pull requests. Read-only.",
                adapter=GitHubRepositoryAdapter(
                    github_owner,
                    github_repo,
                    github_token,
                ),
            )
        )

    hyperv = values.get("SOFIA_HYPERV_OBSERVE", "").strip().lower()
    if hyperv in {"1", "true", "on"}:
        result.append(
            ExternalObservationCapability(
                capability_name="external.observe.hyperv",
                tool_name="inspect_hyperv",
                description="Inspect local Hyper-V virtual machine inventory. Read-only.",
                adapter=HyperVAdapter(),
            )
        )

    return tuple(result)
