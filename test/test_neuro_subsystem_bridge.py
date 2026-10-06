from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace

from sofia.emotion.model import ActiveEmotion, CurrentEmotionalState
from sofia.environment.model import (
    DaylightObservation,
    DaylightState,
    EnvironmentFreshness,
    EnvironmentSnapshot,
    MobileActivityState,
    MobileDeviceObservation,
    MobileNetworkTransport,
    Season,
    WeatherObservation,
)
from sofia.neuro import (
    NeuralSignal,
    NeuroInputCoordinator,
    NeuroObservabilityStore,
    NeuroRuntime,
    NeuroWakeMode,
)
from sofia.ops.model import HostTelemetry
from sofia.voice import TTSStatus


NOW = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc)


def _database(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE distributed_node_identity(
                node_id TEXT PRIMARY KEY,name TEXT,public_key_sha256 TEXT,
                provisioned_at TEXT,recorded_by TEXT,retired INTEGER
            );
            INSERT INTO distributed_node_identity VALUES(
                'node-1','Venus','pin','2026-10-01T00:00:00+00:00','Sparks',0
            );
            CREATE TABLE ops_fleet_reconciliation(
                proposal_key TEXT PRIMARY KEY,active INTEGER
            );
            INSERT INTO ops_fleet_reconciliation VALUES('drift-1',1);
            CREATE TABLE ops_workload_instance(phase TEXT);
            INSERT INTO ops_workload_instance VALUES('failed');
            CREATE TABLE interact_goals(
                id TEXT,priority INTEGER,status TEXT,created_at TEXT
            );
            INSERT INTO interact_goals VALUES(
                'goal-private-title-is-not-read',5,'proposed','2026-10-06T17:00:00+00:00'
            );
            CREATE TABLE application_background_claims(
                status TEXT,finished_at TEXT
            );
            INSERT INTO application_background_claims VALUES(
                'failed','2026-10-06T17:30:00+00:00'
            );
            CREATE TABLE interaction_session_controls(
                session_id TEXT,stopped INTEGER
            );
            INSERT INTO interaction_session_controls VALUES('session-1',1);
            CREATE TABLE interaction_evidence(
                session_id TEXT,status TEXT,occurred_at TEXT
            );
            INSERT INTO interaction_evidence VALUES(
                'session-1','recorded','2026-10-06T17:45:00+00:00'
            );
            CREATE TABLE net_cloudflare_tunnel_status(
                singleton INTEGER PRIMARY KEY,configured INTEGER,state TEXT,
                public_url TEXT,pid INTEGER,restart_count INTEGER,
                updated_at TEXT,last_exit_code INTEGER,error_kind TEXT
            );
            INSERT INTO net_cloudflare_tunnel_status VALUES(
                1,1,'degraded','https://sofia.example.com',NULL,2,
                '2026-10-06T17:59:00+00:00',1,NULL
            );
            CREATE TABLE net_web_evidence(
                evidence_id TEXT PRIMARY KEY,status TEXT,observed_at TEXT
            );
            INSERT INTO net_web_evidence VALUES(
                'web-evidence:test','failed','2026-10-06T17:58:00+00:00'
            );
        """)


def _environment():
    weather = WeatherObservation(
        condition="Light Rain", observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=25), source_id="weather:test",
    )
    mobile = MobileDeviceObservation(
        observed_at=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=5), source_id="mobile:test",
        timezone="UTC", battery_percent=12.0, charging=False,
        network=MobileNetworkTransport.OFFLINE,
        activity=MobileActivityState.WALKING,
    )
    return EnvironmentSnapshot(
        observed_at=NOW, utc_time=NOW, host_local_time=NOW,
        host_timezone_label="UTC", user_local_time=NOW,
        season=Season.AUTUMN,
        daylight=DaylightObservation(DaylightState.DAY),
        weather=weather, weather_freshness=EnvironmentFreshness.CURRENT,
        mobile=mobile, mobile_freshness=EnvironmentFreshness.CURRENT,
    )


def test_production_bridge_maps_all_available_authoritative_domains(tmp_path):
    path = tmp_path / "sofia.db"
    _database(path)
    store = NeuroObservabilityStore(path)
    runtime = NeuroRuntime(observability=store)
    coordinator = NeuroInputCoordinator(runtime, path)
    emotion = CurrentEmotionalState(
        as_of=NOW, subject="sparks", tone="mixed",
        active=(ActiveEmotion("joy", 0.8, ("e1",), ("event-1",)),),
    )
    telemetry = HostTelemetry(
        observed_at=NOW, cpu_percent=92.0,
        ram_used_bytes=9, ram_total_bytes=10,
        storage_free_bytes=1024,
        temperature_c=82.0, throttled=True,
    )
    voice = TTSStatus(
        enabled=True, started=True, backend_name="test", available=True,
        healthy=True, selected_voice="Sofia", voices=("Sofia",),
        supported_controls=("rate",), reason="ready", evidence_ref="voice:test",
    )
    snapshot = coordinator.refresh(
        now=NOW, environment=_environment(), emotion=emotion,
        telemetry=telemetry, voice=voice,
        avatar={"current": {
            "outfit_id": "autumn-cozy",
            "appearance": {
                "posture": "relaxed", "expression": "smile",
                "activity": "conversation",
            },
        }},
        memories=(SimpleNamespace(id="memory-secret", content="never persisted"),),
        habits=(SimpleNamespace(pattern_id="habit-1", confidence=0.84),),
        relationship=SimpleNamespace(occurred_at=NOW - timedelta(hours=2)),
        goal_priorities=((SimpleNamespace(
            id="goal-1", status=SimpleNamespace(value="active"), confidence=0.9,
        ), 0.81),),
        session_id="session-1",
    )

    kinds = {item.kind for item in (snapshot.focus, *snapshot.secondary) if item}
    all_kinds = {item.kind for item in runtime.recent_signals}
    assert kinds
    assert {
        "environment", "body", "emotion", "ops", "fleet", "memory",
        "habit", "relationship", "goal", "run", "interaction", "avatar",
        "voice",
        "network",
    } <= all_kinds
    persisted = json.dumps(store.current()) + json.dumps(store.recent())
    assert "never persisted" not in persisted
    assert "goal-private-title-is-not-read" not in persisted
    assert "winner_reason" in persisted
    # Diagnostics survive restart, but transient attention is intentionally
    # never restored as neural evidence.
    assert NeuroRuntime(
        observability=NeuroObservabilityStore(path)
    ).last_snapshot is None


def test_neuro_routing_preserves_verify_and_scales_auto_compute(tmp_path):
    path = tmp_path / "sofia.db"
    _database(path)
    runtime = NeuroRuntime(observability=NeuroObservabilityStore(path))
    assert runtime.routing_decision(existing_hint="verify").mode is NeuroWakeMode.VERIFY

    runtime.observe_signal(NeuralSignal(
        source="workload:failure", kind="ops", value=1.0,
        confidence=1.0, novelty=1.0, urgency=1.0,
        observed_at=NOW, ttl_seconds=300.0,
    ))
    assert runtime.routing_decision().mode is NeuroWakeMode.DEEP


def test_gaia_reflex_bridge_accepts_attention_only_body_signal(tmp_path):
    path = tmp_path / "sofia.db"
    _database(path)
    coordinator = NeuroInputCoordinator(NeuroRuntime(), path)
    body = NeuralSignal(
        source="gaia:obstacle", kind="body", value=1.0,
        confidence=1.0, novelty=1.0, urgency=1.0,
        observed_at=NOW, ttl_seconds=5.0,
    )
    assert coordinator.observe_reflex(body).focus.kind == "body"
    invalid = NeuralSignal(
        source="gaia:motor", kind="goal", value=1.0,
        confidence=1.0, novelty=1.0, urgency=1.0,
        observed_at=NOW, ttl_seconds=5.0,
    )
    try:
        coordinator.observe_reflex(invalid)
    except ValueError as exc:
        assert "body signal" in str(exc)
    else:
        raise AssertionError("motor/goal signals must not enter the reflex bridge")


def test_neuro_gates_optional_wakes_and_only_advises_background_ordering():
    runtime = NeuroRuntime()
    assert runtime.should_wake_for_reflection() is False
    assert runtime.background_priority("habit_analysis") == 0.0

    runtime.observe_signal(NeuralSignal(
        source="state:longing", kind="emotion", value=0.9,
        confidence=1.0, novelty=0.8, urgency=0.7,
        observed_at=NOW, ttl_seconds=300.0,
    ))
    assert runtime.should_wake_for_reflection() is True
    assert runtime.background_priority("reflection_outreach") > 0.0


def test_neuro_network_attention_is_advisory_not_emotion_or_expression(tmp_path):
    path = tmp_path / "sofia.db"
    _database(path)
    runtime = NeuroRuntime()
    coordinator = NeuroInputCoordinator(runtime, path)
    coordinator.refresh(now=NOW, environment=_environment())

    network = tuple(
        signal for signal in runtime.recent_signals if signal.kind == "network"
    )
    assert {signal.source for signal in network} == {
        "cloudflare:degraded", "web:failed",
    }
    assert runtime.background_priority("web research retry") > 0.0
    assert not any(signal.kind in {"emotion", "avatar"} for signal in network)
