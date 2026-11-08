"""CORE-001: OS process lock + real disposable SQLite writer crash/restart.

This proves local state process exclusion only; it is not distributed
writer consensus or production installed-host acceptance.
"""
from __future__ import annotations

import multiprocessing
from pathlib import Path
import sqlite3
import time

import pytest


def _writer(state_text: str, acquired, hold, observations, *, crash=False):
    from sofia.platform.run.process_lock import StateProcessLock

    path = Path(state_text)
    try:
        with StateProcessLock(
            path, resource="core-runtime", owner_label="Core runtime child",
        ):
            with sqlite3.connect(path, timeout=2) as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS writer_journal (writer TEXT PRIMARY KEY)"
                )
                db.execute(
                    "INSERT INTO writer_journal(writer) VALUES(?)",
                    (multiprocessing.current_process().name,),
                )
            observations.put(("acquired", multiprocessing.current_process().name))
            acquired.set()
            if crash:
                with sqlite3.connect(path, timeout=2) as db:
                    db.execute("PRAGMA journal_mode=WAL")
                # Leave an unfinished transaction; OS termination must roll it
                # back without allowing an overlapping writer to gain lock.
                con = sqlite3.connect(path, isolation_level=None, timeout=2)
                con.execute("BEGIN IMMEDIATE")
                con.execute("INSERT INTO writer_journal(writer) VALUES('uncommitted')")
                observations.put(("uncommitted", multiprocessing.current_process().name))
                hold.wait(timeout=10)
            else:
                hold.wait(timeout=10)
    except Exception as exc:
        observations.put(("denied", type(exc).__name__))


def _context():
    return multiprocessing.get_context("spawn")


def _start(ctx, state, *, crash=False):
    acquired, hold, observed = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(
        target=_writer,
        args=(str(state), acquired, hold, observed),
        kwargs={"crash": crash},
        name=f"synthetic-writer-{int(time.time_ns())}",
    )
    process.start()
    return process, acquired, hold, observed


def _finish(process, hold):
    hold.set()
    process.join(timeout=5)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join(timeout=5)
    assert not process.is_alive()


def test_core001_duplicate_writer_denied_and_restart_reuses_one_sqlite(tmp_path):
    state = tmp_path / "synthetic-writer.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE preserved(k TEXT PRIMARY KEY)")
        db.execute("INSERT INTO preserved VALUES('identity')")
    ctx = _context()
    first, first_ready, first_release, first_events = _start(ctx, state)
    try:
        assert first_ready.wait(timeout=5)
        assert first_events.get(timeout=3)[0] == "acquired"
        second, second_ready, second_release, second_events = _start(ctx, state)
        try:
            assert second_events.get(timeout=5)[0] == "denied"
            assert not second_ready.is_set()
        finally:
            _finish(second, second_release)
    finally:
        _finish(first, first_release)
    third, third_ready, third_release, third_events = _start(ctx, state)
    try:
        assert third_ready.wait(timeout=5)
        assert third_events.get(timeout=3)[0] == "acquired"
    finally:
        _finish(third, third_release)
    with sqlite3.connect(state) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("SELECT k FROM preserved").fetchone() == ("identity",)
        assert db.execute("SELECT count(*) FROM writer_journal").fetchone() == (2,)


def test_core001_crash_releases_lock_and_recovers_uncommitted_sqlite(tmp_path):
    state = tmp_path / "synthetic-crash.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE preserved(k TEXT PRIMARY KEY)")
        db.execute("INSERT INTO preserved VALUES('identity')")
    ctx = _context()
    first, first_ready, first_release, first_events = _start(
        ctx, state, crash=True,
    )
    try:
        assert first_ready.wait(timeout=5)
        assert first_events.get(timeout=3)[0] == "acquired"
        assert first_events.get(timeout=3)[0] == "uncommitted"
        # Terminate only this disposable synthetic process, never real services.
        first.terminate()
        first.join(timeout=5)
        assert not first.is_alive()
    finally:
        if first.is_alive():
            _finish(first, first_release)
    second, second_ready, second_release, second_events = _start(ctx, state)
    try:
        assert second_ready.wait(timeout=5)
        assert second_events.get(timeout=3)[0] == "acquired"
    finally:
        _finish(second, second_release)
    with sqlite3.connect(state) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("SELECT k FROM preserved").fetchone() == ("identity",)
        assert db.execute(
            "SELECT count(*) FROM writer_journal WHERE writer='uncommitted'"
        ).fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM writer_journal").fetchone() == (2,)
