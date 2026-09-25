"""Offline lexical route checks; NOT DNS/TLS/firewall/Discord acceptance."""
import pytest
from sofia.net.discord_routes import DiscordRoutePolicy, Route, RouteDenial, classify_discord_route


def check(url, route=Route.API, enabled=True):
    return classify_discord_route(DiscordRoutePolicy(enabled), url=url, route=route)


def test_disabled_by_default():
    assert not classify_discord_route(DiscordRoutePolicy(), url="https://discord.com/api/v10", route=Route.API).allowed

@pytest.mark.parametrize("url,route", [
    ("https://discord.com/api/v10/users/@me", Route.API),
    ("https://discord.com:443/api/v10/messages?limit=1", Route.API),
    ("wss://gateway.discord.gg/?v=10&encoding=json", Route.GATEWAY),
    ("wss://gateway.discord.gg:443", Route.GATEWAY),
])
def test_allowed_exact_routes(url, route):
    d = check(url, route)
    assert d.allowed and d.denial is None

@pytest.mark.parametrize("url,route", [
    ("https://discord.com.evil.invalid/api/v10", Route.API),
    ("https://evil.invalid/discord.com/api/v10", Route.API),
    ("http://discord.com/api/v10", Route.API),
    ("https://discord.com/", Route.API),
    ("https://discord.com/api", Route.API),
    ("https://discord.com/api/v10", Route.GATEWAY),
    ("wss://gateway.discord.gg.evil.invalid/", Route.GATEWAY),
    ("ws://gateway.discord.gg/", Route.GATEWAY),
    ("wss://gateway.discord.gg/other", Route.GATEWAY),
    ("https://www.google.com/search?q=discord", Route.API),
    ("https://cdn.discordapp.com/attachments/x", Route.API),
    ("https://127.0.0.1/api/v10", Route.API),
])
def test_out_of_scope(url, route):
    assert check(url, route).denial is RouteDenial.OUT_OF_SCOPE

@pytest.mark.parametrize("url", [
    "", "https://discord.com:444/api/v10", "https://user@discord.com/api/v10",
    "https://discord.com/api/v10#frag", "https://discord.com\\@evil.invalid/api/v10",
    "https://discord.com/api/v10\n", " https://discord.com/api/v10", "https://discord.com:bad/api/v10",
    None, 1,
])
def test_malformed(url):
    assert check(url).denial is RouteDenial.INVALID


def test_enable_must_be_bool():
    with pytest.raises(TypeError):
        DiscordRoutePolicy(1)


def test_typed_route_required():
    with pytest.raises(TypeError):
        check("https://discord.com/api/v10", "api")
