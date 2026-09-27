"""Exact-purpose network route grants.

Connectivity never implies application authority, and one route purpose never
implicitly grants another. In particular, Discord/Fleet/NWS do not grant
general web/search.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class RoutePurpose(str, Enum):
    DISCORD = "discord"
    FLEET = "fleet"
    WEATHER_NWS = "weather_nws"
    GENERAL_WEB = "general_web"


@dataclass(frozen=True, slots=True)
class NetworkRouteGrant:
    grant_id: str
    purpose: RoutePurpose
    schemes: tuple[str, ...]
    hosts: tuple[str, ...]
    ports: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.grant_id, str) or not self.grant_id.strip():
            raise ValueError("grant_id required")
        if not isinstance(self.purpose, RoutePurpose):
            raise TypeError("purpose must be RoutePurpose")
        if not self.schemes or any(
            not isinstance(value, str) or not value.strip()
            for value in self.schemes
        ):
            raise ValueError("at least one exact scheme is required")
        if not self.hosts or any(
            not isinstance(value, str) or not value.strip()
            for value in self.hosts
        ):
            raise ValueError("at least one exact host is required")
        normalized_schemes = tuple(value.casefold() for value in self.schemes)
        normalized_hosts = tuple(value.casefold().rstrip(".") for value in self.hosts)
        if len(set(normalized_schemes)) != len(normalized_schemes):
            raise ValueError("schemes must be unique")
        if len(set(normalized_hosts)) != len(normalized_hosts):
            raise ValueError("hosts must be unique")
        for port in self.ports:
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("ports must contain valid TCP/UDP port numbers")

    def allows(self, url: str, *, purpose: RoutePurpose) -> bool:
        if purpose is not self.purpose:
            return False
        if not isinstance(url, str) or not url.strip():
            return False
        parsed = urlparse(url)
        if parsed.username is not None or parsed.password is not None:
            return False
        scheme = parsed.scheme.casefold()
        host = (parsed.hostname or "").casefold().rstrip(".")
        if scheme not in {item.casefold() for item in self.schemes}:
            return False
        if host not in {item.casefold().rstrip(".") for item in self.hosts}:
            return False
        if self.ports:
            port = parsed.port
            if port is None:
                port = 443 if scheme == "https" else 80 if scheme == "http" else None
            if port not in self.ports:
                return False
        return True
