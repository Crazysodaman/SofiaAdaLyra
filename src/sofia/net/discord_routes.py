"""Offline fail-closed Discord endpoint classification, never a network firewall.

The transport must enforce DNS, IP, TLS, proxy and redirect constraints itself.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


class Route(str, Enum):
    API = "api"
    GATEWAY = "gateway"


class RouteDenial(str, Enum):
    DISABLED = "disabled"
    INVALID = "invalid"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True, slots=True)
class RouteDecision:
    allowed: bool
    denial: RouteDenial | None


@dataclass(frozen=True, slots=True)
class DiscordRoutePolicy:
    enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be boolean")


def classify_discord_route(policy: DiscordRoutePolicy, *, url: str, route: Route) -> RouteDecision:
    """Permit exact first-party API or Gateway URLs only when explicitly enabled.

    This function makes NO connection and does not prove Discord ownership.
    It is not a grant to browse, follow redirects or access CDN/media hosts.
    """
    if not isinstance(policy, DiscordRoutePolicy) or not isinstance(route, Route):
        raise TypeError("typed policy and route required")
    if not policy.enabled:
        return RouteDecision(False, RouteDenial.DISABLED)
    if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        return RouteDecision(False, RouteDenial.INVALID)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return RouteDecision(False, RouteDenial.INVALID)
    if (parsed.username is not None or parsed.password is not None or parsed.fragment or
            parsed.hostname is None or port not in (None, 443)):
        return RouteDecision(False, RouteDenial.INVALID)
    if route is Route.API:
        allowed = parsed.scheme == "https" and parsed.hostname == "discord.com" and parsed.path.startswith("/api/")
    else:
        allowed = parsed.scheme == "wss" and parsed.hostname == "gateway.discord.gg" and parsed.path in ("", "/")
    return RouteDecision(True, None) if allowed else RouteDecision(False, RouteDenial.OUT_OF_SCOPE)
