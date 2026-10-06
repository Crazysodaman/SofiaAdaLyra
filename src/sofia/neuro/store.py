"""Bounded NEURO observability persistence; transient activations are not restored."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from .model import NeuralSignal, NeuroRoutingDecision, NeuroStateSnapshot


class NeuroObservabilityStore:
    """Persist the latest diagnostic projection and a bounded signal-event ring."""

    def __init__(self, state_path: str | Path, *, max_events: int = 256) -> None:
        if type(max_events) is not int or not 16 <= max_events <= 4096:
            raise ValueError("max_events must be an integer in 16..4096")
        self.path = Path(state_path)
        self.max_events = max_events
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS neuro_snapshot (
                    state_key TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    routing_json TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS neuro_signal_event (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    value REAL NOT NULL,
                    confidence REAL NOT NULL,
                    novelty REAL NOT NULL,
                    urgency REAL NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS neuro_wake_event (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    llm_called INTEGER NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS neuro_performance_event (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    refresh_ms REAL NOT NULL,
                    cpu_ms REAL NOT NULL,
                    signal_count INTEGER NOT NULL,
                    active_node_count INTEGER NOT NULL,
                    goal_count INTEGER NOT NULL,
                    db_reads INTEGER NOT NULL,
                    db_writes INTEGER NOT NULL,
                    observed_at TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _activation(item):
        if item is None:
            return None
        return {
            "key": item.key,
            "source": item.source,
            "kind": item.kind,
            "score": item.score,
            "novelty": item.novelty,
            "updated_at": item.updated_at.isoformat(),
        }

    @classmethod
    def snapshot_payload(
        cls,
        snapshot: NeuroStateSnapshot,
        signals: tuple[NeuralSignal, ...] = (),
    ) -> dict:
        winning_input = None
        if snapshot.focus is not None:
            winning_input = next((
                item for item in reversed(signals)
                if item.kind == snapshot.focus.kind
                and item.source == snapshot.focus.source
            ), None)
        winner_reason = (
            "No active signals."
            if snapshot.focus is None
            else (
                f"{snapshot.focus.key} has the highest bounded salience score "
                f"({snapshot.focus.score:.3f}) after decay."
                if winning_input is None
                else (
                    f"{snapshot.focus.key} won with score "
                    f"{snapshot.focus.score:.3f}; input value="
                    f"{winning_input.value:.3f}, confidence="
                    f"{winning_input.confidence:.3f}, novelty="
                    f"{winning_input.novelty:.3f}, urgency="
                    f"{winning_input.urgency:.3f}, followed by bounded decay."
                )
            )
        )
        return {
            "generated_at": snapshot.generated_at.isoformat(),
            "focus": cls._activation(snapshot.focus),
            "secondary": [cls._activation(item) for item in snapshot.secondary],
            "active_signal_count": snapshot.active_signal_count,
            "homeostasis": {
                "cognitive_load": snapshot.homeostasis.cognitive_load,
                "novelty_load": snapshot.homeostasis.novelty_load,
                "competition_pressure": snapshot.homeostasis.competition_pressure,
            },
            "winner_reason": winner_reason,
        }

    def record(
        self,
        *,
        snapshot: NeuroStateSnapshot,
        signals: tuple[NeuralSignal, ...] = (),
        routing: NeuroRoutingDecision | None = None,
    ) -> None:
        if not isinstance(snapshot, NeuroStateSnapshot):
            raise TypeError("snapshot must be NeuroStateSnapshot")
        if not isinstance(signals, tuple) or any(
            not isinstance(item, NeuralSignal) for item in signals
        ):
            raise TypeError("signals must be NeuralSignal values")
        if routing is not None and not isinstance(routing, NeuroRoutingDecision):
            raise TypeError("routing must be NeuroRoutingDecision or None")
        payload = json.dumps(
            self.snapshot_payload(snapshot, signals), sort_keys=True,
            separators=(",", ":"), ensure_ascii=True,
        )
        routing_payload = None if routing is None else json.dumps({
            "mode": routing.mode.value,
            "reason": routing.reason,
        }, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as db, db:
            db.execute("""
                INSERT INTO neuro_snapshot(state_key,snapshot_json,routing_json,updated_at)
                VALUES('current',?,?,?)
                ON CONFLICT(state_key) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json,
                    routing_json=COALESCE(excluded.routing_json,neuro_snapshot.routing_json),
                    updated_at=excluded.updated_at
            """, (payload, routing_payload, snapshot.generated_at.isoformat()))
            db.executemany("""
                INSERT INTO neuro_signal_event(
                    kind,source,value,confidence,novelty,urgency,observed_at
                ) VALUES(?,?,?,?,?,?,?)
            """, tuple((
                item.kind, item.source, item.value, item.confidence,
                item.novelty, item.urgency, item.observed_at.isoformat(),
            ) for item in signals))
            db.execute("""
                DELETE FROM neuro_signal_event
                WHERE seq NOT IN (
                    SELECT seq FROM neuro_signal_event ORDER BY seq DESC LIMIT ?
                )
            """, (self.max_events,))

    def current(self) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT snapshot_json,routing_json,updated_at "
                "FROM neuro_snapshot WHERE state_key='current'"
            ).fetchone()
        if row is None:
            return None
        return {
            "snapshot": json.loads(row[0]),
            "routing": None if row[1] is None else json.loads(row[1]),
            "updated_at": row[2],
        }

    def recent(self, *, limit: int = 32) -> tuple[dict, ...]:
        if type(limit) is not int or not 1 <= limit <= self.max_events:
            raise ValueError("limit outside retained event bounds")
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT kind,source,value,confidence,novelty,urgency,observed_at
                FROM neuro_signal_event ORDER BY seq DESC LIMIT ?
            """, (limit,)).fetchall()
        return tuple(dict(row) for row in rows)

    def record_wake(
        self, *, mode: str, reason: str, llm_called: bool, observed_at: datetime,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO neuro_wake_event(mode,reason,llm_called,observed_at) "
                "VALUES(?,?,?,?)",
                (mode, reason[:240], int(llm_called), observed_at.isoformat()),
            )
            db.execute("""
                DELETE FROM neuro_wake_event WHERE seq NOT IN (
                    SELECT seq FROM neuro_wake_event ORDER BY seq DESC LIMIT ?
                )
            """, (self.max_events,))

    def wake_metrics(self) -> dict[str, int]:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT COUNT(*),SUM(CASE WHEN llm_called=0 THEN 1 ELSE 0 END),"
                "SUM(CASE WHEN llm_called=1 THEN 1 ELSE 0 END) FROM neuro_wake_event"
            ).fetchone()
        return {
            "decisions": int(row[0] or 0),
            "llm_avoided": int(row[1] or 0),
            "llm_called": int(row[2] or 0),
        }

    def record_performance(
        self, *, refresh_ms: float, cpu_ms: float, signal_count: int,
        active_node_count: int, goal_count: int, db_reads: int, db_writes: int,
        observed_at: datetime,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute("""
                INSERT INTO neuro_performance_event(
                    refresh_ms,cpu_ms,signal_count,active_node_count,goal_count,
                    db_reads,db_writes,observed_at
                ) VALUES(?,?,?,?,?,?,?,?)
            """, (
                refresh_ms, cpu_ms, signal_count, active_node_count, goal_count,
                db_reads, db_writes, observed_at.isoformat(),
            ))
            db.execute("""
                DELETE FROM neuro_performance_event WHERE seq NOT IN (
                    SELECT seq FROM neuro_performance_event ORDER BY seq DESC LIMIT ?
                )
            """, (self.max_events,))

    def latest_performance(self) -> dict | None:
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM neuro_performance_event ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return None if row is None else dict(row)


def neuro_observability_text(state_path: str | Path) -> str:
    store = NeuroObservabilityStore(state_path)
    current = store.current()
    if current is None:
        return "NEURO has not recorded a production snapshot yet."
    snapshot = current["snapshot"]
    homeostasis = snapshot["homeostasis"]
    focus = snapshot.get("focus")
    lines = [
        f"Updated: {current['updated_at']}",
        "Primary attention: " + (
            "none" if focus is None else f"{focus['key']} ({focus['score']:.3f})"
        ),
        "Secondary activations: " + (
            ", ".join(
                f"{item['key']} ({item['score']:.3f})"
                for item in snapshot.get("secondary", ())
            ) or "none"
        ),
        f"Active signals: {snapshot['active_signal_count']}",
        f"Cognitive load: {homeostasis['cognitive_load']:.3f}",
        f"Novelty load: {homeostasis['novelty_load']:.3f}",
        f"Competition pressure: {homeostasis['competition_pressure']:.3f}",
        f"Why this signal won: {snapshot['winner_reason']}",
    ]
    if current.get("routing"):
        route = current["routing"]
        lines.append(f"Cognitive route: {route['mode']} — {route['reason']}")
    metrics = store.wake_metrics()
    lines.append(
        "Wake decisions: "
        f"{metrics['decisions']} (LLM avoided {metrics['llm_avoided']}; "
        f"called {metrics['llm_called']})"
    )
    performance = store.latest_performance()
    if performance is not None:
        lines.append(
            "Refresh cost: "
            f"{performance['refresh_ms']:.2f} ms wall / "
            f"{performance['cpu_ms']:.2f} ms CPU; signals "
            f"{performance['signal_count']}; nodes "
            f"{performance['active_node_count']}; goals "
            f"{performance['goal_count']}; instrumented DB read/write batches "
            f"{performance['db_reads']}/{performance['db_writes']}"
        )
        if performance["refresh_ms"] > 250.0:
            lines.append(
                "Performance warning: refresh exceeded the 250 ms advisory threshold."
            )
    recent = store.recent(limit=min(16, store.max_events))
    lines.append("Recent signals:")
    lines.extend(
        f"  {item['kind']}:{item['source']} value={item['value']:.3f} "
        f"urgency={item['urgency']:.3f} at {item['observed_at']}"
        for item in recent
    )
    if not recent:
        lines.append("  none")
    return "\n".join(lines)
