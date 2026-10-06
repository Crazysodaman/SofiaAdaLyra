from datetime import timezone
from pathlib import Path
from threading import Event

import pytest

from sofia.net import (
    CloudflareTunnelConfiguration,
    CloudflareTunnelStatusStore,
    CloudflareTunnelSupervisor,
)


def test_runtime_configuration_is_opt_in(monkeypatch):
    monkeypatch.delenv("SOFIA_CLOUDFLARE_TUNNEL_ENABLED", raising=False)
    config = CloudflareTunnelConfiguration.from_runtime(
        mobile_enabled=False, mobile_host="127.0.0.1",
    )
    assert config.enabled is False


def test_enabled_tunnel_requires_loopback_mobile_and_clean_https_origin(
    tmp_path, monkeypatch,
):
    config_file = tmp_path / "cloudflared.yml"
    config_file.write_text("tunnel: test\n", encoding="utf-8")
    monkeypatch.setenv("SOFIA_CLOUDFLARE_TUNNEL_ENABLED", "true")
    monkeypatch.setenv("SOFIA_CLOUDFLARE_CONFIG", str(config_file))
    monkeypatch.setenv("SOFIA_CLOUDFLARE_TUNNEL", "sofia-mobile")
    monkeypatch.setenv("SOFIA_CLOUDFLARE_PUBLIC_URL", "https://sofia.example.com")
    with pytest.raises(ValueError, match="loopback"):
        CloudflareTunnelConfiguration.from_runtime(
            mobile_enabled=True, mobile_host="0.0.0.0",
        )
    config = CloudflareTunnelConfiguration.from_runtime(
        mobile_enabled=True, mobile_host="127.0.0.1",
    )
    assert config.command() == (
        "cloudflared", "--no-autoupdate", "tunnel", "--config",
        str(config_file), "run", "sofia-mobile",
    )
    assert not any("token" in item.casefold() for item in config.command())


def test_supervisor_starts_stops_and_records_status(tmp_path):
    config_file = tmp_path / "cloudflared.yml"
    config_file.write_text("tunnel: test\n", encoding="utf-8")
    terminated = Event()
    spawned = Event()

    class Process:
        pid = 456
        returncode = None

        def wait(self, timeout=None):
            spawned.set()
            assert terminated.wait(timeout or 5)
            self.returncode = 0
            return 0

        def poll(self):
            return self.returncode

        def terminate(self):
            terminated.set()

        def kill(self):
            terminated.set()

    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return Process()

    config = CloudflareTunnelConfiguration(
        enabled=True, config_path=config_file, tunnel="sofia-mobile",
        public_url="https://sofia.example.com",
    )
    supervisor = CloudflareTunnelSupervisor(
        config, state_path=tmp_path / "state.db", popen=popen,
    )
    supervisor.start()
    assert spawned.wait(5)
    supervisor.stop()
    status = CloudflareTunnelStatusStore(tmp_path / "state.db").get()
    assert status is not None
    assert status.state == "stopped"
    assert status.updated_at.tzinfo is timezone.utc
    assert calls[0][1]["shell"] is False
