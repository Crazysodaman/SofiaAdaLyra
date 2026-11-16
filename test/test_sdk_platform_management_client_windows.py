"""Disposable named-pipe test server: NOT a signed installed B1 service."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from threading import Event, Thread
from uuid import uuid4

import pytest

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import make_response
from sofia.sdk.platform_management_windows_client import (
    read_windows_management, windows_management_pipe_name,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")

PLATFORM_ID = str(uuid4())
GENERATION = 3
CORE_ID = str(uuid4())


def _data(request):
    if request.operation == "startup.status":
        return {
            "platform_id": request.target_platform_id,
            "generation": request.expected_generation,
            "operator_stop": False,
            "core_started": True,
            "core_count": 1,
            "active_core_count": 1,
            "startup_state": "CORES_RUNNING",
            "autostart_enabled_count": 1,
            "autostart_reconciled_at": None,
            "management_listening": True,
        }
    if request.operation == "core.list":
        return {
            "platform_id": request.target_platform_id,
            "generation": request.expected_generation,
            "operator_stop": False,
            "cores": [{
                "core_id": CORE_ID, "installed": True, "enabled": True,
                "startup_mode": "on_platform_ready",
                "observed_state": "RUNNING",
                "generation": request.expected_generation,
                "last_error_code": None,
            }],
        }
    return {
        "platform_id": request.target_platform_id,
        "generation": request.expected_generation,
        "operator_stop": False,
        "core_started": False,
    }


@contextmanager
def synthetic_service(mode="OK"):
    from sofia.platform.run.management_windows_pipe import (
        ManagementWindowsPipeListener,
    )

    observed = []
    def dispatch(raw, *, authenticated_peer, now):
        request = UntrustedManagementRead.parse(raw, now=now)
        observed.append((raw, request, authenticated_peer, now))
        if mode == "STOPPED":
            return make_response(
                request, observed_at=now, denial_code="STOPPED",
            )
        body = make_response(request, observed_at=now, data=_data(request))
        if mode == "FORGED_REQUEST":
            body["request_id"] = "req:forged"
        return body

    name = windows_management_pipe_name(
        platform_id=PLATFORM_ID, generation=GENERATION,
    )
    stop = Event()
    with ManagementWindowsPipeListener(name, dispatch=dispatch) as server:
        worker = Thread(target=server.serve_until, args=(stop,), daemon=True)
        worker.start()
        try:
            yield name, observed
        finally:
            stop.set()
            worker.join(timeout=4)


def call(name, operation, **changes):
    kw = dict(
        pipe_name=name, expected_platform_id=PLATFORM_ID,
        expected_generation=GENERATION, operation=operation,
    )
    kw.update(changes)
    return read_windows_management(**kw)


def test_native_windows_pipe_status_round_trip():
    with synthetic_service() as (name, observed):
        result = call(name, "platform.status")
        assert result.outcome == "OK"
        assert result.data["generation"] == GENERATION
        assert result.data["core_started"] is False
        assert len(observed) == 1
        assert observed[0][1].operation == "platform.status"
        assert observed[0][2].startswith("windows:sid:S-1-5-")
        assert isinstance(observed[0][3], datetime)


def test_native_windows_pipe_startup_and_core_inventory_reads():
    with synthetic_service() as (name, observed):
        startup = call(name, "startup.status")
        assert startup.outcome == "OK"
        assert startup.data["startup_state"] == "CORES_RUNNING"
        inventory = call(name, "core.list")
        assert inventory.outcome == "OK"
        assert inventory.data["cores"][0]["core_id"] == CORE_ID
        assert [item[1].operation for item in observed] == [
            "startup.status", "core.list",
        ]


def test_native_windows_pipe_typed_stop_denial():
    with synthetic_service("STOPPED") as (name, _):
        result = call(name, "startup.status")
        assert result.outcome == "DENIED"
        assert result.denial_code == "STOPPED"
        assert result.data is None


def test_native_windows_pipe_rejects_uncorrelated_request_id():
    with synthetic_service("FORGED_REQUEST") as (name, _):
        with pytest.raises(PermissionError, match="uncorrelated"):
            call(name, "core.list")


def test_windows_pipe_pin_mismatch_and_arbitrary_paths_fail_before_connect():
    with pytest.raises(PermissionError, match="pinned"):
        call("AegisPlatform-" + "0" * 32 + "-" + str(GENERATION), "platform.status")
    for bad in (
        "", "\\\\.\\pipe\\AegisPlatform-" + "0" * 32 + "-" + str(GENERATION),
        "AegisPlatform-" + "0" * 32 + "-3/../x", "x" * 200,
    ):
        with pytest.raises(ValueError, match="pipe name"):
            call(bad, "platform.status")


def test_windows_pipe_noncanonical_platform_or_generation_rejected():
    name = windows_management_pipe_name(
        platform_id=PLATFORM_ID, generation=GENERATION,
    )
    with pytest.raises(ValueError, match="UUID"):
        windows_management_pipe_name(platform_id="platform:alpha", generation=3)
    with pytest.raises(ValueError, match="generation"):
        windows_management_pipe_name(platform_id=PLATFORM_ID, generation=0)
    with pytest.raises(ValueError, match="unsupported"):
        call(name, "module.remove")
