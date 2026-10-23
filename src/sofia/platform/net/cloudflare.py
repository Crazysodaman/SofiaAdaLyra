"""Opt-in cloudflared process supervision for the authenticated mobile API."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from threading import Event, RLock, Thread
from time import monotonic
from typing import Callable
from urllib.parse import urlsplit


_TUNNEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


def _flag(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().casefold()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean")


@dataclass(frozen=True, slots=True)
class CloudflareTunnelConfiguration:
    enabled: bool = False
    executable: str = "cloudflared"
    config_path: Path | None = None
    tunnel: str | None = None
    public_url: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")
        if not isinstance(self.executable, str) or not self.executable.strip():
            raise ValueError("cloudflared executable is required")
        if self.public_url is not None:
            parsed = urlsplit(self.public_url)
            if (
                parsed.scheme.casefold() != "https"
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Cloudflare public URL must be a clean HTTPS origin")
        if self.enabled:
            if self.config_path is None or not self.config_path.is_file():
                raise ValueError("enabled Cloudflare tunnel requires an existing config file")
            if self.tunnel is None or _TUNNEL.fullmatch(self.tunnel) is None:
                raise ValueError("enabled Cloudflare tunnel requires a bounded name/UUID")
            if self.public_url is None:
                raise ValueError("enabled Cloudflare tunnel requires its public HTTPS URL")

    @classmethod
    def from_runtime(
        cls,
        *,
        mobile_enabled: bool,
        mobile_host: str,
    ) -> "CloudflareTunnelConfiguration":
        enabled = _flag("SOFIA_CLOUDFLARE_TUNNEL_ENABLED")
        if enabled and not mobile_enabled:
            raise ValueError("Cloudflare mobile tunnel requires the mobile API")
        if enabled and mobile_host.casefold() not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Cloudflare tunnel requires a loopback-only mobile API")
        raw_config = os.environ.get("SOFIA_CLOUDFLARE_CONFIG", "").strip()
        return cls(
            enabled=enabled,
            executable=os.environ.get("SOFIA_CLOUDFLARE_BIN", "cloudflared").strip(),
            config_path=Path(raw_config) if raw_config else None,
            tunnel=os.environ.get("SOFIA_CLOUDFLARE_TUNNEL", "").strip() or None,
            public_url=os.environ.get("SOFIA_CLOUDFLARE_PUBLIC_URL", "").strip() or None,
        )

    def command(self) -> tuple[str, ...]:
        if not self.enabled or self.config_path is None or self.tunnel is None:
            raise RuntimeError("Cloudflare tunnel is disabled")
        # Credentials remain referenced inside the host-owned config file; no
        # tunnel token or secret is placed in argv, logs, state, or model context.
        return (
            self.executable,
            "--no-autoupdate",
            "tunnel",
            "--config",
            str(self.config_path),
            "run",
            self.tunnel,
        )


@dataclass(frozen=True, slots=True)
class CloudflareTunnelStatus:
    configured: bool
    state: str
    public_url: str | None
    pid: int | None
    restart_count: int
    updated_at: datetime
    last_exit_code: int | None = None
    error_kind: str | None = None


class CloudflareTunnelStatusStore:
    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS net_cloudflare_tunnel_status (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    configured INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    public_url TEXT,
                    pid INTEGER,
                    restart_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_exit_code INTEGER,
                    error_kind TEXT
                )
            """)

    def put(self, status: CloudflareTunnelStatus) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""
                INSERT INTO net_cloudflare_tunnel_status(
                    singleton,configured,state,public_url,pid,restart_count,
                    updated_at,last_exit_code,error_kind
                ) VALUES(1,?,?,?,?,?,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    configured=excluded.configured,state=excluded.state,
                    public_url=excluded.public_url,pid=excluded.pid,
                    restart_count=excluded.restart_count,updated_at=excluded.updated_at,
                    last_exit_code=excluded.last_exit_code,error_kind=excluded.error_kind
            """, (
                int(status.configured), status.state, status.public_url,
                status.pid, status.restart_count, status.updated_at.isoformat(),
                status.last_exit_code, status.error_kind,
            ))

    def get(self) -> CloudflareTunnelStatus | None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute("""
                SELECT configured,state,public_url,pid,restart_count,updated_at,
                       last_exit_code,error_kind
                FROM net_cloudflare_tunnel_status WHERE singleton=1
            """).fetchone()
        if row is None:
            return None
        return CloudflareTunnelStatus(
            configured=bool(row[0]), state=row[1], public_url=row[2], pid=row[3],
            restart_count=row[4], updated_at=datetime.fromisoformat(row[5]),
            last_exit_code=row[6], error_kind=row[7],
        )


PopenFactory = Callable[..., subprocess.Popen]


class CloudflareTunnelSupervisor:
    """Own one fixed cloudflared child and restart it with bounded backoff."""

    def __init__(
        self,
        configuration: CloudflareTunnelConfiguration,
        *,
        state_path: str | Path,
        popen: PopenFactory = subprocess.Popen,
    ) -> None:
        if not isinstance(configuration, CloudflareTunnelConfiguration):
            raise TypeError("configuration must be CloudflareTunnelConfiguration")
        if not callable(popen):
            raise TypeError("popen must be callable")
        self.configuration = configuration
        self.store = CloudflareTunnelStatusStore(state_path)
        self._popen = popen
        self._stop = Event()
        self._lock = RLock()
        self._thread: Thread | None = None
        self._process: subprocess.Popen | None = None
        self._restart_count = 0
        if not configuration.enabled:
            self._record("disabled")

    def _record(
        self,
        state: str,
        *,
        exit_code: int | None = None,
        error: BaseException | None = None,
    ) -> None:
        with self._lock:
            process = self._process
            pid = None if process is None else process.pid
        self.store.put(CloudflareTunnelStatus(
            configured=self.configuration.enabled,
            state=state,
            public_url=self.configuration.public_url,
            pid=pid,
            restart_count=self._restart_count,
            updated_at=datetime.now(timezone.utc),
            last_exit_code=exit_code,
            error_kind=None if error is None else type(error).__name__,
        ))

    def start(self) -> None:
        if not self.configuration.enabled:
            return
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("Cloudflare tunnel supervisor already started")
            self._stop.clear()
            self._record("starting")
            self._thread = Thread(
                target=self._run,
                name="sofia-cloudflare-tunnel",
                daemon=True,
            )
            self._thread.start()

    def _spawn(self):
        return self._popen(
            self.configuration.command(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )

    def _run(self) -> None:
        backoff = (5.0, 15.0, 60.0, 120.0)
        while not self._stop.is_set():
            started = monotonic()
            try:
                process = self._spawn()
                with self._lock:
                    self._process = process
                self._record("running")
                exit_code = process.wait()
                with self._lock:
                    self._process = None
                if self._stop.is_set():
                    self._record("stopped", exit_code=exit_code)
                    return
                self._restart_count += 1
                self._record("degraded", exit_code=exit_code)
            except Exception as exc:
                with self._lock:
                    self._process = None
                self._restart_count += 1
                self._record("failed", error=exc)
            if monotonic() - started >= 300:
                self._restart_count = 0
            delay = backoff[min(self._restart_count - 1, len(backoff) - 1)]
            self._stop.wait(delay)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            process = self._process
            thread = self._thread
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if thread is not None:
            thread.join(timeout=15)
        with self._lock:
            self._process = None
            self._thread = None
        if self.configuration.enabled:
            self._record("stopped")
        self._record("stopped")

    @property
    def status(self) -> CloudflareTunnelStatus | None:
        return self.store.get()
